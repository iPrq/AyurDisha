"""Fixture-backed mock retrieval (not connected to Qdrant)."""

from __future__ import annotations

from graph.models import LegalScope, RetrievedSource
from retrieval.base import filter_sources


# All entries are TEST FIXTURES — not government or live corpus data.
_FIXTURES: list[RetrievedSource] = [
    RetrievedSource(
        id="fixture-in-s3d",
        title="[TEST FIXTURE] Indian Patents Act — Section 3(d) summary",
        text=(
            "[TEST FIXTURE — NOT OFFICIAL TEXT] Section 3(d) concerns the mere discovery "
            "of a new form of a known substance which does not result in the enhancement "
            "of the known efficacy of that substance, and the mere discovery of any new "
            "property or new use for a known substance."
        ),
        section="3(d)",
        source_type="statute_fixture",
        source_url=None,
        effective_date="fixture",
        retrieval_score=0.92,
        jurisdiction="india",
        legal_scope=LegalScope.DOMESTIC,
        is_fixture=True,
    ),
    RetrievedSource(
        id="fixture-in-s3e",
        title="[TEST FIXTURE] Indian Patents Act — Section 3(e) summary",
        text=(
            "[TEST FIXTURE — NOT OFFICIAL TEXT] Section 3(e) excludes a substance obtained "
            "by a mere admixture resulting only in the aggregation of the properties of "
            "the components thereof, or a process for producing such substance."
        ),
        section="3(e)",
        source_type="statute_fixture",
        source_url=None,
        effective_date="fixture",
        retrieval_score=0.90,
        jurisdiction="india",
        legal_scope=LegalScope.DOMESTIC,
        is_fixture=True,
    ),
    RetrievedSource(
        id="fixture-in-s3p",
        title="[TEST FIXTURE] Indian Patents Act — Section 3(p) summary",
        text=(
            "[TEST FIXTURE — NOT OFFICIAL TEXT] Section 3(p) excludes an invention which, "
            "in effect, is traditional knowledge or which is an aggregation or duplication "
            "of known properties of traditionally known component or components."
        ),
        section="3(p)",
        source_type="statute_fixture",
        source_url=None,
        effective_date="fixture",
        retrieval_score=0.91,
        jurisdiction="india",
        legal_scope=LegalScope.DOMESTIC,
        is_fixture=True,
    ),
    RetrievedSource(
        id="fixture-in-prior-art",
        title="[TEST FIXTURE] Sample prior-art note — Withania formulations",
        text=(
            "[TEST FIXTURE] Prior disclosures discuss Withania somnifera root extracts "
            "used in traditional preparations. This fixture is for retrieval testing only."
        ),
        section=None,
        source_type="prior_art_fixture",
        source_url=None,
        effective_date="fixture",
        retrieval_score=0.75,
        jurisdiction="india",
        legal_scope=LegalScope.DOMESTIC,
        is_fixture=True,
    ),
    RetrievedSource(
        id="fixture-in-ip-routes",
        title="[TEST FIXTURE] Domestic IP pathway overview",
        text=(
            "[TEST FIXTURE] Depending on subject matter, applicants may consider patent, "
            "trademark, design, or trade secret pathways. This is decision-support fixture "
            "text only — not legal advice."
        ),
        section=None,
        source_type="guidance_fixture",
        source_url=None,
        effective_date="fixture",
        retrieval_score=0.70,
        jurisdiction="india",
        legal_scope=LegalScope.DOMESTIC,
        is_fixture=True,
    ),
    RetrievedSource(
        id="fixture-intl-trips",
        title="[TEST FIXTURE] Comparative IP — TRIPS-oriented note",
        text=(
            "[TEST FIXTURE — NOT OFFICIAL TEXT] Comparative international IP materials may "
            "discuss patentable subject matter standards under TRIPS-oriented frameworks. "
            "This fixture exists only to test legal_scope=international filtering."
        ),
        section=None,
        source_type="comparative_ip_fixture",
        source_url=None,
        effective_date="fixture",
        retrieval_score=0.80,
        jurisdiction="wipo",
        legal_scope=LegalScope.INTERNATIONAL,
        is_fixture=True,
    ),
    RetrievedSource(
        id="fixture-intl-epo-note",
        title="[TEST FIXTURE] Comparative IP — EPO-style subject-matter note",
        text=(
            "[TEST FIXTURE — NOT OFFICIAL TEXT] Some jurisdictions apply distinct exclusions "
            "for plant varieties, methods of treatment, or traditional knowledge analogues. "
            "Cite only retrieved comparative fixtures; never invent foreign statutes."
        ),
        section=None,
        source_type="comparative_ip_fixture",
        source_url=None,
        effective_date="fixture",
        retrieval_score=0.72,
        jurisdiction="epo",
        legal_scope=LegalScope.INTERNATIONAL,
        is_fixture=True,
    ),
    # --- Product regulation (Product Review legal compliance) ---
    RetrievedSource(
        id="fixture-in-reg-dca-asu",
        title="[TEST FIXTURE] Drugs and Cosmetics Act — Ayurvedic drug licensing",
        text=(
            "[TEST FIXTURE — NOT OFFICIAL TEXT] Ayurvedic, Siddha and Unani drugs are "
            "regulated under the Drugs and Cosmetics Act, 1940 and the Drugs Rules, 1945. "
            "Manufacture for sale requires a licence from the State Licensing Authority. "
            "Ayurvedic proprietary medicines require evidence of safety and effectiveness "
            "for licensing (Rule 158B)."
        ),
        section="Rule 158B",
        source_type="regulation_fixture",
        source_url=None,
        effective_date="fixture",
        retrieval_score=0.88,
        jurisdiction="india",
        legal_scope=LegalScope.DOMESTIC,
        is_fixture=True,
    ),
    RetrievedSource(
        id="fixture-in-reg-gmp",
        title="[TEST FIXTURE] Schedule T — GMP for ASU manufacturing",
        text=(
            "[TEST FIXTURE — NOT OFFICIAL TEXT] Schedule T to the Drugs Rules prescribes "
            "Good Manufacturing Practices for Ayurvedic, Siddha and Unani manufacturing "
            "units, including premises, raw material testing and record keeping."
        ),
        section="Schedule T",
        source_type="regulation_fixture",
        source_url=None,
        effective_date="fixture",
        retrieval_score=0.82,
        jurisdiction="india",
        legal_scope=LegalScope.DOMESTIC,
        is_fixture=True,
    ),
    RetrievedSource(
        id="fixture-in-reg-fssai",
        title="[TEST FIXTURE] FSSAI — botanical health supplements and Ayurveda Aahara",
        text=(
            "[TEST FIXTURE — NOT OFFICIAL TEXT] Botanical products marketed as foods may "
            "fall under the Food Safety and Standards (Health Supplements, Nutraceuticals "
            "...) Regulations, 2016 or the Food Safety and Standards (Ayurveda Aahara) "
            "Regulations, 2022, rather than drug licensing."
        ),
        section=None,
        source_type="regulation_fixture",
        source_url=None,
        effective_date="fixture",
        retrieval_score=0.80,
        jurisdiction="india",
        legal_scope=LegalScope.DOMESTIC,
        is_fixture=True,
    ),
    RetrievedSource(
        id="fixture-in-reg-dmr",
        title="[TEST FIXTURE] Drugs and Magic Remedies Act — advertising claims",
        text=(
            "[TEST FIXTURE — NOT OFFICIAL TEXT] The Drugs and Magic Remedies "
            "(Objectionable Advertisements) Act, 1954 restricts advertisements claiming "
            "to treat listed diseases and conditions."
        ),
        section=None,
        source_type="regulation_fixture",
        source_url=None,
        effective_date="fixture",
        retrieval_score=0.78,
        jurisdiction="india",
        legal_scope=LegalScope.DOMESTIC,
        is_fixture=True,
    ),
    RetrievedSource(
        id="fixture-intl-reg-thmp",
        title="[TEST FIXTURE] Comparative regulation — traditional herbal medicinal products",
        text=(
            "[TEST FIXTURE — NOT OFFICIAL TEXT] Some foreign markets offer a simplified "
            "registration route for traditional herbal medicinal products based on "
            "evidence of long-standing use. Cite only retrieved comparative sources."
        ),
        section=None,
        source_type="regulation_fixture",
        source_url=None,
        effective_date="fixture",
        retrieval_score=0.76,
        jurisdiction="eu",
        legal_scope=LegalScope.INTERNATIONAL,
        is_fixture=True,
    ),
    # --- Access & Benefit Sharing (NBA / ABS) ---
    RetrievedSource(
        id="fixture-in-abs-bd-act",
        title="[TEST FIXTURE] Biological Diversity Act — access and approvals",
        text=(
            "[TEST FIXTURE — NOT OFFICIAL TEXT] Under the Biological Diversity Act, 2002 "
            "(as amended in 2023), foreign entities require prior approval of the "
            "National Biodiversity Authority (NBA) to obtain biological resources "
            "occurring in India for research or commercial utilization. Indian entities "
            "give prior intimation to the State Biodiversity Board (SBB) for commercial "
            "utilization. Codified traditional knowledge and cultivated medicinal plants "
            "(other than those notified) are exempted from certain provisions."
        ),
        section=None,
        source_type="regulation_fixture",
        source_url=None,
        effective_date="fixture",
        retrieval_score=0.87,
        jurisdiction="india",
        legal_scope=LegalScope.DOMESTIC,
        is_fixture=True,
    ),
    RetrievedSource(
        id="fixture-in-abs-rates",
        title="[TEST FIXTURE] ABS benefit-sharing rates on commercial utilization",
        text=(
            "[TEST FIXTURE — NOT OFFICIAL TEXT; modelled on the 2014 ABS Guidelines, "
            "which may be superseded — verify against currently notified regulations] "
            "Where biological resources are accessed for commercial utilization, benefit "
            "sharing is payable on the annual gross ex-factory sale of the product: "
            "up to Rs 1 crore: 0.1 per cent; above Rs 1 crore and up to Rs 3 crore: "
            "0.2 per cent; above Rs 3 crore: 0.5 per cent."
        ),
        section=None,
        source_type="regulation_fixture",
        source_url=None,
        effective_date="fixture",
        retrieval_score=0.86,
        jurisdiction="india",
        legal_scope=LegalScope.DOMESTIC,
        is_fixture=True,
    ),
]


