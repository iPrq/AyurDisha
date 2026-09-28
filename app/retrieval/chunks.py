"""Canonical chunk model shared by ingestion, Qdrant payloads, and BM25."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field

from graph.models import LegalScope, RetrievedSource

SOURCE_TYPES = (
    "statute", "guideline", "patent", "comparative_ip", "regulation", "case_law", "prior_art"
)


class CanonicalChunk(BaseModel):
    """One indexed unit. Payload fields reconstruct a RetrievedSource on their own."""

    id: str
    title: str
    text: str
    section: str | None = None
    source_type: str
    source_url: str | None = None
    effective_date: str | None = None
    jurisdiction: str | None = None
    legal_scope: LegalScope | None = None
    is_fixture: bool = Field(default=False)

    @property
    def point_id(self) -> str:
        """Deterministic Qdrant point ID (Qdrant requires UUID or int IDs)."""
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"ayurdisha:{self.id}"))

    def index_text(self) -> str:
        """Text used for both embeddings and BM25 so both see the same content."""
        parts = [self.title]
        if self.section:
            parts.append(f"Section {self.section}")
        parts.append(self.text)
        return "\n".join(parts)

    def to_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "CanonicalChunk":
        return cls.model_validate(payload)

    def to_retrieved_source(self, score: float) -> RetrievedSource:
        return RetrievedSource(
            id=self.id,
            title=self.title,
            text=self.text,
            section=self.section,
            source_type=self.source_type,
            source_url=self.source_url,
            effective_date=self.effective_date,
            retrieval_score=float(score),
            jurisdiction=self.jurisdiction,
            legal_scope=self.legal_scope,
            is_fixture=self.is_fixture,
        )
