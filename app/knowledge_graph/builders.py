"""Build GraphBatches from curated seed data, the corpus, and pipeline responses."""

from __future__ import annotations

import json
import logging
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from graph.models import BotanicalResult, BotanicalStatus, RetrievedSource
from knowledge_graph.schema import (
    CATEGORY,
    CITES,
    COMPETES_WITH,
    COMPOUND,
    CONTAINS,
    DOCUMENT,
    FORMULATION,
    HERB,
    IN_CATEGORY,
    INGREDIENT,
    INGREDIENT_OF,
    MAY_REFER_TO,
    MENTIONED_IN,
    NAME,
    PATENT,
    PRODUCT,
    SOURCE,
    GraphBatch,
    alias_pattern,
    normalize,
)
from knowledge_graph.seed_data import AMBIGUOUS_NAMES, FORMULATIONS, HERBS

logger = logging.getLogger(__name__)

SNIPPET_CHARS = 600
AliasMap = dict[str, set[str]]


# ---------------------------------------------------------------------------
# Alias matching
# ---------------------------------------------------------------------------


def alias_map(batch: GraphBatch, labels: tuple[str, ...] = (HERB, FORMULATION)) -> AliasMap:
    out: AliasMap = defaultdict(set)
    for node in batch.nodes.values():
        if node.label in labels:
            for term in (node.name, *node.aliases):
                out[normalize(term)].add(node.key)
    return out


class Matcher:
    """Finds entity mentions (by name / alias) in free text."""

    def __init__(self, aliases: AliasMap) -> None:
        self.aliases = aliases
        self.pattern = alias_pattern(list(aliases))

    def counts(self, text: str) -> Counter[str]:
        found: Counter[str] = Counter()
        if not self.pattern or not text:
            return found
        for m in self.pattern.finditer(text):
            for key in self.aliases.get(normalize(m.group(0)), ()):
                found[key] += 1
        return found


# ---------------------------------------------------------------------------
# Curated seed
# ---------------------------------------------------------------------------


def build_seed_batch() -> GraphBatch:
    b = GraphBatch()
    herb_keys: dict[str, str] = {}
    for h in HERBS:
        key = b.add_node(
            HERB,
            h.botanical_name,
            aliases=list(h.names),
            confidence=h.confidence,
            family=h.family,
        )
        herb_keys[h.botanical_name] = key
        for compound in h.compounds:
            b.add_edge(key, b.add_node(COMPOUND, compound), CONTAINS)

    for term, botanicals in AMBIGUOUS_NAMES.items():
        name_key = b.add_node(NAME, term, ambiguous=True)
        for botanical in botanicals:
            b.add_edge(name_key, herb_keys[botanical], MAY_REFER_TO)

    for f in FORMULATIONS:
        fkey = b.add_node(FORMULATION, f.name, aliases=list(f.aliases), dosage_form=f.dosage_form)
        for botanical in f.herbs:
            b.add_edge(herb_keys[botanical], fkey, INGREDIENT_OF)
    return b


# ---------------------------------------------------------------------------
# Corpus: classical formulary, document mentions, patents
# ---------------------------------------------------------------------------

_BKK_ENTRY = re.compile(
    r"^(?P<name>[^\n()]+?)\s*\((?P<form>[^)\n]+)\)[ \t]*\n\s*\n"
    r"Category:\s*(?P<cat>[^\n]+)\n"
    r"Main ingredients:\s*(?P<main>[^\n]*)\n"
    r"Ingredients:\s*(?P<ing>[^\n]*)\n"
    r"(?:Reference:\s*(?P<ref>[^\n]*)\n)?"
    r"(?:Indications:\s*(?P<ind>[^\n]*))?",
    re.MULTILINE,
)
_VERNACULAR_BINOMIAL = re.compile(r"([A-Z][\w-]+)\s*\(([A-Z][a-z]+ [a-z][a-z-]+)\)")


def _split_ingredients(main: str) -> list[str]:
    names: list[str] = []
    for part in main.split(","):
        outer = re.sub(r"\([^)]*\)", "", part).strip(" .")
        inner = re.findall(r"\(([^)]*)\)", part)
        if outer:
            names.append(outer)
        names.extend(i.strip() for i in inner if i.strip())
    return names


