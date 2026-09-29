"""Formulation Intelligence models — shared formulation context, typed graph, agent actions."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, computed_field

from graph.models import (
    AbsPurpose,
    BotanicalCandidate,
    BotanicalResult,
    EntityType,
    EvidenceKind,
    LegalScope,
    ResourceSource,
    RetrievedSource,
    VerificationResult,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Formulation context
# ---------------------------------------------------------------------------


class IdentityStatus(str, Enum):
    CONFIRMED = "confirmed"
    PROBABLE = "probable"
    AMBIGUOUS = "ambiguous"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    HUMAN_REVIEW = "human_review"


class FormulationSourceType(str, Enum):
    MANUAL = "manual"
    TEXT = "text"
    PDF = "pdf"
    PATENT_PDF = "patent_pdf"
    CHAT = "chat"
    VOICE = "voice"


Unit = Literal["mg", "g", "kg", "mcg", "ml", "l", "%", "iu", "part", "tablet", "capsule"]
UNITS: tuple[str, ...] = ("mg", "g", "kg", "mcg", "ml", "l", "%", "iu", "part", "tablet", "capsule")

IngredientType = Literal["botanical", "mineral", "animal", "excipient", "unknown"]


class FormulationIngredient(BaseModel):
    id: str
    user_term: str
    normalized_name: str | None = None
    botanical_name: str | None = None
    synonyms: list[str] = Field(default_factory=list)
    plant_part: str | None = None
    quantity: float | None = Field(default=None, ge=0)
    unit: str | None = None
    ingredient_type: IngredientType = "unknown"
    identity_status: IdentityStatus = IdentityStatus.INSUFFICIENT_EVIDENCE
    evidence_ids: list[str] = Field(default_factory=list)
    source_text: str | None = None
    candidates: list[BotanicalCandidate] = Field(
        default_factory=list, description="Populated when identity is ambiguous — never auto-picked"
    )
    identity_notes: str | None = None
    resolved_by_user: bool = False
    botanical: BotanicalResult | None = Field(
        default=None, description="Raw result from the shared botanical normalizer"
    )


class FormulationCharacteristic(BaseModel):
    key: str
    label: str
    value: str
    origin: Literal["user", "derived", "source"] = "derived"
    evidence_kind: EvidenceKind | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    status: IdentityStatus = IdentityStatus.CONFIRMED


class FormulationContext(BaseModel):
    formulation_id: str
    name: str | None = None
    raw_text: str | None = Field(default=None, description="Pasted / extracted text (never evidence)")
    original_user_text: str | None = Field(
        default=None, description="User's original wording (any language) kept for traceability"
    )
    language: str | None = None
    source_type: FormulationSourceType = FormulationSourceType.MANUAL
    source_document_id: str | None = None
    ingredients: list[FormulationIngredient] = Field(default_factory=list)
    dosage_form: str | None = None
    route: str | None = None
    intended_use: str | None = None
    product_claims: list[str] = Field(default_factory=list)
    target_market: str | None = None
    jurisdiction: str = "india"
    legal_scope: LegalScope = LegalScope.DOMESTIC
    entity_type: EntityType | None = None
    purpose: AbsPurpose | None = None
    resource_source: ResourceSource | None = None
    formulation_characteristics: list[FormulationCharacteristic] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    confirmed: bool = False
    last_referenced_ingredient: str | None = Field(
        default=None, description="Ingredient id that pronouns like 'it' resolve to"
    )
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    version: int = 1

    @computed_field  # type: ignore[prop-decorator]
    @property
    def botanical_identities(self) -> list[str]:
        return [i.botanical_name for i in self.ingredients if i.botanical_name]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def plant_parts(self) -> list[str]:
        return [i.plant_part for i in self.ingredients if i.plant_part]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def biological_resources(self) -> list[str]:
        """Resolved botanical identities only — ambiguous / unknown terms are not listed."""
        return [
            i.botanical_name
            for i in self.ingredients
            if i.botanical_name
            and i.identity_status in (IdentityStatus.CONFIRMED, IdentityStatus.PROBABLE)
        ]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def ambiguities(self) -> list[str]:
        return [i.id for i in self.ingredients if i.identity_status == IdentityStatus.AMBIGUOUS]

    def find_ingredient(self, term_or_id: str) -> FormulationIngredient | None:
        key = (term_or_id or "").strip().lower()
        if not key:
            return None
        for ing in self.ingredients:
            names = {ing.id.lower(), ing.user_term.lower()}
            if ing.normalized_name:
                names.add(ing.normalized_name.lower())
            if ing.botanical_name:
                names.add(ing.botanical_name.lower())
            names.update(s.lower() for s in ing.synonyms)
            if key in names:
                return ing
        return None


class FormulationVersion(BaseModel):
    version: int
    change_summary: str
    action_type: str | None = None
    snapshot: FormulationContext
    created_at: datetime = Field(default_factory=utcnow)


class VersionComparison(BaseModel):
    formulation_id: str
    from_version: int
    to_version: int
    changes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Structured formulation graph (backend-generated, never LLM-invented)
# ---------------------------------------------------------------------------


class FGNodeType(str, Enum):
    FORMULATION = "formulation"
    COMPOSITION = "composition"
    INGREDIENT = "ingredient"
    BOTANICAL_IDENTITY = "botanical_identity"
    PLANT_PART = "plant_part"
    CHEMICAL = "chemical"
    DOSAGE_FORM = "dosage_form"
    ROUTE = "route"
    INTENDED_USE = "intended_use"
    CHARACTERISTIC = "characteristic"
    CLASSIFICATION = "classification"
    REGULATORY = "regulatory"
    PATENT = "patent"
    PRIOR_ART = "prior_art"
    TRADITIONAL_KNOWLEDGE = "traditional_knowledge"
    BIOLOGICAL_RESOURCE = "biological_resource"
    ABS = "abs"
    EVIDENCE = "evidence"
    ACTION = "action"
    UNCERTAINTY = "uncertainty"


class FGEdgeType(str, Enum):
    CONTAINS = "contains"
    DERIVED_FROM = "derived_from"
    IDENTIFIED_AS = "identified_as"
    PART_OF = "part_of"
    USED_FOR = "used_for"
    CLASSIFIED_AS = "classified_as"
    MAY_TRIGGER = "may_trigger"
    RELEVANT_TO = "relevant_to"
    SUPPORTED_BY = "supported_by"
    CONTRADICTED_BY = "contradicted_by"
    REQUIRES_REVIEW = "requires_review"
    LEADS_TO = "leads_to"


class WhyItMatters(BaseModel):
    facts: list[str] = Field(default_factory=list, description="FACT FROM SOURCE (verified)")
    interpretation: list[str] = Field(default_factory=list, description="MODEL INTERPRETATION")
    uncertainty: list[str] = Field(default_factory=list, description="UNCERTAINTY")


class FGNode(BaseModel):
    id: str
    type: FGNodeType
    label: str
    sublabel: str | None = None
    status: IdentityStatus | None = None
    layer: int = 0
    branch: Literal["core", "regulatory", "patent", "abs", "evidence", "action"] = "core"
    evidence_ids: list[str] = Field(default_factory=list)
    evidence_kind: EvidenceKind | None = None
    why_it_matters: WhyItMatters | None = None
    ref: str | None = Field(default=None, description="Ingredient id / source id / action type")


class FGEdge(BaseModel):
    id: str
    source: str
    target: str
    type: FGEdgeType
    status: IdentityStatus | None = None
    evidence_ids: list[str] = Field(default_factory=list)


class EvidenceItem(BaseModel):
    """A retrieved source plus the verifier's verdict for the graph claims that cite it."""

    source: RetrievedSource
    branch: str
    supports: list[str] = Field(default_factory=list, description="Verified graph claims")
    verifier_status: Literal["SUPPORTED", "PARTIALLY_SUPPORTED", "UNSUPPORTED", "NOT_VERIFIED"] = (
        "NOT_VERIFIED"
    )


