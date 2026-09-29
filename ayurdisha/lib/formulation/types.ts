import type {
  AbsPurpose,
  BotanicalCandidate,
  BotanicalResult,
  EntityType,
  EvidenceKind,
  LegalScope,
  PdfPageInfo,
  ResourceSource,
  RetrievedSource,
  VerificationResult,
} from "@/lib/types";

export type IdentityStatus =
  | "confirmed"
  | "probable"
  | "ambiguous"
  | "insufficient_evidence"
  | "human_review";

export type FormulationSourceType =
  | "manual"
  | "text"
  | "pdf"
  | "patent_pdf"
  | "chat"
  | "voice";

export const UNITS = [
  "mg",
  "g",
  "kg",
  "mcg",
  "ml",
  "l",
  "%",
  "iu",
  "part",
  "tablet",
  "capsule",
] as const;
export type Unit = (typeof UNITS)[number];

export interface FormulationIngredient {
  id: string;
  user_term: string;
  normalized_name: string | null;
  botanical_name: string | null;
  synonyms: string[];
  plant_part: string | null;
  quantity: number | null;
  unit: string | null;
  ingredient_type: string;
  identity_status: IdentityStatus;
  evidence_ids: string[];
  source_text: string | null;
  candidates: BotanicalCandidate[];
  identity_notes: string | null;
  resolved_by_user: boolean;
  botanical: BotanicalResult | null;
}

export interface FormulationCharacteristic {
  key: string;
  label: string;
  value: string;
  origin: "user" | "derived" | "source";
  evidence_kind: EvidenceKind | null;
  evidence_ids: string[];
  status: IdentityStatus;
}

export interface FormulationContext {
  formulation_id: string;
  name: string | null;
  raw_text: string | null;
  original_user_text: string | null;
  language: string | null;
  source_type: FormulationSourceType;
  source_document_id: string | null;
  ingredients: FormulationIngredient[];
  dosage_form: string | null;
  route: string | null;
  intended_use: string | null;
  product_claims: string[];
  target_market: string | null;
  jurisdiction: string;
  legal_scope: LegalScope;
  entity_type: EntityType | null;
  purpose: AbsPurpose | null;
  resource_source: ResourceSource | null;
  formulation_characteristics: FormulationCharacteristic[];
  missing_information: string[];
  evidence_ids: string[];
  confirmed: boolean;
  last_referenced_ingredient: string | null;
  created_at: string;
  updated_at: string;
  version: number;
  botanical_identities: string[];
  plant_parts: string[];
  biological_resources: string[];
  ambiguities: string[];
}

export interface ExtractionMeta {
  method: string | null;
  dropped: string[];
  language: string | null;
  language_method: string | null;
  pages: PdfPageInfo[];
  total_pages: number | null;
  ocr_used: boolean;
  truncated: boolean;
  filename: string | null;
}

export interface VersionInfo {
  version: number;
  change_summary: string;
  action_type: string | null;
  created_at: string;
}

export interface FormulationEnvelope {
  context: FormulationContext;
  extraction: ExtractionMeta | null;
  versions: VersionInfo[];
}

export type FGNodeType =
  | "formulation"
  | "composition"
  | "ingredient"
  | "botanical_identity"
  | "plant_part"
  | "chemical"
  | "dosage_form"
  | "route"
  | "intended_use"
  | "characteristic"
  | "classification"
  | "regulatory"
  | "patent"
  | "prior_art"
  | "traditional_knowledge"
  | "biological_resource"
  | "abs"
  | "evidence"
  | "action"
  | "uncertainty";

export type FGEdgeType =
  | "contains"
  | "derived_from"
  | "identified_as"
  | "part_of"
  | "used_for"
  | "classified_as"
  | "may_trigger"
  | "relevant_to"
  | "supported_by"
  | "contradicted_by"
  | "requires_review"
  | "leads_to";

export type GraphBranch =
  | "core"
  | "regulatory"
  | "patent"
  | "abs"
  | "evidence"
  | "action";

export interface WhyItMatters {
  facts: string[];
  interpretation: string[];
  uncertainty: string[];
}

export interface FGNode {
  id: string;
  type: FGNodeType;
  label: string;
  sublabel: string | null;
  status: IdentityStatus | null;
  layer: number;
  branch: GraphBranch;
  evidence_ids: string[];
  evidence_kind: EvidenceKind | null;
  why_it_matters: WhyItMatters | null;
  ref: string | null;
}

export interface FGEdge {
  id: string;
  source: string;
  target: string;
  type: FGEdgeType;
  status: IdentityStatus | null;
  evidence_ids: string[];
}

