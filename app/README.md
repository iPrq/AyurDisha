# AyurDisha Backend (`app/`)

FastAPI + LangGraph backend. **Patent Advisor first** (Phases 1–6).

## Run

```powershell
uv sync
uv run uvicorn main:app --reload --port 8000
```

- Docs: http://127.0.0.1:8000/docs  
- Health: http://127.0.0.1:8000/health  
- API: `POST /api/v1/patent-advisor`

## Test

```powershell
uv run pytest tests/ -v
```

## Real retrieval (Qdrant Cloud + BM25)

```powershell
uv run python -m ingest.build_index --recreate   # after adding docs to data/raw/
# then set RETRIEVER_BACKEND=qdrant in .env
```

## Guide

See [`../docs/BACKEND_GUIDE.md`](../docs/BACKEND_GUIDE.md) for the full walkthrough (architecture, `legal_scope` switch, config, extending mocks), and [`../docs/RETRIEVAL_GUIDE.md`](../docs/RETRIEVAL_GUIDE.md) for Qdrant/BM25 ingestion, retrieval and AWS ECS deployment.