def parse_classical_formulary(text: str, base: GraphBatch, *, doc_title: str) -> GraphBatch:
    """Formulation -> ingredient edges from the Bhaishajya Kalpana Kosha layout."""
    b = GraphBatch()
    herbs = alias_map(base, (HERB,))
    forms = alias_map(base, (FORMULATION,))

    for m in _BKK_ENTRY.finditer(text):
        name = m.group("name").strip()
        existing = forms.get(normalize(name))
        if existing and len(existing) == 1:
            fkey = next(iter(existing))
            b.add_node(FORMULATION, base.nodes[fkey].name, aliases=[name])
        else:
            fkey = b.add_node(FORMULATION, name)
        b.add_node(
            FORMULATION,
            b.nodes[fkey].name,
            dosage_form=m.group("form").strip(),
            indications=(m.group("ind") or "").strip() or None,
            reference=(m.group("ref") or "").strip() or None,
            source_document=doc_title,
        )
        b.add_edge(fkey, b.add_node(CATEGORY, m.group("cat").strip()), IN_CATEGORY)

        binomials = {
            normalize(v): bn for v, bn in _VERNACULAR_BINOMIAL.findall(m.group("ing") or "")
        }
        for ingredient in _split_ingredients(m.group("main") or ""):
            norm = normalize(ingredient)
            if norm in forms and fkey not in forms[norm]:
                b.add_edge(next(iter(forms[norm])), fkey, INGREDIENT_OF)
                continue
            target = herbs.get(norm)
            if not target and norm in binomials:
                target = herbs.get(normalize(binomials[norm]))
                if not target:
                    target = {b.add_node(HERB, binomials[norm], aliases=[ingredient], confidence=0.85)}
                    herbs[norm] = target
                    herbs[normalize(binomials[norm])] = target
            if target and len(target) == 1:
                hkey = next(iter(target))
                b.add_edge(hkey, fkey, INGREDIENT_OF)
            else:
                b.add_edge(b.add_node(INGREDIENT, ingredient), fkey, INGREDIENT_OF)
    return b


def _load_meta(path: Path) -> dict[str, Any]:
    meta_path = path.with_name(f"{path.stem}.meta.json")
    if not meta_path.exists():
        return {"doc_id": path.stem, "title": path.stem}
    return json.loads(meta_path.read_text(encoding="utf-8"))


def build_corpus_batch(
    corpus_dir: Path,
    base: GraphBatch,
    *,
    max_patents_per_entity: int = 12,
) -> GraphBatch:
    """Scan corpus documents and patent exports for herb / formulation mentions."""
    b = GraphBatch()
    md_files = sorted(corpus_dir.glob("*.md"))

    for path in md_files:
        if "bhaishajya" in path.stem:
            meta = _load_meta(path)
            b.merge(parse_classical_formulary(
                path.read_text(encoding="utf-8"), base, doc_title=meta.get("title") or path.stem
            ))

    vocab = GraphBatch()
    vocab.merge(base)
    vocab.merge(b)
    matcher = Matcher(alias_map(vocab))

    for path in md_files:
        meta = _load_meta(path)
        counts = matcher.counts(path.read_text(encoding="utf-8"))
        if not counts:
            continue
        dkey = b.add_node(
            DOCUMENT,
            meta.get("title") or path.stem,
            ident=meta.get("doc_id") or path.stem,
            source_type=meta.get("source_type"),
            url=meta.get("source_url"),
            jurisdiction=meta.get("jurisdiction"),
        )
        for key, n in counts.items():
            b.add_edge(key, dkey, MENTIONED_IN, count=n)

    per_entity: dict[str, list[tuple[bool, str, dict[str, Any]]]] = defaultdict(list)
    for path in sorted(corpus_dir.glob("*.json")):
        if path.name.endswith(".meta.json"):
            continue
        try:
            records = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.warning("Skipping unreadable corpus file %s", path)
            continue
        if not isinstance(records, list):
            continue
        for rec in records:
            if not isinstance(rec, dict) or not rec.get("publication_number"):
                continue
            title = rec.get("title") or ""
            body = " ".join(filter(None, [title, rec.get("abstract"), rec.get("first_claim")]))
            title_hits = matcher.counts(title)
            for key in matcher.counts(body):
                per_entity[key].append((key in title_hits, rec.get("publication_date") or "", rec))

    for key, hits in per_entity.items():
        hits.sort(key=lambda h: (h[0], h[1]), reverse=True)
        for in_title, _, rec in hits[:max_patents_per_entity]:
            pkey = b.add_node(
                PATENT,
                (rec.get("title") or rec["publication_number"]).strip()[:200],
                ident=rec["publication_number"],
                publication_number=rec["publication_number"],
                url=rec.get("url"),
                publication_date=rec.get("publication_date"),
                jurisdiction=rec.get("jurisdiction"),
                snippet=(rec.get("abstract") or "")[:SNIPPET_CHARS] or None,
            )
            b.add_edge(key, pkey, MENTIONED_IN, in_title=in_title)
    return b


