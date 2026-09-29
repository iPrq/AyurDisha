# AyurDisha Backend — Developer Guide

**Status:** Phases 1–6 complete (shared foundation + Section 3 & Patent Advisor).  
**Product Review, NBA/ABS, real Qdrant/Neo4j, and frontend are deferred.**

---

## 1. What this backend does

AyurDisha is a **decision-support** API for Ayurvedic IP guidance. It is **not legal advice**.

This tranche ships one workflow:

```
POST /api/v1/patent-advisor
```

Pipeline:

```
InputParser
  → Botanical Normalizer (shared)
  → Legal/Patent Retrieval (jurisdiction + legal_scope filters)
  → Section 3 Scorer + deterministic risk indicator
  → Prior-Art Advisor
  → IP Route Analysis
  → Critic Verifier (shared)
```

Safety rules baked in:

- Never invent statutes, foreign law, patent numbers, or URLs
- Cite only retrieved evidence (`source_id`)
- Ambiguous botanicals → do **not** silently pick; escalate
- `legal_scope=international` with no comparative hits → `HUMAN_REVIEW_REQUIRED`
- Two separate scores:
  - `patentability_risk`: deterministic Section 3 **risk indicator** (weighted 3(d)/3(e)/3(p)), not “probability of approval”
  - `grant_likelihood`: **LLM-estimated** grant probability (`grant_likelihood` node) with confidence, key factors and rationale — uncalibrated against Patent Office outcomes; not computed when no sources are retrieved

### PDF uploads

Each workflow has a multipart `POST .../extract` endpoint (`file` field). It validates the upload (PDF only, `PDF_MAX_BYTES`), extracts text with OCR fallback for scanned pages, and asks the LLM to pull form fields. Validation lives in `api/pdf_upload.py`.

| Endpoint | Extracted fields | How the document is used |
|---|---|---|
| `POST /api/v1/patent-advisor/extract` | product, ingredients, summary | Frontend sends `document_text` with `/patent-advisor`; included in Section 3 / prior-art / IP-route / grant prompts |
| `POST /api/v1/product-review/extract` | product, ingredients, product_category, summary | Frontend sends `document_text` with `/product-review`; included in market / legal / resource prompts |
| `POST /api/v1/nba-abs/extract` | product, ingredients (product_category, summary also returned) | Pre-fill only; `/nba-abs` does not accept document text |

Document text is prompt context only, never evidence: it is fenced and labelled "do not cite", and citations are still filtered to retrieved source ids.

---

## 2. Quick start

### Prerequisites

