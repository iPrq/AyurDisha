"""AyurDisha FastAPI application — Formulation Intelligence, Product Review, Patent Advisor, NBA / ABS."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.formulation import get_graph as get_formulation_graph
from api.formulation import router as formulation_router
from api.knowledge_graph import router as knowledge_graph_router
from api.language import router as language_router
from api.nba_abs import get_graph as get_nba_abs_graph
from api.nba_abs import router as nba_abs_router
from api.patent_advisor import get_graph
from api.patent_advisor import router as patent_advisor_router
from api.product_review import get_graph as get_product_review_graph
from api.product_review import router as product_review_router
from config import get_settings
from knowledge_graph.service import seed_in_background

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Non-mock backends are built eagerly so misconfiguration fails at startup.
    settings = get_settings()
    seed_in_background(settings)
    if settings.retriever_backend != "mock":
        get_graph()
        get_nba_abs_graph()
        get_formulation_graph()
    if settings.retriever_backend != "mock" or settings.web_search_backend != "mock":
        get_product_review_graph()
    yield


app = FastAPI(
    title="AyurDisha",
    description=(
        "Decision-support backend for Ayurvedic product review, IP guidance, and "
        "NBA / ABS benefit-sharing. Not legal advice. "
        "Unsupported claims are rejected or escalated."
    ),
    version="0.2.0",
    lifespan=lifespan,
)

app.include_router(product_review_router)
app.include_router(patent_advisor_router)
app.include_router(nba_abs_router)
app.include_router(knowledge_graph_router)
app.include_router(formulation_router)
app.include_router(language_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