def _score_query(source: RetrievedSource, query: str) -> float:
    """Simple lexical boost on top of fixture retrieval_score."""
    q = query.lower()
    blob = f"{source.title} {source.text} {source.section or ''}".lower()
    bonus = 0.0
    for token in q.split():
        if len(token) > 2 and token in blob:
            bonus += 0.02
    return min(1.0, source.retrieval_score + bonus)


class MockLegalRetriever:
    """In-memory retriever with jurisdiction / legal_scope filters."""

    def __init__(self, corpus: list[RetrievedSource] | None = None) -> None:
        self._corpus = list(corpus) if corpus is not None else list(_FIXTURES)

    def retrieve(
        self,
        query: str,
        *,
        jurisdiction: str = "india",
        legal_scope: LegalScope | str = LegalScope.DOMESTIC,
        top_k: int = 8,
        source_types: list[str] | None = None,
    ) -> list[RetrievedSource]:
        filtered = filter_sources(
            self._corpus,
            jurisdiction=jurisdiction,
            legal_scope=legal_scope,
        )
        if source_types:
            # Fixture types carry a suffix, e.g. "statute_fixture" matches "statute".
            wanted = {t.strip().lower() for t in source_types}
            filtered = [
                s
                for s in filtered
                if s.source_type.lower() in wanted
                or s.source_type.lower().removesuffix("_fixture") in wanted
            ]
        ranked = sorted(
            filtered,
            key=lambda s: _score_query(s, query or ""),
            reverse=True,
        )
        return ranked[:top_k]


def get_mock_retriever() -> MockLegalRetriever:
    return MockLegalRetriever()


def get_fixture_corpus() -> list[RetrievedSource]:
    """Expose fixture list for tests."""
    return list(_FIXTURES)