export interface EvidenceItem {
  source: RetrievedSource;
  branch: string;
  supports: string[];
  verifier_status:
    | "SUPPORTED"
    | "PARTIALLY_SUPPORTED"
    | "UNSUPPORTED"
    | "NOT_VERIFIED";
}

export interface FormulationGraph {
  formulation_id: string;
  version: number;
  nodes: FGNode[];
  edges: FGEdge[];
  evidence: EvidenceItem[];
  verification: VerificationResult | null;
  generated_at: string;
  disclaimer: string;
}

export type ToolName = "review" | "patent" | "nba-abs";

export interface SuggestedAction {
  tool: ToolName;
  label: string;
  action_type: "RUN_PRODUCT_REVIEW" | "RUN_PATENT_ADVISOR" | "RUN_ABS";
  ready: boolean;
  missing: string[];
  question: string | null;
}

export interface AnalyzeResponse {
  context: FormulationContext;
  graph: FormulationGraph;
  suggested_actions: SuggestedAction[];
  escalation_reasons: string[];
}

export interface ClarificationOption {
  value: string;
  label: string;
}

export interface ClarificationRequest {
  kind: "field" | "identity" | "ingredients" | "name";
  field: string;
  question: string;
  options: ClarificationOption[];
  ingredient_id: string | null;
  blocking_tool: ToolName | null;
}

export interface ReadinessResponse {
  tool: ToolName;
  ready: boolean;
  clarification: ClarificationRequest | null;
  missing: string[];
}

export interface ToolHandoff {
  tool: ToolName;
  route: string;
  formulation_id: string;
  version: number;
  fields: Record<string, unknown>;
  derived_fields: string[];
  missing: string[];
  summary: {
    name?: string;
    ingredient_count?: number;
    dosage_form?: string | null;
    normalized_botanicals?: string[];
    biological_resources?: string[];
    ambiguous?: string[];
  };
}

export interface ScenarioChange {
  ingredient_id: string;
  quantity?: number | null;
  unit?: Unit | null;
}

export interface ScenarioResult {
  banner: string;
  base_version: number;
  scenario_context: FormulationContext;
  changes: string[];
  potentially_affected: string[];
  note: string;
}

export interface VersionComparison {
  formulation_id: string;
  from_version: number;
  to_version: number;
  changes: string[];
}

export interface IngredientInput {
  user_term: string;
  quantity?: number | null;
  unit?: string | null;
  plant_part?: string | null;
}

export interface CreateFormulationRequest {
  name?: string | null;
  raw_text?: string | null;
  language?: string | null;
  source_type?: FormulationSourceType;
  ingredients?: IngredientInput[];
  dosage_form?: string | null;
  route?: string | null;
  intended_use?: string | null;
  claims?: string[];
  target_market?: string | null;
  legal_scope?: LegalScope;
  purpose?: AbsPurpose | null;
  entity_type?: EntityType | null;
  resource_source?: ResourceSource | null;
}

// Language

export interface LanguageCapabilities {
  provider: string;
  configured: boolean;
  asr: boolean;
  translation: boolean;
  tts: boolean;
  transliteration: boolean;
  detection: "service" | "heuristic";
  languages: { code: string; name: string }[];
  notes: string[];
}

export interface TranscribeResponse {
  text: string;
  language: string;
  provider: string;
  detected: { language: string; method: string; provider: string } | null;
}

export interface TranslateResult {
  text: string;
  original_text: string;
  source_language: string;
  target_language: string;
  provider: string;
  translated: boolean;
  protected_terms: string[];
  fallback_reason: string | null;
}

export interface SpeakResult {
  audio_base64: string;
  audio_format: string;
  language: string;
  provider: string;
}

export const LANGUAGE_OPTIONS: { code: string; name: string }[] = [
  { code: "auto", name: "Auto-detect" },
  { code: "en", name: "English" },
  { code: "hi", name: "हिन्दी Hindi" },
  { code: "ml", name: "മലയാളം Malayalam" },
  { code: "ta", name: "தமிழ் Tamil" },
  { code: "te", name: "తెలుగు Telugu" },
  { code: "kn", name: "ಕನ್ನಡ Kannada" },
  { code: "bn", name: "বাংলা Bengali" },
  { code: "mr", name: "मराठी Marathi" },
  { code: "gu", name: "ગુજરાતી Gujarati" },
  { code: "pa", name: "ਪੰਜਾਬੀ Punjabi" },
  { code: "or", name: "ଓଡ଼ିଆ Odia" },
  { code: "as", name: "অসমীয়া Assamese" },
  { code: "ur", name: "اردو Urdu" },
];
