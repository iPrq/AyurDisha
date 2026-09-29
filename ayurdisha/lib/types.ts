export type LegalScope = "domestic" | "international";
export type EvidenceKind =
  | "FACT_FROM_SOURCE"
  | "MODEL_INTERPRETATION"
  | "CALCULATION"
  | "UNCERTAINTY";
export type DimensionRating =
  | "FAVORABLE"
  | "MODERATE"
  | "CHALLENGING"
  | "INSUFFICIENT_EVIDENCE";

export interface RetrievedSource {
  id: string;
  title: string;
  text: string;
  section: string | null;
  source_type: string;
  source_url: string | null;
  effective_date: string | null;
  retrieval_score: number;
  jurisdiction: string | null;
  legal_scope: LegalScope | null;
  is_fixture: boolean;
}

export interface BotanicalCandidate {
  botanical_name: string;
  synonyms: string[];
  phytochemicals: string[];
  confidence: number;
}

export interface BotanicalResult {
  status: "RESOLVED" | "AMBIGUOUS" | "UNRESOLVED";
  input_term: string;
  botanical_name: string | null;
  synonyms: string[];
  phytochemicals: string[];
  confidence: number;
  candidates: BotanicalCandidate[];
  notes: string | null;
}

export interface ClaimVerification {
  claim: string;
  status: "SUPPORTED" | "PARTIALLY_SUPPORTED" | "UNSUPPORTED";
  evidence_source_ids: string[];
  notes: string | null;
}

export interface VerificationResult {
  outcome: "PASS" | "FAIL" | "HUMAN_REVIEW_REQUIRED";
  claims: ClaimVerification[];
  stripped_unsupported_claims: string[];
  escalation_reasons: string[];
  notes: string | null;
}

export interface ReviewFinding {
  summary: string;
  evidence_source_ids: string[];
  evidence_kind: EvidenceKind;
}

interface BaseResponse {
  verification: VerificationResult | null;
  retrieved_sources: RetrievedSource[];
  final_answer: string | null;
  disclaimer: string;
}

// Product review

export interface ProductReviewRequest {
  product: string;
  ingredients: string[];
  legal_scope: LegalScope;
  target_market?: string | null;
  product_category?: string | null;
  user_query?: string | null;
}

export interface ProductReviewResponse extends BaseResponse {
  product: string;
  ingredients: string[];
  legal_scope: LegalScope;
  target_market: string | null;
  botanicals: BotanicalResult[];
  market_feasibility: {
    rating: DimensionRating;
    summary: string;
    target_category: string | null;
    target_market: string | null;
    competitors: {
      name: string;
      company: string | null;
      notes: string | null;
      evidence_source_ids: string[];
    }[];
    demand_indicators: ReviewFinding[];
    findings: ReviewFinding[];
    insufficient_evidence: boolean;
  } | null;
  legal_compliance: {
    rating: DimensionRating;
    summary: string;
    regulatory_category: string | null;
    requirements: ReviewFinding[];
    restrictions: ReviewFinding[];
    insufficient_evidence: boolean;
  } | null;
  resource_accessibility: {
    rating: DimensionRating;
    summary: string;
    resources: {
      ingredient: string;
      botanical_name: string | null;
      availability: string;
      cultivation: string;
      sustainability_concerns: string;
      evidence_source_ids: string[];
    }[];
    findings: ReviewFinding[];
    insufficient_evidence: boolean;
  } | null;
  combined_summary: string | null;
}

// Patent advisor

export interface PatentAdvisorRequest {
  product: string;
  ingredients: string[];
  legal_scope: LegalScope;
  user_query?: string | null;
  document_text?: string | null;
}

export interface PdfPageInfo {
  page: number;
  method: "text" | "ocr" | "empty";
  chars: number;
}

export interface PatentDocumentExtractResponse {
  filename: string | null;
  product: string;
  ingredients: string[];
  summary: string;
  document_text: string;
  pages: PdfPageInfo[];
  total_pages: number;
  ocr_used: boolean;
  truncated: boolean;
}

export interface PatentAdvisorResponse extends BaseResponse {
  product: string;
  ingredients: string[];
  legal_scope: LegalScope;
  botanical: BotanicalResult | null;
  section3: {
    provisions: {
      clause: string;
      triggered: boolean;
      reason: string;
      evidence_source_ids: string[];
      evidence_kind: EvidenceKind;
      evidence_gap: boolean;
    }[];
    summary: string;
    insufficient_evidence: boolean;
    rejected_clauses: string[];
    evidence_gap_clauses: string[];
  } | null;
  patentability_risk: {
    score: number;
    triggered_clauses: string[];
    unweighted_triggered_clauses: string[];
    weight_d: number;
    weight_e: number;
    weight_p: number;
    disclaimer: string;
  } | null;
  prior_art: {
    findings: {
      summary: string;
      evidence_source_ids: string[];
      evidence_kind: EvidenceKind;
      relevance: string | null;
    }[];
    summary: string;
    insufficient_evidence: boolean;
  } | null;
  ip_routes: {
    suggestions: {
      route: "Patent" | "Trademark" | "Design" | "Trade Secret";
      appropriate: boolean;
      rationale: string;
      evidence_source_ids: string[];
      evidence_kind: EvidenceKind;
    }[];
    summary: string;
    insufficient_evidence: boolean;
  } | null;
}

// NBA / ABS

export type AbsPurpose =
  | "commercial_utilization"
  | "research"
  | "bio_survey"
  | "ipr";
export type EntityType = "indian" | "foreign";
export type ResourceSource = "wild" | "cultivated" | "unknown";

export interface NbaAbsRequest {
  product: string;
  ingredients: string[];
  annual_turnover_inr?: number | null;
  purpose: AbsPurpose;
  entity_type: EntityType;
  resource_source: ResourceSource;
  percentage_override?: number | null;
  user_query?: string | null;
}

export interface NbaAbsResponse extends BaseResponse {
  product: string;
  ingredients: string[];
  purpose: AbsPurpose;
  entity_type: EntityType;
  resource_source: ResourceSource;
  annual_turnover_inr: number | null;
  botanicals: BotanicalResult[];
  applicability: {
    status: "APPLICABLE" | "NOT_APPLICABLE" | "UNCERTAIN";
    authority: string | null;
    summary: string;
    reasons: ReviewFinding[];
    exemptions_considered: ReviewFinding[];
    insufficient_evidence: boolean;
  } | null;
  rate_selection: {
    percentage: number | null;
    basis: string | null;
    tier_description: string | null;
    source_id: string | null;
    quoted_text: string | null;
    rationale: string;
    grounded: boolean;
    insufficient_evidence: boolean;
  } | null;
  calculation: {
    annual_turnover_inr: number;
    percentage: number;
    fee_inr: number;
    formula: string;
    percentage_origin: "source" | "user_override";
    source_id: string | null;
  } | null;
}