class FormulationGraph(BaseModel):
    formulation_id: str
    version: int
    nodes: list[FGNode] = Field(default_factory=list)
    edges: list[FGEdge] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    verification: VerificationResult | None = None
    generated_at: datetime = Field(default_factory=utcnow)
    disclaimer: str = (
        "Formulation map is decision support generated from structured data and retrieved "
        "sources. It is not legal advice; unsupported relations are shown as insufficient evidence."
    )


# ---------------------------------------------------------------------------
# Agent intents, actions and plans
# ---------------------------------------------------------------------------


class AgentIntent(str, Enum):
    CREATE_FORMULATION = "CREATE_FORMULATION"
    UPDATE_FORMULATION = "UPDATE_FORMULATION"
    ADD_INGREDIENT = "ADD_INGREDIENT"
    REMOVE_INGREDIENT = "REMOVE_INGREDIENT"
    UPDATE_QUANTITY = "UPDATE_QUANTITY"
    UPDATE_DOSAGE_FORM = "UPDATE_DOSAGE_FORM"
    UPDATE_INTENDED_USE = "UPDATE_INTENDED_USE"
    UPLOAD_DOCUMENT = "UPLOAD_DOCUMENT"
    REVIEW_PRODUCT = "REVIEW_PRODUCT"
    ANALYZE_PATENT = "ANALYZE_PATENT"
    CHECK_ABS = "CHECK_ABS"
    VIEW_EVIDENCE = "VIEW_EVIDENCE"
    RESOLVE_AMBIGUITY = "RESOLVE_AMBIGUITY"
    SHOW_DECISION_PATH = "SHOW_DECISION_PATH"
    SHOW_FORMULATION = "SHOW_FORMULATION"
    FOCUS_ENTITY = "FOCUS_ENTITY"
    COMPARE_FORMULATIONS = "COMPARE_FORMULATIONS"
    SCENARIO = "SCENARIO"
    EXPLAIN_RESULT = "EXPLAIN_RESULT"
    GENERAL_QUESTION = "GENERAL_QUESTION"


