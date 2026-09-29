"use client";

import { usePathname, useRouter } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  type AgentAction,
  type AppRoute,
  type GraphFilter,
  type PlannedAction,
  RUN_ACTION_TOOL,
  TOOL_ROUTE,
  validatePlannedAction,
} from "@/lib/agent/actions";
import { waitForTool } from "@/lib/agent/bus";
import { formulationApi, type AgentPlanResponse } from "@/lib/formulation/api";
import type { StepEvent } from "@/lib/formulation/sse";
import type {
  AnalyzeResponse,
  ClarificationRequest,
  FormulationContext,
  FormulationGraph,
  ScenarioResult,
  ToolName,
  VersionComparison,
  VersionInfo,
} from "@/lib/formulation/types";

export type StepStatus =
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "waiting_for_user"
  | "requires_confirmation"
  | "skipped";

export type RunStatus =
  | "running"
  | "completed"
  | "failed"
  | "waiting_for_user"
  | "requires_confirmation"
  | "cancelled";

export interface SubStep {
  node: string;
  label: string;
  status: "running" | "completed" | "failed";
}

export interface AgentStep {
  id: string;
  label: string;
  executor: PlannedAction["executor"];
  action: AgentAction;
  status: StepStatus;
  detail?: string;
  substeps: SubStep[];
}

export interface AgentRun {
  id: string;
  request: string;
  source: "text" | "voice" | "button";
  message: string;
  messageLocalized: string | null;
  translationNote: string | null;
  language: string | null;
  status: RunStatus;
  steps: AgentStep[];
  clarification: ClarificationRequest | null;
  error?: string;
  createdAt: number;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  subtext?: string;
  runId?: string;
}

export interface GraphUi {
  filter: GraphFilter;
  focusNodeId: string | null;
  evidenceOpen: boolean;
  evidenceNodeId: string | null;
}

export interface AnalysisProgress {
  started: (e: StepEvent) => void;
  completed: (e: StepEvent) => void;
  failed: (e: StepEvent) => void;
}

interface SendOptions {
  source?: "text" | "voice";
  originalText?: string;
  language?: string;
}

interface AgentContextValue {
  formulation: FormulationContext | null;
  versions: VersionInfo[];
  setFormulation: (ctx: FormulationContext | null, versions?: VersionInfo[]) => void;
  refreshFormulation: () => Promise<void>;
  analysis: AnalyzeResponse | null;
  analysisStale: boolean;
  analyzing: boolean;
  analyzeNow: (progress?: AnalysisProgress) => Promise<void>;
  graphUi: GraphUi;
  setGraphUi: (patch: Partial<GraphUi>) => void;
  scenario: ScenarioResult | null;
  setScenario: (s: ScenarioResult | null) => void;
  comparison: VersionComparison | null;
  runs: AgentRun[];
  messages: ChatMessage[];
  busy: boolean;
  send: (text: string, opts?: SendOptions) => Promise<void>;
  answerClarification: (runId: string, value: string) => Promise<void>;
  confirmRun: (runId: string) => void;
  cancelRun: (runId: string) => void;
  startToolRun: (tool: ToolName, opts?: { run?: boolean }) => void;
  language: string;
  setLanguage: (code: string) => void;
  dockOpen: boolean;
  setDockOpen: (open: boolean) => void;
}

const AgentContext = createContext<AgentContextValue | null>(null);

export function useAgent(): AgentContextValue {
  const ctx = useContext(AgentContext);
  if (!ctx) throw new Error("useAgent must be used inside <AgentProvider>");
  return ctx;
}

const STORAGE_KEY = "ayurdisha.agent.v1";
const TOOL_LABEL: Record<ToolName, string> = {
  review: "Product Review",
  patent: "Patent Advisor",
  "nba-abs": "NBA / ABS",
};
const RUN_LABEL: Record<ToolName, string> = {
  review: "Running product review",
  patent: "Running patent analysis",
  "nba-abs": "Assessing biodiversity/ABS applicability",
};
const RUN_TYPE: Record<ToolName, AgentAction> = {
  review: { type: "RUN_PRODUCT_REVIEW" },
  patent: { type: "RUN_PATENT_ADVISOR" },
  "nba-abs": { type: "RUN_ABS" },
};