- Python **3.10+**
- [uv](https://github.com/astral-sh/uv) (recommended; project already has `uv.lock`)

### Install & run

```powershell
cd d:\Code\hackathon\AyurDisha\app
uv sync
uv run uvicorn main:app --reload --port 8000
```

Open:

- Health: http://127.0.0.1:8000/health  
- Swagger: http://127.0.0.1:8000/docs  

### Optional Gemini key

Copy `.env.example` → `.env` and set:

```env
GOOGLE_API_KEY=your_key_here
LLM_MODEL=gemini-2.0-flash
LLM_TEMPERATURE=0
```

**Current Patent Advisor path is deterministic + mock retrieval/KG.** The LLM factory exists for later/injected use; tests never call paid APIs.

### Run tests

```powershell
cd d:\Code\hackathon\AyurDisha\app
uv run pytest tests/ -v
```

Expected: **32 passed**.

---

## 3. Call the API

### Domestic (Indian Section 3 focus)

```powershell
curl -X POST http://127.0.0.1:8000/api/v1/patent-advisor `
  -H "Content-Type: application/json" `
  -d '{
    "product": "Ashwagandha capsule",
    "ingredients": ["Ashwagandha"],
    "language": "en",
    "jurisdiction": "india",
    "legal_scope": "domestic"
  }'
```

### International switch

```powershell
curl -X POST http://127.0.0.1:8000/api/v1/patent-advisor `
  -H "Content-Type: application/json" `
  -d '{
    "product": "Ashwagandha capsule",
    "ingredients": ["Ashwagandha"],
    "language": "en",
    "jurisdiction": "india",
    "legal_scope": "international"
  }'
```

| Field | Meaning |
|-------|---------|
| `jurisdiction` | Primary domestic jurisdiction (default `india`) |
| `legal_scope` | `domestic` \| `international` — the legal switch |

**Behavior:**

| `legal_scope` | Retrieval / reasoning |
|---------------|------------------------|
| `domestic` | Only sources tagged domestic for that jurisdiction (e.g. Section 3 fixtures) |
| `international` | Only comparative/international fixtures; if none → escalate, never invent foreign law |

### Example response shape (abbreviated)

```json
{
  "product": "Ashwagandha capsule",
  "ingredients": ["Ashwagandha"],
  "jurisdiction": "india",
  "legal_scope": "domestic",
  "botanical": {
    "status": "RESOLVED",
    "botanical_name": "Withania somnifera",
    "synonyms": ["Ashwagandha", "..."],
    "phytochemicals": ["withanolides", "..."],
    "confidence": 0.95
  },
  "section3": { "provisions": [ /* any of the 15 supported clauses */ ], "summary": "...",
                "rejected_clauses": [], "evidence_gap_clauses": [] },
  "patentability_risk": {
    "score": 0.7,
    "triggered_clauses": ["3(d)", "3(p)"],
    "unweighted_triggered_clauses": [],
    "label": "decision_support_risk_indicator"
  },
  "prior_art": { "findings": [], "summary": "..." },
  "ip_routes": { "suggestions": [ /* Patent, Trademark, Design, Trade Secret */ ] },
  "verification": { "outcome": "PASS|FAIL|HUMAN_REVIEW_REQUIRED", "claims": [] },
  "retrieved_sources": [ /* all is_fixture: true in mock mode */ ],
  "final_answer": "...",
  "disclaimer": "AyurDisha provides decision support only..."
}
```

### Ambiguous botanical demo

Use ingredient `"ginseng"` or `"ambiguous_herb"`:

- `botanical.status` = `AMBIGUOUS`
- `botanical_name` not chosen
- `verification.outcome` / `verification_status` → `HUMAN_REVIEW_REQUIRED`
- `escalation_reasons` includes `ambiguous_botanical`

---

## 4. Package map

```
app/
  main.py                          # FastAPI app + /health + patent-advisor router
  config.py                        # env settings, Section 3 weights, thresholds
  .env.example
  llm/provider.py                  # get_chat_model(); injectable; Gemini if key set
  graph/
    models.py                      # LegalScope, RetrievedSource, Section3, API models…
    state.py                       # PatentAdvisorState (TypedDict)
    prompts.py                     # system prompts + legal_scope_instruction()
    shared/
      botanical.py                 # Botanical Normalizer node
      verifier.py                  # Critic Verifier node
      input_parser.py
    patent_advisor/
      retrieval.py                 # retrieval node (scope-aware)
      section3.py                  # Section 3 scorer (15 clauses; no 3(g))
      risk.py                      # deterministic risk = Σ weights
      prior_art.py
      ip_routes.py
    patent_advisor_graph.py        # StateGraph wiring
  retrieval/
    base.py                        # filter_sources / LegalRetriever protocol
    mock.py                        # fixture corpus (TEST FIXTURE markers)
  knowledge_graph/
    base.py                        # BotanicalKnowledgeGraph protocol
    mock.py                        # Ashwagandha → Withania somnifera, etc.
  api/patent_advisor.py            # POST /api/v1/patent-advisor (+ /extract)
  api/pdf_upload.py                # shared PDF validation + product field extraction
  tests/                           # 32 tests, no paid API
```

**Not built yet:** `product_review_graph.py`, `nba_abs_graph.py`, real Qdrant/BM25/Neo4j, frontend.

---

## 5. Architecture deep dive

### 5.1 Shared services vs feature graphs

| Layer | Role |
|-------|------|
| Botanical Normalizer | Shared — resolve plant names via KG |
| Hybrid Retrieval | Shared protocol — mock now; Qdrant/BM25 later |
| Critic Verifier | Shared — strip unsupported claims |
| Patent Advisor graph | Feature workflow (this tranche) |

Botanical / Verifier are **backend services**, not user-facing products.

### 5.2 Graph nodes (what each writes)

| Node | Reads | Writes |
|------|-------|--------|
| `input_parser` | product, ingredients | `botanical_input`, `parsed_notes` |
| `botanical` | botanical_input / ingredients | `botanical`, `botanical_name`, status, synonyms, phytochemicals; escalates if AMBIGUOUS |
| `retrieval` | query fields + legal_scope | `retrieved_sources`, `retrieval_insufficient` |
| `section3` | sources + scope | `section3`, `patentability_risk`, `patentability_risk_score` |
| `prior_art` | sources | `prior_art` |
| `ip_routes` | sources + section3 + risk | `ip_routes`, draft `final_answer` |
| `verifier` | claims + sources | `verification`, cleaned `final_answer`, escalation |

### 5.3 Deterministic risk formula

Configured in `config.py` / env (`SECTION3_WEIGHT_D/E/P`):

```text
risk = 0
if 3(d) triggered: risk += weight_d   # default 0.35
if 3(e) triggered: risk += weight_e   # default 0.30
if 3(p) triggered: risk += weight_p   # default 0.35
risk = min(1.0, risk)
```

Implemented in `graph/patent_advisor/risk.py` — **Python only**, never asked of an LLM.

Supported Section 3 clauses: 3(a), 3(b), 3(c), 3(d), 3(e), 3(f), 3(h), 3(i), 3(j), 3(k),
3(l), 3(m), 3(n), 3(o), 3(p) (`SUPPORTED_SECTION3_CLAUSES` in `graph/models.py`). 3(g) is
never an active provision; if the model returns it (or any other unsupported clause) it is
dropped, recorded in `rejected_clauses`, and escalated as `unsupported_section3_clause`.
Only 3(d)/3(e)/3(p) have weights. Other triggered clauses add **nothing** to the score (no
weights are invented) and are listed in `unweighted_triggered_clauses`. Each clause counts once.

Evidence validation (`section3.py`): a cited `evidence_source_id` is kept only if it is a
retrieved source and that source is unlabeled (guideline, preamble, patent) or labeled with
the same clause. A triggered clause left without valid evidence is cleared, marked
`evidence_gap`, listed in `evidence_gap_clauses`, and escalated as `section3_evidence_gap`,
which the shared verifier always turns into `HUMAN_REVIEW_REQUIRED`.

### 5.4 Mock fixtures vs real infra

All mock legal texts are labeled **`[TEST FIXTURE — NOT OFFICIAL TEXT]`** and `is_fixture=True`.

| Interface | Mock today | Real |
|-----------|------------|-------|
| `BotanicalKnowledgeGraph` | `knowledge_graph/mock.py` | Neo4j (later) |
| `LegalRetriever` | `retrieval/mock.py` | `retrieval/qdrant_hybrid.py` (Qdrant + BM25), selected with `RETRIEVER_BACKEND=qdrant` — see [RETRIEVAL_GUIDE.md](RETRIEVAL_GUIDE.md) |

To inject fakes in tests:

```python
from graph.patent_advisor_graph import build_patent_advisor_graph
from retrieval.mock import MockLegalRetriever

graph = build_patent_advisor_graph(retriever=MockLegalRetriever(corpus=[...]))
```

---

## 6. Configuration reference

| Env var | Default | Purpose |
|---------|---------|---------|
| `GOOGLE_API_KEY` | unset | Enables Gemini via `get_chat_model()` |
| `LLM_MODEL` | `gemini-2.0-flash` | Model id |
| `LLM_TEMPERATURE` | `0` | Always 0 for legal reasoning |
| `DEFAULT_JURISDICTION` | `india` | Default jurisdiction |
| `DEFAULT_LEGAL_SCOPE` | `domestic` | Default switch |
| `SECTION3_WEIGHT_D/E/P` | 0.35 / 0.30 / 0.35 | Risk weights |
| `BOTANICAL_CONFIDENCE_THRESHOLD` | `0.7` | Resolve vs leave unresolved |
| `VERIFICATION_MIN_SUPPORT_RATIO` | `0.6` | Verifier FAIL threshold |
| `MAX_VERIFIER_RETRIES` | `1` | Placeholder for future retry loop |

---

## 7. Programmatic usage (without HTTP)

```python
from graph.models import LegalScope
from graph.patent_advisor_graph import run_patent_advisor

result = run_patent_advisor({
    "product": "Ashwagandha capsule",
    "ingredients": ["Ashwagandha"],
    "language": "en",
    "jurisdiction": "india",
    "legal_scope": LegalScope.DOMESTIC,
})
print(result["botanical_name"])
print(result["patentability_risk_score"])
print(result["verification_status"])
```

Working directory / `PYTHONPATH` must include `app/` (uvicorn and pytest `conftest.py` already handle this).

---

## 8. Test catalog

| File | Covers |
|------|--------|
| `test_botanical.py` | Known Ashwagandha, ambiguous ginseng, unknown, LLM inject |
| `test_legal_scope_filter.py` | Domestic/international filters, empty intl corpus |
| `test_verifier.py` | Supported / unsupported / missing evidence / escalate |
| `test_section3_risk.py` | Weight math, fixture scoring, intl no-invent |
| `test_patent_advisor_graph.py` | Full graph domestic / ambiguous / intl / empty intl |
| `test_patent_advisor_api.py` | `/health`, POST domestic/intl, 422 validation |
| `test_qdrant_config.py` | Local client, cloud URL/key validation, secret redaction |
| `test_chunking.py` | Statute clause / guideline / patent chunking, deterministic IDs, sidecars |
| `test_bm25.py` | BM25 ranking, ID mapping, persistence + rebuild |
| `test_rrf.py` | RRF math, dedupe, deterministic ties |
| `test_qdrant_hybrid.py` | End-to-end ingest + hybrid retrieval, scope/source filters, conversion |
| `test_retriever_factory.py` | mock/qdrant selection, fail-loud config errors, reranker toggle |
| `test_cloud_smoke.py` | Opt-in (`RUN_CLOUD_TESTS=1`) read-only Qdrant Cloud check |

---

## 9. How to extend

### Add a botanical synonym

Edit `knowledge_graph/mock.py` `_LOOKUP` / entity fixtures.

### Add a legal fixture for scope tests

Append a `RetrievedSource` in `retrieval/mock.py` with:

- `jurisdiction`
- `legal_scope` (`domestic` or `international`)
- `is_fixture=True`
- Clear `[TEST FIXTURE]` wording in `text`

### Real retriever (Qdrant + BM25)

Implemented in `retrieval/qdrant_hybrid.py`; the API picks it via `retrieval/factory.py::get_retriever`
when `RETRIEVER_BACKEND=qdrant`. Setup, ingestion and AWS deployment: [RETRIEVAL_GUIDE.md](RETRIEVAL_GUIDE.md).

### Next product features (deferred)

1. Product Review graph + `POST /api/v1/product-review`
2. NBA/ABS graph + `POST /api/v1/nba-abs`
3. Real Qdrant + Neo4j
4. Verifier retry edges / richer LLM structured outputs
5. Frontend (3 cards + international switch UI)

---

## 10. Delivery checklist (this tranche)

| Item | Done |
|------|------|
| Phase 1 inventory | Yes |
| Config + LLM abstraction | Yes |
| Models / state / prompts + `legal_scope` | Yes |
| Mock KG + Botanical Normalizer + tests | Yes |
| Mock retrieval + scope filters + tests | Yes |
| Critic Verifier + tests | Yes |
| Patent Advisor graph + risk + tests | Yes |
| `POST /api/v1/patent-advisor` + API tests | Yes |
| Product Review / NBA / real infra / UI | **No — next gates** |

---

## 11. Troubleshooting

| Symptom | Fix |
|---------|-----|
| `ModuleNotFoundError: config` | Run from `app/` or ensure `app` is on `sys.path` |
| API 422 | `product` is required; `legal_scope` must be `domestic` or `international` |
| Empty international sources | Expected if corpus has no intl fixtures — check escalation reasons |
| Want live Gemini | Set `GOOGLE_API_KEY`; current graph still uses deterministic scorers |
| Tests hit network | They should not — if they do, a non-mock path was wired incorrectly |

---

*Built against `docs/PATENT_ADVISOR_BACKEND_PLAN.md`. For architecture rationale see that file and `docs/LANGGRAPH_PHASE_1-3_PLAN.md`.*
