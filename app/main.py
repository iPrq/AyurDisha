"""AyurDisha FastAPI application — Patent Advisor first."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.patent_advisor import get_graph
from api.patent_advisor import router as patent_advisor_router
from config import get_settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Non-mock backends are built eagerly so misconfiguration fails at startup.
    if get_settings().retriever_backend != "mock":
        get_graph()
    yield


app = FastAPI(
    title="AyurDisha",
    description=(
        "Decision-support backend for Ayurvedic IP guidance. "
        "Not legal advice. Unsupported claims are rejected or escalated."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(patent_advisor_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
