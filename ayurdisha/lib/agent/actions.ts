import type {
  ClarificationRequest,
  ScenarioChange,
  ToolName,
  Unit,
} from "@/lib/formulation/types";
import { UNITS } from "@/lib/formulation/types";

export type AppRoute = "/formulation" | "/review" | "/patent" | "/nba-abs" | "/graph";
export type GraphFilter = "all" | "patent" | "regulatory" | "abs" | "evidence";
export type ContextField =
  | "name"
  | "route"
  | "target_market"
  | "jurisdiction"
  | "legal_scope"
  | "purpose"
  | "entity_type"
  | "resource_source";

export type AgentAction =
  | { type: "CREATE_FORMULATION"; name?: string | null }
  | {
      type: "ADD_INGREDIENT";
      user_term: string;
      quantity?: number | null;
      unit?: Unit | null;
      plant_part?: string | null;
    }
  | { type: "REMOVE_INGREDIENT"; ingredient_id: string }
  | {
      type: "UPDATE_INGREDIENT";
      ingredient_id: string;
      user_term?: string | null;
      quantity?: number | null;
      unit?: Unit | null;
      plant_part?: string | null;
    }
  | { type: "UPDATE_DOSAGE_FORM"; value: string }
  | { type: "UPDATE_INTENDED_USE"; value: string }
  | { type: "UPDATE_CLAIMS"; claims: string[] }
  | { type: "UPDATE_FIELD"; field: ContextField; value: string | null }
  | { type: "RESOLVE_ENTITY"; ingredient_id: string; botanical_name: string }
  | { type: "RESOLVE_BOTANICALS" }
  | { type: "CONFIRM_FORMULATION" }
  | { type: "NAVIGATE"; route: AppRoute }
  | { type: "IMPORT_CONTEXT"; tool: ToolName }
  | { type: "RUN_PRODUCT_REVIEW" }
  | { type: "RUN_PATENT_ADVISOR" }
  | { type: "RUN_ABS" }
  | { type: "ANALYZE_FORMULATION" }
  | {
      type: "OPEN_EVIDENCE";
      node_id?: string | null;
      ingredient_id?: string | null;
      term?: string | null;
    }
  | {
      type: "FOCUS_GRAPH_NODE";
      node_id?: string | null;
      ingredient_id?: string | null;
      term?: string | null;
    }
  | { type: "SET_GRAPH_FILTER"; filter: GraphFilter }
  | { type: "ASK_CLARIFICATION"; clarification: ClarificationRequest }
  | { type: "CREATE_SCENARIO"; changes: ScenarioChange[] }
  | {
      type: "COMPARE_VERSIONS";
      from_version?: number | null;
      to_version?: number | null;
    };

export type AgentActionType = AgentAction["type"];
export type ActionExecutor = "server" | "client" | "workflow";

export interface PlannedAction {
  id: string;
  label: string;
  executor: ActionExecutor;
  action: AgentAction;
}

export const APP_ROUTES: readonly AppRoute[] = [
  "/formulation",
  "/review",
  "/patent",
  "/nba-abs",
  "/graph",
];
const GRAPH_FILTERS: readonly GraphFilter[] = ["all", "patent", "regulatory", "abs", "evidence"];
const TOOLS: readonly ToolName[] = ["review", "patent", "nba-abs"];
const CONTEXT_FIELDS: readonly ContextField[] = [
  "name",
  "route",
  "target_market",
  "jurisdiction",
  "legal_scope",
  "purpose",
  "entity_type",
  "resource_source",
];

/** Allowed keys per action type — anything else makes the action invalid. */
const SCHEMA: Record<AgentActionType, readonly string[]> = {
  CREATE_FORMULATION: ["name"],
  ADD_INGREDIENT: ["user_term", "quantity", "unit", "plant_part"],
  REMOVE_INGREDIENT: ["ingredient_id"],
  UPDATE_INGREDIENT: ["ingredient_id", "user_term", "quantity", "unit", "plant_part"],
  UPDATE_DOSAGE_FORM: ["value"],
  UPDATE_INTENDED_USE: ["value"],
  UPDATE_CLAIMS: ["claims"],
  UPDATE_FIELD: ["field", "value"],
  RESOLVE_ENTITY: ["ingredient_id", "botanical_name"],
  RESOLVE_BOTANICALS: [],
  CONFIRM_FORMULATION: [],
  NAVIGATE: ["route"],
  IMPORT_CONTEXT: ["tool"],
  RUN_PRODUCT_REVIEW: [],
  RUN_PATENT_ADVISOR: [],
  RUN_ABS: [],
  ANALYZE_FORMULATION: [],
  OPEN_EVIDENCE: ["node_id", "ingredient_id", "term"],
  FOCUS_GRAPH_NODE: ["node_id", "ingredient_id", "term"],
  SET_GRAPH_FILTER: ["filter"],
  ASK_CLARIFICATION: ["clarification"],
  CREATE_SCENARIO: ["changes"],
  COMPARE_VERSIONS: ["from_version", "to_version"],
};

