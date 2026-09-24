"""AyurDisha FastAPI application — Patent Advisor first."""

from __future__ import annotations

from fastapi import FastAPI

from api.patent_advisor import router as patent_advisor_router

app = FastAPI(
    title="AyurDisha",
    description=(
        "Decision-support backend for Ayurvedic IP guidance. "
        "Not legal advice. Unsupported claims are rejected or escalated."
    ),
    version="0.1.0",
)

app.include_router(patent_advisor_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