AppRoute = Literal["/formulation", "/review", "/patent", "/nba-abs", "/graph"]
ToolName = Literal["review", "patent", "nba-abs"]
GraphFilter = Literal["all", "patent", "regulatory", "abs", "evidence"]
ContextField = Literal[
    "name",
    "route",
    "target_market",
    "jurisdiction",
    "legal_scope",
    "purpose",
    "entity_type",
    "resource_source",
]


class _Action(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateFormulationAction(_Action):
    type: Literal["CREATE_FORMULATION"] = "CREATE_FORMULATION"
    name: str | None = Field(default=None, max_length=120)


class AddIngredientAction(_Action):
    type: Literal["ADD_INGREDIENT"] = "ADD_INGREDIENT"
    user_term: str = Field(min_length=1, max_length=80)
    quantity: float | None = Field(default=None, ge=0)
    unit: Unit | None = None
    plant_part: str | None = Field(default=None, max_length=60)


class RemoveIngredientAction(_Action):
    type: Literal["REMOVE_INGREDIENT"] = "REMOVE_INGREDIENT"
    ingredient_id: str


class UpdateIngredientAction(_Action):
    type: Literal["UPDATE_INGREDIENT"] = "UPDATE_INGREDIENT"
    ingredient_id: str
    user_term: str | None = Field(default=None, min_length=1, max_length=80)
    quantity: float | None = Field(default=None, ge=0)
    unit: Unit | None = None
    plant_part: str | None = Field(default=None, max_length=60)


class UpdateDosageFormAction(_Action):
    type: Literal["UPDATE_DOSAGE_FORM"] = "UPDATE_DOSAGE_FORM"
    value: str = Field(min_length=1, max_length=60)


class UpdateIntendedUseAction(_Action):
    type: Literal["UPDATE_INTENDED_USE"] = "UPDATE_INTENDED_USE"
    value: str = Field(min_length=1, max_length=200)


class UpdateClaimsAction(_Action):
    type: Literal["UPDATE_CLAIMS"] = "UPDATE_CLAIMS"
    claims: list[str] = Field(default_factory=list, max_length=20)


class UpdateFieldAction(_Action):
    type: Literal["UPDATE_FIELD"] = "UPDATE_FIELD"
    field: ContextField
    value: str | None = Field(default=None, max_length=120)


class ResolveEntityAction(_Action):
    type: Literal["RESOLVE_ENTITY"] = "RESOLVE_ENTITY"
    ingredient_id: str
    botanical_name: str = Field(min_length=1, max_length=120)


class ResolveBotanicalsAction(_Action):
    type: Literal["RESOLVE_BOTANICALS"] = "RESOLVE_BOTANICALS"


class ConfirmFormulationAction(_Action):
    type: Literal["CONFIRM_FORMULATION"] = "CONFIRM_FORMULATION"


class NavigateAction(_Action):
    type: Literal["NAVIGATE"] = "NAVIGATE"
    route: AppRoute


class ImportContextAction(_Action):
    type: Literal["IMPORT_CONTEXT"] = "IMPORT_CONTEXT"
    tool: ToolName


class RunProductReviewAction(_Action):
    type: Literal["RUN_PRODUCT_REVIEW"] = "RUN_PRODUCT_REVIEW"


class RunPatentAdvisorAction(_Action):
    type: Literal["RUN_PATENT_ADVISOR"] = "RUN_PATENT_ADVISOR"


class RunAbsAction(_Action):
    type: Literal["RUN_ABS"] = "RUN_ABS"


class AnalyzeFormulationAction(_Action):
    type: Literal["ANALYZE_FORMULATION"] = "ANALYZE_FORMULATION"


class OpenEvidenceAction(_Action):
    type: Literal["OPEN_EVIDENCE"] = "OPEN_EVIDENCE"
    node_id: str | None = None
    ingredient_id: str | None = None
    term: str | None = Field(default=None, max_length=80)


class FocusGraphNodeAction(_Action):
    type: Literal["FOCUS_GRAPH_NODE"] = "FOCUS_GRAPH_NODE"
    node_id: str | None = None
    ingredient_id: str | None = None
    term: str | None = Field(default=None, max_length=80)


class SetGraphFilterAction(_Action):
    type: Literal["SET_GRAPH_FILTER"] = "SET_GRAPH_FILTER"
    filter: GraphFilter


class ClarificationOption(BaseModel):
    value: str
    label: str


class ClarificationRequest(BaseModel):
    kind: Literal["field", "identity", "ingredients", "name"]
    field: str
    question: str
    options: list[ClarificationOption] = Field(default_factory=list)
    ingredient_id: str | None = None
    blocking_tool: ToolName | None = None


class AskClarificationAction(_Action):
    type: Literal["ASK_CLARIFICATION"] = "ASK_CLARIFICATION"
    clarification: ClarificationRequest


class ScenarioChange(BaseModel):
    ingredient_id: str
    quantity: float | None = Field(default=None, ge=0)
    unit: Unit | None = None


class CreateScenarioAction(_Action):
    type: Literal["CREATE_SCENARIO"] = "CREATE_SCENARIO"
    changes: list[ScenarioChange] = Field(min_length=1)


class CompareVersionsAction(_Action):
    type: Literal["COMPARE_VERSIONS"] = "COMPARE_VERSIONS"
    from_version: int | None = None
    to_version: int | None = None


AgentAction = Annotated[
    Union[
        CreateFormulationAction,
        AddIngredientAction,
        RemoveIngredientAction,
        UpdateIngredientAction,
        UpdateDosageFormAction,
        UpdateIntendedUseAction,
        UpdateClaimsAction,
        UpdateFieldAction,
        ResolveEntityAction,
        ResolveBotanicalsAction,
        ConfirmFormulationAction,
        NavigateAction,
        ImportContextAction,
        RunProductReviewAction,
        RunPatentAdvisorAction,
        RunAbsAction,
        AnalyzeFormulationAction,
        OpenEvidenceAction,
        FocusGraphNodeAction,
        SetGraphFilterAction,
        AskClarificationAction,
        CreateScenarioAction,
        CompareVersionsAction,
    ],
    Field(discriminator="type"),
]

# Actions the backend store executes (they change formulation state and create versions).
MUTATING_ACTIONS: frozenset[str] = frozenset(
    {
        "ADD_INGREDIENT",
        "REMOVE_INGREDIENT",
        "UPDATE_INGREDIENT",
        "UPDATE_DOSAGE_FORM",
        "UPDATE_INTENDED_USE",
        "UPDATE_CLAIMS",
        "UPDATE_FIELD",
        "RESOLVE_ENTITY",
        "RESOLVE_BOTANICALS",
        "CONFIRM_FORMULATION",
    }
)
WORKFLOW_ACTIONS: frozenset[str] = frozenset(
    {"RUN_PRODUCT_REVIEW", "RUN_PATENT_ADVISOR", "RUN_ABS", "ANALYZE_FORMULATION"}
)

ActionExecutor = Literal["server", "client", "workflow"]


def executor_for(action_type: str) -> ActionExecutor:
    if action_type in MUTATING_ACTIONS or action_type in {
        "CREATE_FORMULATION",
        "CREATE_SCENARIO",
        "COMPARE_VERSIONS",
    }:
        return "server"
    if action_type in WORKFLOW_ACTIONS:
        return "workflow"
    return "client"


class PlannedAction(BaseModel):
    id: str
    label: str
    executor: ActionExecutor
    action: AgentAction


class AgentPlan(BaseModel):
    run_id: str
    intent: AgentIntent
    intents: list[AgentIntent] = Field(default_factory=list)
    message: str = ""
    actions: list[PlannedAction] = Field(default_factory=list)
    clarification: ClarificationRequest | None = None
    requires_confirmation: bool = False
    original_text: str = ""
    normalized_text: str = ""
    language: str | None = None
    language_method: str | None = None
    translation_note: str | None = None
    message_localized: str | None = Field(
        default=None, description="Assistant message in the user's language (display only)"
    )
    decoder: Literal["llm", "rules", "command"] = "rules"


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    formulation_id: str | None = None
    original_text: str | None = Field(default=None, max_length=4000)
    language: str | None = None
    source: Literal["text", "voice"] = "text"
    current_route: str | None = None


class ActionRequest(BaseModel):
    action: AgentAction
    base_version: int | None = None


class ActionResult(BaseModel):
    ok: bool
    action_type: str
    summary: str
    context: FormulationContext
    changed_ingredient_id: str | None = None
    changed_fields: list[str] = Field(default_factory=list)


class ReadinessResponse(BaseModel):
    tool: ToolName
    ready: bool
    clarification: ClarificationRequest | None = None
    missing: list[str] = Field(default_factory=list)


def plain(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value