export const MUTATING_ACTIONS: ReadonlySet<AgentActionType> = new Set([
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
]);

export const RUN_ACTION_TOOL: Partial<Record<AgentActionType, ToolName>> = {
  RUN_PRODUCT_REVIEW: "review",
  RUN_PATENT_ADVISOR: "patent",
  RUN_ABS: "nba-abs",
};

export const TOOL_ROUTE: Record<ToolName, AppRoute> = {
  review: "/review",
  patent: "/patent",
  "nba-abs": "/nba-abs",
};

const isStr = (v: unknown, max = 200): v is string =>
  typeof v === "string" && v.length > 0 && v.length <= max;
const optStr = (v: unknown, max = 200) => v == null || isStr(v, max);
const optNum = (v: unknown) =>
  v == null || (typeof v === "number" && Number.isFinite(v) && v >= 0);
const optUnit = (v: unknown) => v == null || (UNITS as readonly unknown[]).includes(v);

/**
 * Validates an action against the fixed schema. Returns the action or null.
 * The UI only executes actions that pass — there is no generic event or DOM path.
 */
export function validateAction(input: unknown): AgentAction | null {
  if (!input || typeof input !== "object" || Array.isArray(input)) return null;
  const a = input as Record<string, unknown>;
  const type = a.type as AgentActionType;
  const allowed = SCHEMA[type];
  if (!allowed) return null;
  for (const key of Object.keys(a)) {
    if (key !== "type" && !allowed.includes(key)) return null;
  }
  switch (type) {
    case "CREATE_FORMULATION":
      return optStr(a.name, 120) ? (a as AgentAction) : null;
    case "ADD_INGREDIENT":
      return isStr(a.user_term, 80) && optNum(a.quantity) && optUnit(a.unit) && optStr(a.plant_part, 60)
        ? (a as AgentAction)
        : null;
    case "REMOVE_INGREDIENT":
      return isStr(a.ingredient_id, 64) ? (a as AgentAction) : null;
    case "UPDATE_INGREDIENT":
      return isStr(a.ingredient_id, 64) &&
        optStr(a.user_term, 80) &&
        optNum(a.quantity) &&
        optUnit(a.unit) &&
        optStr(a.plant_part, 60)
        ? (a as AgentAction)
        : null;
    case "UPDATE_DOSAGE_FORM":
      return isStr(a.value, 60) ? (a as AgentAction) : null;
    case "UPDATE_INTENDED_USE":
      return isStr(a.value, 200) ? (a as AgentAction) : null;
    case "UPDATE_CLAIMS":
      return Array.isArray(a.claims) && a.claims.length <= 20 && a.claims.every((c) => isStr(c, 300))
        ? (a as AgentAction)
        : null;
    case "UPDATE_FIELD":
      return CONTEXT_FIELDS.includes(a.field as ContextField) && optStr(a.value, 120)
        ? (a as AgentAction)
        : null;
    case "RESOLVE_ENTITY":
      return isStr(a.ingredient_id, 64) && isStr(a.botanical_name, 120) ? (a as AgentAction) : null;
    case "NAVIGATE":
      return APP_ROUTES.includes(a.route as AppRoute) ? (a as AgentAction) : null;
    case "IMPORT_CONTEXT":
      return TOOLS.includes(a.tool as ToolName) ? (a as AgentAction) : null;
    case "OPEN_EVIDENCE":
    case "FOCUS_GRAPH_NODE":
      return optStr(a.node_id, 120) && optStr(a.ingredient_id, 64) && optStr(a.term, 80)
        ? (a as AgentAction)
        : null;
    case "SET_GRAPH_FILTER":
      return GRAPH_FILTERS.includes(a.filter as GraphFilter) ? (a as AgentAction) : null;
    case "ASK_CLARIFICATION": {
      const c = a.clarification as Record<string, unknown> | null;
      return c && typeof c === "object" && isStr(c.question, 500) && Array.isArray(c.options)
        ? (a as AgentAction)
        : null;
    }
    case "CREATE_SCENARIO":
      return Array.isArray(a.changes) &&
        a.changes.length > 0 &&
        a.changes.every(
          (c) =>
            c && typeof c === "object" && isStr((c as ScenarioChange).ingredient_id, 64) &&
            optNum((c as ScenarioChange).quantity) && optUnit((c as ScenarioChange).unit),
        )
        ? (a as AgentAction)
        : null;
    case "COMPARE_VERSIONS":
      return optNum(a.from_version) && optNum(a.to_version) ? (a as AgentAction) : null;
    default:
      return a as AgentAction;
  }
}

export function validatePlannedAction(input: unknown): PlannedAction | null {
  if (!input || typeof input !== "object") return null;
  const p = input as Record<string, unknown>;
  const action = validateAction(p.action);
  if (!action || !isStr(p.id, 64) || !isStr(p.label, 200)) return null;
  if (p.executor !== "server" && p.executor !== "client" && p.executor !== "workflow") return null;
  return { id: p.id, label: p.label, executor: p.executor, action };
}
