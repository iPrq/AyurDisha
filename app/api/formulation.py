"""Formulation Intelligence FastAPI router — shared formulation context + agent planning."""

from __future__ import annotations

import logging
from typing import Any, Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from api.pdf_upload import read_pdf_upload
from api.streaming import SSE_HEADERS, stream_graph
from config import get_settings
from graph.formulation.clarify import formulation_missing_information, readiness
from graph.formulation.characterize import characterize
from graph.formulation.handoff import ToolHandoff, build_handoff
from graph.formulation.identity import resolve_ingredient
from graph.formulation.intent import decode_request
from graph.formulation.models import (
    UNITS,
    ActionRequest,
    ActionResult,
    AgentPlan,
    ChatRequest,
    ConfirmFormulationAction,
    FormulationContext,
    FormulationGraph,
    FormulationIngredient,
    FormulationSourceType,
    ReadinessResponse,
    ScenarioChange,
    ToolName,
    VersionComparison,
)
from graph.formulation.planner import plan_request
from graph.formulation.scenario import ScenarioResult, build_scenario
from graph.formulation.store import (
    ActionRejected,
    FormulationNotFound,
    VersionConflict,
    get_formulation_store,
    new_id,
)
from graph.formulation.telemetry import log_event, timed
from graph.formulation_graph import (
    build_formulation_graph,
    check_ambiguities_node,
    extract_formulation_node,
    language_normalization_node,
    parse_input_node,
    resolve_botanicals_node,
)
from graph.models import AbsPurpose, EntityType, LegalScope, PdfPageInfo, ResourceSource
from knowledge_graph.factory import get_knowledge_graph
from language.base import LanguageServiceUnavailable
from language.factory import get_language_provider
from llm.provider import get_chat_model
from retrieval.factory import get_retriever

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["formulation"])

_graph = None
_llm_holder: dict[str, Any] = {}


def get_graph():
    global _graph
    if _graph is None:
        settings = get_settings()
        _graph = build_formulation_graph(
            retriever=get_retriever(settings),
            kg=get_knowledge_graph(settings),
            settings=settings,
            language_provider=get_language_provider(settings),
        )
    return _graph


def get_llm():
    if "llm" not in _llm_holder:
        _llm_holder["llm"] = get_chat_model(settings=get_settings())
    return _llm_holder["llm"]


def _resolver():
    settings = get_settings()
    kg = get_knowledge_graph(settings)
    llm = get_llm()

    def _resolve(ing: FormulationIngredient) -> FormulationIngredient:
        return resolve_ingredient(ing, kg=kg, settings=settings, llm=llm)

    return _resolve


def _get(formulation_id: str) -> FormulationContext:
    try:
        return get_formulation_store().get(formulation_id)
    except FormulationNotFound as exc:
        raise HTTPException(status_code=404, detail="Formulation not found (it may have expired).") from exc


# ---------------------------------------------------------------------------
# Wire models
# ---------------------------------------------------------------------------


class IngredientInput(BaseModel):
    user_term: str = Field(min_length=1, max_length=80)
    quantity: float | None = Field(default=None, ge=0)
    unit: str | None = None
    plant_part: str | None = Field(default=None, max_length=60)