# ---------------------------------------------------------------------------
# Pipeline responses
# ---------------------------------------------------------------------------


def _botanicals(response: Any) -> list[BotanicalResult]:
    items = list(getattr(response, "botanicals", None) or [])
    single = getattr(response, "botanical", None)
    if not items and single is not None:
        items = [single]
    return items


def build_response_batch(
    response: Any,
    *,
    feature: str,
    vocabulary: AliasMap | None = None,
) -> GraphBatch:
    """Product, its resolved herbs / compounds, and the sources that mention them."""
    b = GraphBatch()
    product = b.add_node(
        PRODUCT,
        response.product,
        feature=feature,
        jurisdiction=getattr(response, "jurisdiction", None),
        ingredients=list(getattr(response, "ingredients", None) or []),
    )
    mentions: AliasMap = defaultdict(set)
    for term, keys in (vocabulary or {}).items():
        mentions[term] |= keys

    for r in _botanicals(response):
        if r.status == BotanicalStatus.RESOLVED and r.botanical_name:
            hkey = b.add_node(HERB, r.botanical_name, synonyms=r.synonyms or None)
            b.add_edge(hkey, product, INGREDIENT_OF, input_term=r.input_term)
            for compound in r.phytochemicals:
                b.add_edge(hkey, b.add_node(COMPOUND, compound), CONTAINS)
            for term in (r.botanical_name, r.input_term, *r.synonyms):
                mentions[normalize(term)].add(hkey)
        elif r.input_term:
            nkey = b.add_node(NAME, r.input_term, ambiguous=r.status == BotanicalStatus.AMBIGUOUS)
            b.add_edge(nkey, product, INGREDIENT_OF)
            for c in r.candidates:
                hkey = b.add_node(HERB, c.botanical_name)
                b.add_edge(nkey, hkey, MAY_REFER_TO, confidence=c.confidence)
            mentions[normalize(r.input_term)].add(nkey)

    matcher = Matcher(mentions)
    sources: list[RetrievedSource] = list(getattr(response, "retrieved_sources", None) or [])
    for s in sources:
        skey = b.add_node(
            SOURCE,
            s.title or s.id,
            ident=s.id,
            source_id=s.id,
            source_type=s.source_type,
            section=s.section,
            url=s.source_url,
            jurisdiction=s.jurisdiction,
            snippet=(s.text or "")[:SNIPPET_CHARS] or None,
        )
        b.add_edge(product, skey, CITES)
        for key, n in matcher.counts(f"{s.title}\n{s.text}").items():
            if key not in b.nodes:
                label = key.split(":", 1)[0]
                b.add_node(label, key.split(":", 1)[1])
            b.add_edge(key, skey, MENTIONED_IN, count=n)

    market = getattr(response, "market_feasibility", None)
    for comp in getattr(market, "competitors", None) or []:
        ckey = b.add_node(PRODUCT, comp.name, company=comp.company, feature="competitor")
        b.add_edge(ckey, product, COMPETES_WITH)
    return b