const uid = (p: string) =>
  `${p}_${typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID().slice(0, 8) : Math.random().toString(36).slice(2, 10)}`;

const errMsg = (e: unknown) => (e instanceof Error ? e.message : String(e));

/** Step failures carry a user-facing message; waiting pauses the run without failing it. */
class PauseRun extends Error {
  constructor(public clarification: ClarificationRequest) {
    super("waiting_for_user");
  }
}

export function resolveGraphNode(
  graph: FormulationGraph,
  ctx: FormulationContext | null,
  target: { node_id?: string | null; ingredient_id?: string | null; term?: string | null },
): string | null {
  const ids = new Set(graph.nodes.map((n) => n.id));
  if (target.node_id && ids.has(target.node_id)) return target.node_id;
  if (target.ingredient_id && ids.has(`ing:${target.ingredient_id}`)) return `ing:${target.ingredient_id}`;
  const term = target.term?.trim().toLowerCase();
  if (!term) return null;
  const ing = ctx?.ingredients.find((i) =>
    [i.user_term, i.normalized_name, i.botanical_name, ...i.synonyms]
      .filter(Boolean)
      .some((n) => (n as string).toLowerCase() === term),
  );
  if (ing && ids.has(`ing:${ing.id}`)) return `ing:${ing.id}`;
  const byLabel = graph.nodes.find((n) => n.label.toLowerCase().includes(term));
  return byLabel?.id ?? null;
}

