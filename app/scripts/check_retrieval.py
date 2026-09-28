"""Read-only check of the real index (no writes). Run from app/ with RETRIEVER_BACKEND=qdrant:

    uv run python scripts/check_retrieval.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import get_settings  # noqa: E402
from graph.models import SUPPORTED_SECTION3_CLAUSES  # noqa: E402
from graph.patent_advisor.retrieval import legal_patent_retrieval_node  # noqa: E402
from retrieval.factory import get_retriever  # noqa: E402

QUERIES = [
    "Section 3(d) known substance efficacy",
    "Section 3(k)",
    "traditional knowledge",
    "prior approval National Biodiversity Authority patent",
]


def main() -> int:
    s = get_settings()
    if s.retriever_backend != "qdrant":
        print(f"RETRIEVER_BACKEND is '{s.retriever_backend}'; set RETRIEVER_BACKEND=qdrant in .env first.")
        return 2
    r = get_retriever(s)
    for q in QUERIES:
        print(q)
        for h in r.retrieve(q, jurisdiction="india", legal_scope="domestic", top_k=3):
            print(f"    {h.retrieval_score:.4f}  {h.id} | {h.section}")
    state = {
        "product": "Ashwagandha capsule", "ingredients": ["Ashwagandha"], "language": "en",
        "jurisdiction": "india", "legal_scope": "domestic", "botanical_name": "Withania somnifera",
    }
    sources = legal_patent_retrieval_node(state, retriever=r, settings=s)["retrieved_sources"]
    got = sorted({x.section for x in sources if (x.section or "").startswith("3(")})
    missing = [c for c in SUPPORTED_SECTION3_CLAUSES if c not in got]
    print("\nSection 3 clauses retrieved:", got)
    print("RESULT:", "OK - all 15 clauses, no 3(g)" if not missing and "3(g)" not in got
          else f"PROBLEM - missing {missing}")
    return 0 if not missing else 1


if __name__ == "__main__":
    sys.exit(main())