class CreateFormulationRequest(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    raw_text: str | None = Field(default=None, max_length=50_000)
    language: str | None = None
    source_type: FormulationSourceType = FormulationSourceType.MANUAL
    ingredients: list[IngredientInput] = Field(default_factory=list, max_length=40)
    dosage_form: str | None = Field(default=None, max_length=60)
    route: str | None = Field(default=None, max_length=60)
    intended_use: str | None = Field(default=None, max_length=200)
    claims: list[str] = Field(default_factory=list, max_length=20)
    target_market: str | None = Field(default=None, max_length=60)
    jurisdiction: str = "india"
    legal_scope: LegalScope = LegalScope.DOMESTIC
    purpose: AbsPurpose | None = None
    entity_type: EntityType | None = None
    resource_source: ResourceSource | None = None


class ExtractionMeta(BaseModel):
    method: str | None = None
    dropped: list[str] = Field(default_factory=list)
    language: str | None = None
    language_method: str | None = None
    pages: list[PdfPageInfo] = Field(default_factory=list)
    total_pages: int | None = None
    ocr_used: bool = False
    truncated: bool = False
    filename: str | None = None


class VersionInfo(BaseModel):
    version: int
    change_summary: str
    action_type: str | None = None
    created_at: Any


class FormulationEnvelope(BaseModel):
    context: FormulationContext
    extraction: ExtractionMeta | None = None
    versions: list[VersionInfo] = Field(default_factory=list)


class AnalyzeResponse(BaseModel):
    context: FormulationContext
    graph: FormulationGraph
    suggested_actions: list[dict[str, Any]] = Field(default_factory=list)
    escalation_reasons: list[str] = Field(default_factory=list)


class ReadinessRequest(BaseModel):
    tool: ToolName


class ScenarioRequest(BaseModel):
    changes: list[ScenarioChange] = Field(min_length=1)


def _versions(formulation_id: str) -> list[VersionInfo]:
    return [
        VersionInfo(version=v.version, change_summary=v.change_summary, action_type=v.action_type, created_at=v.created_at)
        for v in get_formulation_store().history(formulation_id)
    ]


def _unit(value: str | None) -> str | None:
    u = (value or "").strip().lower() or None
    return u if u in UNITS else None


def _prepare(ctx: FormulationContext, raw_text: str | None, language: str | None) -> tuple[FormulationContext, ExtractionMeta]:
    """Reuses the workflow's own nodes for the extraction half (no retrieval / verification)."""
    settings = get_settings()
    llm = get_llm()
    state: dict[str, Any] = {"formulation": ctx, "raw_text": raw_text or "", "language": language or "auto"}
    for step in (
        parse_input_node,
        lambda s: language_normalization_node(s, provider=get_language_provider(settings)),
        lambda s: extract_formulation_node(s, llm=llm, settings=settings),
        lambda s: resolve_botanicals_node(s, kg=get_knowledge_graph(settings), settings=settings, llm=llm),
        check_ambiguities_node,
    ):
        update = step(state)
        state.update({k: v for k, v in update.items() if k != "escalation_reasons"})
    out: FormulationContext = state["formulation"]
    out.formulation_characteristics = characterize(out)
    out.missing_information = formulation_missing_information(out)
    return out, ExtractionMeta(
        method=state.get("extraction_method"),
        dropped=state.get("extraction_dropped") or [],
        language=state.get("language"),
        language_method=state.get("language_method"),
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/formulation", response_model=FormulationEnvelope)
def create_formulation(request: CreateFormulationRequest) -> FormulationEnvelope:
    """Create a formulation from structured fields and/or pasted text (extraction + normalization)."""
    with timed("formulation_create", workflow="formulation") as log:
        ctx = FormulationContext(
            formulation_id=new_id("form"),
            name=request.name,
            raw_text=request.raw_text,
            source_type=request.source_type,
            dosage_form=(request.dosage_form or "").strip().lower() or None,
            route=request.route,
            intended_use=request.intended_use,
            product_claims=[c for c in request.claims if c.strip()],
            target_market=request.target_market,
            jurisdiction=request.jurisdiction,
            legal_scope=request.legal_scope,
            purpose=request.purpose,
            entity_type=request.entity_type,
            resource_source=request.resource_source,
        )
        seen: set[str] = set()
        for item in request.ingredients:
            key = item.user_term.strip().lower()
            if key in seen:
                continue
            seen.add(key)
            ctx.ingredients.append(
                FormulationIngredient(
                    id=new_id("ing"),
                    user_term=item.user_term.strip(),
                    quantity=item.quantity,
                    unit=_unit(item.unit),
                    plant_part=item.plant_part,
                )
            )
        try:
            ctx, meta = _prepare(ctx, request.raw_text, request.language)
        except Exception as exc:  # noqa: BLE001
            logger.exception("formulation create failed")
            raise HTTPException(status_code=500, detail=str(exc)[:300]) from exc
        stored = get_formulation_store().create(ctx, summary="Created formulation")
        log.update(extraction_method=meta.method, ingredient_count=len(stored.ingredients), language=meta.language)
        return FormulationEnvelope(context=stored, extraction=meta, versions=_versions(stored.formulation_id))


@router.post("/formulation/upload", response_model=FormulationEnvelope)
def upload_formulation(
    file: UploadFile = File(...),
    kind: Literal["formulation", "patent"] = Form("formulation"),
) -> FormulationEnvelope:
    """Extract a formulation from a PDF (text layer first, OCR fallback). Not indexed into the corpus."""
    settings = get_settings()
    with timed("formulation_upload", workflow="formulation") as log:
        extraction = read_pdf_upload(file, settings)
        source_type = FormulationSourceType.PATENT_PDF if kind == "patent" else FormulationSourceType.PDF
        ctx = FormulationContext(
            formulation_id=new_id("form"),
            source_type=source_type,
            source_document_id=new_id("doc"),
            raw_text=extraction.text[: settings.patent_doc_context_chars],
        )
        try:
            ctx, meta = _prepare(ctx, extraction.text, "auto")
        except Exception as exc:  # noqa: BLE001
            logger.exception("formulation upload extraction failed")
            raise HTTPException(status_code=500, detail=str(exc)[:300]) from exc
        meta.pages = [PdfPageInfo(**p.model_dump()) for p in extraction.pages]
        meta.total_pages = extraction.total_pages
        meta.ocr_used = extraction.ocr_used
        meta.truncated = extraction.truncated
        meta.filename = file.filename
        stored = get_formulation_store().create(ctx, summary=f"Extracted from {kind} PDF")
        log.update(
            extraction_method=f"{meta.method}{'+ocr' if extraction.ocr_used else ''}",
            ingredient_count=len(stored.ingredients),
        )
        return FormulationEnvelope(context=stored, extraction=meta, versions=_versions(stored.formulation_id))


@router.get("/formulation/{formulation_id}", response_model=FormulationEnvelope)
def get_formulation(formulation_id: str) -> FormulationEnvelope:
    ctx = _get(formulation_id)
    return FormulationEnvelope(context=ctx, versions=_versions(formulation_id))


@router.post("/formulation/{formulation_id}/actions", response_model=ActionResult)
def apply_formulation_action(formulation_id: str, request: ActionRequest) -> ActionResult:
    """Execute one validated state action (creates a new version)."""
    with timed("agent_action", action_type=request.action.type) as log:
        _get(formulation_id)
        try:
            result = get_formulation_store().apply_action(
                formulation_id, request.action, base_version=request.base_version, resolver=_resolver()
            )
        except ActionRejected as exc:
            log["status"] = "rejected"
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except VersionConflict as exc:
            log["status"] = "conflict"
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        ctx = result.context
        ctx.formulation_characteristics = characterize(ctx)
        ctx.missing_information = formulation_missing_information(ctx)
        get_formulation_store().update_derived(ctx)
        result.context = get_formulation_store().get(formulation_id)
        return result


@router.post("/formulation/{formulation_id}/confirm", response_model=ActionResult)
def confirm_formulation(formulation_id: str) -> ActionResult:
    return apply_formulation_action(
        formulation_id, ActionRequest(action=ConfirmFormulationAction())
    )


def _analyze_response(formulation_id: str, state: dict[str, Any]) -> AnalyzeResponse:
    out: FormulationContext = state["formulation"]
    get_formulation_store().update_derived(out)
    graph: FormulationGraph = state["graph"]
    log_event(
        "formulation_analyze",
        workflow="formulation",
        ingredient_count=len(out.ingredients),
        verification=graph.verification.outcome.value if graph.verification else "not_verified",
        source_count=len(graph.evidence),
    )
    return AnalyzeResponse(
        context=get_formulation_store().get(formulation_id),
        graph=graph,
        suggested_actions=state.get("suggested_actions") or [],
        escalation_reasons=list(state.get("escalation_reasons") or []),
    )


def _analyze_initial(ctx: FormulationContext) -> dict[str, Any]:
    return {"formulation": ctx, "raw_text": "", "escalation_reasons": []}


@router.post("/formulation/{formulation_id}/analyze", response_model=AnalyzeResponse)
def analyze_formulation(formulation_id: str) -> AnalyzeResponse:
    """Run the Formulation Intelligence graph: retrieval, characterization, map, verification."""
    ctx = _get(formulation_id)
    try:
        state = get_graph().invoke(_analyze_initial(ctx))
    except Exception as exc:  # noqa: BLE001
        logger.exception("formulation analyze failed")
        raise HTTPException(status_code=500, detail=str(exc)[:300]) from exc
    return _analyze_response(formulation_id, state)


@router.post("/formulation/{formulation_id}/analyze/stream")
def analyze_formulation_stream(formulation_id: str) -> StreamingResponse:
    """Same as ``/analyze`` but streams real LangGraph node progress as server-sent events."""
    ctx = _get(formulation_id)
    return StreamingResponse(
        stream_graph(
            get_graph(),
            _analyze_initial(ctx),
            workflow="formulation",
            to_response=lambda state: _analyze_response(formulation_id, state),
        ),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@router.post("/formulation/{formulation_id}/readiness", response_model=ReadinessResponse)
def formulation_readiness(formulation_id: str, request: ReadinessRequest) -> ReadinessResponse:
    return readiness(_get(formulation_id), request.tool)


@router.get("/formulation/{formulation_id}/handoff/{tool}", response_model=ToolHandoff)
def formulation_handoff(formulation_id: str, tool: ToolName) -> ToolHandoff:
    handoff = build_handoff(_get(formulation_id), tool)
    log_event("formulation_handoff_built", workflow=tool, ingredient_count=handoff.summary.get("ingredient_count"))
    return handoff


@router.post("/formulation/{formulation_id}/scenario", response_model=ScenarioResult)
def formulation_scenario(formulation_id: str, request: ScenarioRequest) -> ScenarioResult:
    try:
        return build_scenario(_get(formulation_id), request.changes)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/formulation/{formulation_id}/compare", response_model=VersionComparison)
def formulation_compare(
    formulation_id: str, from_version: int | None = None, to_version: int | None = None
) -> VersionComparison:
    _get(formulation_id)
    try:
        return get_formulation_store().compare(formulation_id, from_version, to_version)
    except FormulationNotFound as exc:
        raise HTTPException(status_code=404, detail="Version not found.") from exc


@router.post("/formulation/chat", response_model=AgentPlan)
def formulation_chat(request: ChatRequest) -> AgentPlan:
    """Decode a natural-language request into a validated, state-aware action plan (nothing executes here)."""
    ctx = _get(request.formulation_id) if request.formulation_id else None
    provider = get_language_provider()
    original = request.original_text or request.message
    with timed("agent_plan", provider=provider.name) as log:
        requested = (request.language or "auto").lower()
        detected = provider.detect_language(request.message)
        source = detected.language if requested in ("", "auto") else requested
        normalized = request.message
        translation_note = None
        language_method = detected.method
        if source != "en" and detected.language != "en":
            try:
                normalized = provider.translate(request.message, source_language=source, target_language="en").text
                language_method = f"{provider.name}_translation"
            except LanguageServiceUnavailable as exc:
                translation_note = f"Translation unavailable ({exc}); interpreted the original text."
                language_method = "untranslated"
        decoded = decode_request(normalized, ctx, llm=get_llm())
        plan = plan_request(decoded.request, ctx, text=normalized, current_route=request.current_route)
        plan.decoder = decoded.decoder
        plan.original_text = original
        plan.normalized_text = normalized
        plan.language = source
        plan.language_method = language_method
        plan.translation_note = translation_note
        if source != "en" and plan.message:
            try:
                plan.message_localized = provider.translate(
                    plan.message, source_language="en", target_language=source
                ).text
            except LanguageServiceUnavailable:
                plan.message_localized = None
        log.update(
            intent=plan.intent.value,
            intents=",".join(i.value for i in plan.intents),
            decoder=plan.decoder,
            language=source,
            language_method=language_method,
            action_count=len(plan.actions),
        )
        return plan