export function AgentProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();

  const [formulation, setFormulationState] = useState<FormulationContext | null>(null);
  const [versions, setVersions] = useState<VersionInfo[]>([]);
  const [analysis, setAnalysis] = useState<AnalyzeResponse | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [graphUi, setGraphUiState] = useState<GraphUi>({
    filter: "all",
    focusNodeId: null,
    evidenceOpen: false,
    evidenceNodeId: null,
  });
  const [scenario, setScenario] = useState<ScenarioResult | null>(null);
  const [comparison, setComparison] = useState<VersionComparison | null>(null);
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const [language, setLanguage] = useState("auto");
  const [dockOpen, setDockOpen] = useState(false);
  const [hydrated, setHydrated] = useState(false);

  const formulationRef = useRef<FormulationContext | null>(null);
  const analysisRef = useRef<AnalyzeResponse | null>(null);
  const runsRef = useRef<AgentRun[]>([]);
  const pathRef = useRef(pathname);
  const cancelled = useRef(new Set<string>());
  const importedVersion = useRef<Partial<Record<ToolName, number>>>({});

  useEffect(() => {
    pathRef.current = pathname;
  }, [pathname]);

  const setFormulation = useCallback((ctx: FormulationContext | null, v?: VersionInfo[]) => {
    formulationRef.current = ctx;
    setFormulationState(ctx);
    if (v) setVersions(v);
    if (!ctx) {
      analysisRef.current = null;
      setAnalysis(null);
      setScenario(null);
      setComparison(null);
    }
  }, []);

  const refreshFormulation = useCallback(async () => {
    const id = formulationRef.current?.formulation_id;
    if (!id) return;
    const env = await formulationApi.get(id);
    setFormulation(env.context, env.versions);
  }, [setFormulation]);

  const setGraphUi = useCallback((patch: Partial<GraphUi>) => {
    setGraphUiState((g) => ({ ...g, ...patch }));
  }, []);

  // ---- persistence (session only; the formulation itself lives on the backend) ----
  useEffect(() => {
    try {
      const raw = sessionStorage.getItem(STORAGE_KEY);
      if (raw) {
        const saved = JSON.parse(raw) as {
          formulationId?: string;
          runs?: AgentRun[];
          messages?: ChatMessage[];
          language?: string;
        };
        // Interrupted runs are not resumed or reported as done after a reload.
        const restored = (saved.runs ?? []).map((r) =>
          r.status === "running"
            ? {
                ...r,
                status: "failed" as const,
                error: "Interrupted by page reload",
                steps: r.steps.map((s) =>
                  s.status === "running" || s.status === "queued"
                    ? { ...s, status: "skipped" as const, detail: "Not run (page reloaded)" }
                    : s,
                ),
              }
            : r,
        );
        runsRef.current = restored;
        setRuns(restored);
        setMessages(saved.messages ?? []);
        if (saved.language) setLanguage(saved.language);
        if (saved.formulationId) {
          formulationApi
            .get(saved.formulationId)
            .then((env) => setFormulation(env.context, env.versions))
            .catch(() => setFormulation(null));
        }
      }
    } catch {
      /* corrupt storage is ignored */
    }
    setHydrated(true);
  }, [setFormulation]);

  useEffect(() => {
    if (!hydrated) return;
    try {
      sessionStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          formulationId: formulation?.formulation_id,
          runs: runs.slice(-15),
          messages: messages.slice(-40),
          language,
        }),
      );
    } catch {
      /* storage full / disabled */
    }
  }, [hydrated, formulation?.formulation_id, runs, messages, language]);

  // ---- run state helpers ----
  const commitRuns = useCallback((next: AgentRun[]) => {
    runsRef.current = next;
    setRuns(next);
  }, []);

  const patchRun = useCallback(
    (runId: string, patch: Partial<AgentRun> | ((r: AgentRun) => Partial<AgentRun>)) => {
      commitRuns(
        runsRef.current.map((r) =>
          r.id === runId ? { ...r, ...(typeof patch === "function" ? patch(r) : patch) } : r,
        ),
      );
    },
    [commitRuns],
  );

  const patchStep = useCallback(
    (runId: string, stepId: string, patch: Partial<AgentStep> | ((s: AgentStep) => Partial<AgentStep>)) => {
      patchRun(runId, (r) => ({
        steps: r.steps.map((s) =>
          s.id === stepId ? { ...s, ...(typeof patch === "function" ? patch(s) : patch) } : s,
        ),
      }));
    },
    [patchRun],
  );

  const progressFor = useCallback(
    (runId: string, stepId: string) => ({
      started: (e: StepEvent) =>
        patchStep(runId, stepId, (s) => ({
          substeps: [...s.substeps.filter((x) => x.node !== e.node), { node: e.node, label: e.label, status: "running" }],
        })),
      completed: (e: StepEvent) =>
        patchStep(runId, stepId, (s) => ({
          substeps: s.substeps.some((x) => x.node === e.node)
            ? s.substeps.map((x) => (x.node === e.node ? { ...x, status: "completed" as const } : x))
            : [...s.substeps, { node: e.node, label: e.label, status: "completed" as const }],
        })),
      failed: (e: StepEvent) =>
        patchStep(runId, stepId, (s) => ({
          substeps: s.substeps.map((x) => (x.node === e.node ? { ...x, status: "failed" as const } : x)),
        })),
    }),
    [patchStep],
  );

  const waitForPath = useCallback((route: string, timeoutMs = 8000) => {
    return new Promise<void>((resolve, reject) => {
      const start = Date.now();
      const tick = () => {
        if (pathRef.current === route) return resolve();
        if (Date.now() - start > timeoutMs) return reject(new Error(`Navigation to ${route} did not complete.`));
        setTimeout(tick, 50);
      };
      tick();
    });
  }, []);

  const runAnalysis = useCallback(
    async (progress?: AnalysisProgress) => {
      const id = formulationRef.current?.formulation_id;
      if (!id) throw new Error("No formulation to analyze yet.");
      setAnalyzing(true);
      try {
        const res = await formulationApi.analyzeStream(id, {
          onStepStarted: progress?.started,
          onStepCompleted: progress?.completed,
          onStepFailed: progress?.failed,
        });
        analysisRef.current = res;
        setAnalysis(res);
        formulationRef.current = res.context;
        setFormulationState(res.context);
        return res;
      } finally {
        setAnalyzing(false);
      }
    },
    [],
  );

  const analyzeNow = useCallback(
    async (progress?: AnalysisProgress) => {
      await runAnalysis(progress);
    },
    [runAnalysis],
  );

  const requireId = () => {
    const id = formulationRef.current?.formulation_id;
    if (!id) throw new Error("No formulation yet — describe or create one first.");
    return id;
  };

  const ensureGraph = async (runId: string, stepId: string) => {
    const current = analysisRef.current;
    const ctx = formulationRef.current;
    if (current && ctx && current.graph.version === ctx.version) return current.graph;
    patchStep(runId, stepId, { detail: "Generating the formulation map first" });
    return (await runAnalysis(progressFor(runId, stepId))).graph;
  };

  /** Executes one step. Returns a user-facing completion detail; throws on failure. */
  const executeStep = async (run: AgentRun, step: AgentStep): Promise<string> => {
    const a = step.action;
    switch (a.type) {
      case "CREATE_FORMULATION": {
        if (formulationRef.current) return "Using the current formulation";
        const env = await formulationApi.create({ name: a.name ?? null, source_type: "chat" });
        setFormulation(env.context, env.versions);
        return "Formulation created";
      }
      case "ADD_INGREDIENT":
      case "REMOVE_INGREDIENT":
      case "UPDATE_INGREDIENT":
      case "UPDATE_DOSAGE_FORM":
      case "UPDATE_INTENDED_USE":
      case "UPDATE_CLAIMS":
      case "UPDATE_FIELD":
      case "RESOLVE_ENTITY":
      case "RESOLVE_BOTANICALS":
      case "CONFIRM_FORMULATION": {
        const id = requireId();
        const res = await formulationApi.action(id, a, formulationRef.current?.version);
        const env = await formulationApi.get(id);
        setFormulation(res.context, env.versions);
        return res.summary;
      }
      case "NAVIGATE": {
        if (pathRef.current !== a.route) {
          router.push(a.route);
          await waitForPath(a.route);
        }
        return `On ${a.route}`;
      }
      case "IMPORT_CONTEXT": {
        const id = requireId();
        const handoff = await formulationApi.handoff(id, a.tool);
        const caps = await waitForTool(a.tool);
        await caps.autofill(handoff);
        importedVersion.current[a.tool] = handoff.version;
        return `Filled ${Object.keys(handoff.fields).length} fields from formulation v${handoff.version}`;
      }
      case "RUN_PRODUCT_REVIEW":
      case "RUN_PATENT_ADVISOR":
      case "RUN_ABS": {
        const tool = RUN_ACTION_TOOL[a.type] as ToolName;
        const id = requireId();
        const ready = await formulationApi.readiness(id, tool);
        if (!ready.ready && ready.clarification) throw new PauseRun(ready.clarification);
        if (!ready.ready) throw new Error(`Missing: ${ready.missing.join(", ")}`);
        const caps = await waitForTool(tool);
        const version = formulationRef.current?.version ?? 0;
        if (importedVersion.current[tool] !== version) {
          const handoff = await formulationApi.handoff(id, tool);
          await caps.autofill(handoff);
          importedVersion.current[tool] = handoff.version;
        }
        const outcome = await caps.run(progressFor(run.id, step.id));
        return outcome.summary;
      }
      case "ANALYZE_FORMULATION": {
        const res = await runAnalysis(progressFor(run.id, step.id));
        return `Map built: ${res.graph.nodes.length} nodes, ${res.graph.evidence.length} sources`;
      }
      case "SET_GRAPH_FILTER": {
        await ensureGraph(run.id, step.id);
        setGraphUi({ filter: a.filter });
        return `Showing ${a.filter === "all" ? "all branches" : `${a.filter} branch`}`;
      }
      case "FOCUS_GRAPH_NODE": {
        const graph = await ensureGraph(run.id, step.id);
        const nodeId = resolveGraphNode(graph, formulationRef.current, a);
        if (!nodeId) throw new Error(`“${a.term ?? a.node_id ?? a.ingredient_id}” is not on the map.`);
        setGraphUi({ focusNodeId: nodeId });
        return `Focused ${graph.nodes.find((n) => n.id === nodeId)?.label ?? nodeId}`;
      }
      case "OPEN_EVIDENCE": {
        const graph = await ensureGraph(run.id, step.id);
        const target = a.node_id || a.ingredient_id || a.term ? resolveGraphNode(graph, formulationRef.current, a) : null;
        setGraphUi({ evidenceOpen: true, evidenceNodeId: target, ...(target ? { focusNodeId: target } : {}) });
        return `Evidence panel open (${graph.evidence.length} sources)`;
      }
      case "ASK_CLARIFICATION":
        throw new PauseRun(a.clarification);
      case "CREATE_SCENARIO": {
        const res = await formulationApi.scenario(requireId(), a.changes);
        setScenario(res);
        return `Scenario built (${res.changes.length} change${res.changes.length === 1 ? "" : "s"}) — not applied`;
      }
      case "COMPARE_VERSIONS": {
        const res = await formulationApi.compare(requireId(), a.from_version, a.to_version);
        setComparison(res);
        return `v${res.from_version} → v${res.to_version}: ${res.changes.length} change(s)`;
      }
    }
  };

  const executeFrom = async (runId: string, startIndex: number) => {
    setBusy(true);
    patchRun(runId, { status: "running", clarification: null, error: undefined });
    try {
      for (let i = startIndex; ; i++) {
        const run = runsRef.current.find((r) => r.id === runId);
        if (!run || i >= run.steps.length) break;
        if (cancelled.current.has(runId)) {
          patchRun(runId, (r) => ({
            status: "cancelled",
            steps: r.steps.map((s, j) => (j >= i && s.status !== "completed" ? { ...s, status: "skipped" } : s)),
          }));
          return;
        }
        const step = run.steps[i];
        if (step.status === "completed") continue;
        patchStep(runId, step.id, { status: "running", detail: undefined });
        try {
          const detail = await executeStep(run, step);
          patchStep(runId, step.id, { status: "completed", detail });
        } catch (e) {
          if (e instanceof PauseRun) {
            patchStep(runId, step.id, { status: "waiting_for_user", detail: e.clarification.question });
            patchRun(runId, { status: "waiting_for_user", clarification: e.clarification });
            return;
          }
          const message = errMsg(e);
          patchStep(runId, step.id, { status: "failed", detail: message });
          patchRun(runId, (r) => ({
            status: "failed",
            error: message,
            steps: r.steps.map((s, j) => (j > i ? { ...s, status: "skipped", detail: "Not run" } : s)),
          }));
          return;
        }
      }
      patchRun(runId, { status: "completed" });
    } finally {
      setBusy(false);
    }
  };

  const startRun = (run: AgentRun) => {
    commitRuns([...runsRef.current, run]);
    if (run.status === "requires_confirmation") return;
    void executeFrom(run.id, 0);
  };

  const buildRun = (
    plan: Pick<AgentPlanResponse, "message" | "message_localized" | "translation_note" | "language"> & {
      id: string;
      actions: PlannedAction[];
      requires_confirmation: boolean;
    },
    request: string,
    source: AgentRun["source"],
  ): AgentRun => ({
    id: plan.id,
    request,
    source,
    message: plan.message,
    messageLocalized: plan.message_localized,
    translationNote: plan.translation_note,
    language: plan.language,
    status: plan.requires_confirmation ? "requires_confirmation" : "running",
    clarification: null,
    createdAt: Date.now(),
    steps: plan.actions.map((p, idx) => ({
      id: p.id,
      label: p.label,
      executor: p.executor,
      action: p.action,
      status: plan.requires_confirmation && idx === 0 ? "requires_confirmation" : "queued",
      substeps: [],
    })),
  });

  const waitingRun = () => {
    for (let i = runsRef.current.length - 1; i >= 0; i--) {
      if (runsRef.current[i].status === "waiting_for_user") return runsRef.current[i];
    }
    return undefined;
  };

  const resumeAfterAnswer = async (run: AgentRun) => {
    const idx = run.steps.findIndex((s) => s.status === "waiting_for_user");
    if (idx < 0) return;
    const step = run.steps[idx];
    if (step.action.type === "ASK_CLARIFICATION") {
      patchStep(run.id, step.id, { status: "completed", detail: "Answered" });
      await executeFrom(run.id, idx + 1);
    } else {
      patchStep(run.id, step.id, { status: "queued", detail: undefined });
      await executeFrom(run.id, idx);
    }
  };

  const answerClarification = async (runId: string, value: string) => {
    const run = runsRef.current.find((r) => r.id === runId);
    const c = run?.clarification;
    if (!run || !c) return;
    let action: AgentAction | null = null;
    if (c.kind === "identity" && c.ingredient_id) {
      action = { type: "RESOLVE_ENTITY", ingredient_id: c.ingredient_id, botanical_name: value };
    } else if (c.kind === "field") {
      action = { type: "UPDATE_FIELD", field: c.field as Extract<AgentAction, { type: "UPDATE_FIELD" }>["field"], value };
    }
    if (!action) return;
    const label = c.options.find((o) => o.value === value)?.label ?? value;
    setMessages((m) => [...m, { id: uid("msg"), role: "user", text: label, runId }]);
    const answerStep: AgentStep = {
      id: uid("step"),
      label: c.kind === "identity" ? `Recording identity: ${label}` : `Recording ${c.field.replace("_", " ")}: ${label}`,
      executor: "server",
      action,
      status: "running",
      substeps: [],
    };
    const waitIdx = run.steps.findIndex((s) => s.status === "waiting_for_user");
    patchRun(runId, (r) => ({
      clarification: null,
      steps: [...r.steps.slice(0, waitIdx), answerStep, ...r.steps.slice(waitIdx)],
    }));
    try {
      const detail = await executeStep(run, answerStep);
      patchStep(runId, answerStep.id, { status: "completed", detail });
    } catch (e) {
      patchStep(runId, answerStep.id, { status: "failed", detail: errMsg(e) });
      patchRun(runId, { status: "waiting_for_user", clarification: c });
      return;
    }
    const updated = runsRef.current.find((r) => r.id === runId);
    if (updated) await resumeAfterAnswer(updated);
  };

  const send = async (text: string, opts: SendOptions = {}) => {
    const message = text.trim();
    if (!message) return;
    setMessages((m) => [
      ...m,
      {
        id: uid("msg"),
        role: "user",
        text: opts.originalText && opts.originalText !== message ? opts.originalText : message,
        subtext: opts.source === "voice" ? "🎙 voice" : undefined,
      },
    ]);
    setBusy(true);
    let plan: AgentPlanResponse;
    try {
      plan = await formulationApi.chat({
        message,
        formulation_id: formulationRef.current?.formulation_id ?? null,
        original_text: opts.originalText ?? message,
        language: opts.language ?? language,
        source: opts.source ?? "text",
        current_route: pathRef.current,
      });
    } catch (e) {
      setMessages((m) => [...m, { id: uid("msg"), role: "assistant", text: `I couldn't plan that: ${errMsg(e)}` }]);
      setBusy(false);
      return;
    }
    setBusy(false);
    const actions = plan.actions.map(validatePlannedAction);
    if (actions.some((a) => a === null)) {
      setMessages((m) => [
        ...m,
        { id: uid("msg"), role: "assistant", text: "I received an action I'm not allowed to run, so I stopped. Nothing was changed." },
      ]);
      return;
    }
    const valid = actions as PlannedAction[];

    // A reply to an open question: apply only the matching answer, then resume that run.
    const pending = waitingRun();
    const answer = pending?.clarification
      ? valid.find(
          (p) =>
            (p.action.type === "UPDATE_FIELD" && p.action.field === pending.clarification!.field) ||
            (p.action.type === "RESOLVE_ENTITY" && p.action.ingredient_id === pending.clarification!.ingredient_id),
        )
      : undefined;
    if (pending && answer) {
      const value = answer.action.type === "UPDATE_FIELD" ? answer.action.value : (answer.action as { botanical_name: string }).botanical_name;
      setMessages((m) => m.slice(0, -1));
      if (value) await answerClarification(pending.id, value);
      return;
    }
    if (pending) cancelRun(pending.id);

    const assistantText = plan.message_localized || plan.message || (valid.length ? "Working on it." : "I'm not sure what to do with that.");
    setMessages((m) => [
      ...m,
      {
        id: uid("msg"),
        role: "assistant",
        text: assistantText,
        subtext: plan.translation_note ?? (plan.message_localized ? plan.message : undefined),
        runId: valid.length ? plan.run_id : undefined,
      },
    ]);
    if (!valid.length) return;
    startRun(
      buildRun(
        { ...plan, id: plan.run_id, actions: valid, requires_confirmation: plan.requires_confirmation },
        opts.originalText ?? message,
        opts.source ?? "text",
      ),
    );
  };

  const confirmRun = (runId: string) => {
    const run = runsRef.current.find((r) => r.id === runId);
    if (!run || run.status !== "requires_confirmation") return;
    patchRun(runId, (r) => ({ steps: r.steps.map((s) => (s.status === "requires_confirmation" ? { ...s, status: "queued" } : s)) }));
    void executeFrom(runId, 0);
  };

  const cancelRun = (runId: string) => {
    const run = runsRef.current.find((r) => r.id === runId);
    if (!run) return;
    if (run.status === "running") {
      cancelled.current.add(runId);
      return;
    }
    if (run.status === "waiting_for_user" || run.status === "requires_confirmation") {
      patchRun(runId, (r) => ({
        status: "cancelled",
        clarification: null,
        steps: r.steps.map((s) => (s.status === "completed" ? s : { ...s, status: "skipped", detail: "Cancelled" })),
      }));
    }
  };

  const startToolRun = (tool: ToolName, opts: { run?: boolean } = {}) => {
    const shouldRun = opts.run ?? true;
    const actions: PlannedAction[] = [
      { id: uid("step"), label: `Opening ${TOOL_LABEL[tool]}`, executor: "client", action: { type: "NAVIGATE", route: TOOL_ROUTE[tool] as AppRoute } },
      { id: uid("step"), label: "Importing formulation context", executor: "client", action: { type: "IMPORT_CONTEXT", tool } },
      ...(shouldRun
        ? [{ id: uid("step"), label: RUN_LABEL[tool], executor: "workflow" as const, action: RUN_TYPE[tool] }]
        : []),
    ];
    const runId = uid("run");
    const message = shouldRun
      ? `Running ${TOOL_LABEL[tool]} with the current formulation.`
      : `Opening ${TOOL_LABEL[tool]} with the current formulation.`;
    setDockOpen(true);
    setMessages((m) => [...m, { id: uid("msg"), role: "assistant", text: message, runId }]);
    startRun(
      buildRun(
        {
          id: runId,
          actions,
          requires_confirmation: false,
          message,
          message_localized: null,
          translation_note: null,
          language: null,
        },
        shouldRun ? `Run ${TOOL_LABEL[tool]}` : `Open ${TOOL_LABEL[tool]}`,
        "button",
      ),
    );
  };

  const analysisStale = !!(analysis && formulation && analysis.graph.version !== formulation.version);

  const value = useMemo<AgentContextValue>(
    () => ({
      formulation,
      versions,
      setFormulation,
      refreshFormulation,
      analysis,
      analysisStale,
      analyzing,
      analyzeNow,
      graphUi,
      setGraphUi,
      scenario,
      setScenario,
      comparison,
      runs,
      messages,
      busy,
      send,
      answerClarification,
      confirmRun,
      cancelRun,
      startToolRun,
      language,
      setLanguage,
      dockOpen,
      setDockOpen,
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [formulation, versions, analysis, analysisStale, analyzing, graphUi, scenario, comparison, runs, messages, busy, language, dockOpen],
  );

  return <AgentContext.Provider value={value}>{children}</AgentContext.Provider>;
}
