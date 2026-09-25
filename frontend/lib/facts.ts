/**
 * Repository facts used on the overview / architecture pages.
 *
 * Only values that can be pointed at a file in this repository live here, and
 * every entry carries its citation. Anything that changes per run (case counts,
 * model metrics, validation status) is read at runtime from the JSON artifacts
 * instead of being duplicated here.
 */

export interface Fact {
  label: string;
  value: string;
  source: string;
}

/** Phase 2 graph baseline — locked, never reloaded. */
export const GRAPH_FACTS: Fact[] = [
  { label: "VERTEX TYPES", value: "8", source: "tigergraph/schema" },
  { label: "EDGE TYPES", value: "11", source: "docs/GRAPH_WRITE_BLOCKER.md:37" },
  {
    label: "LOADED EDGES",
    value: "2,505,266",
    source: "DATASET_DISCOVERY.md:137",
  },
  { label: "REJECTED / ORPHAN", value: "0 / 0", source: "docs/GRAPH_WRITE_BLOCKER.md:37" },
];

/** The development phase order the repository was built in (AGENTS.md). */
export const PHASES: { n: string; name: string; status: "done" | "blocked" }[] = [
  { n: "0", name: "Dataset analysis", status: "done" },
  { n: "1", name: "Schema", status: "done" },
  { n: "2", name: "GSQL + load", status: "done" },
  { n: "3", name: "MCP tools", status: "done" },
  { n: "4", name: "GraphRAG", status: "done" },
  { n: "5", name: "Evidence engine", status: "done" },
  { n: "6", name: "Agent", status: "done" },
  { n: "7", name: "Innovation", status: "done" },
  { n: "8", name: "Policy", status: "done" },
  { n: "9", name: "UI", status: "done" },
  { n: "10", name: "20 cases", status: "done" },
  { n: "11", name: "Evaluation", status: "done" },
  { n: "12", name: "Demo", status: "done" },
];

/** Modules of this console — the navigation model. */
export interface ModuleDef {
  n: string;
  title: string;
  href: string;
  desc: string;
  tags: string[];
}

export const MODULES: ModuleDef[] = [
  {
    n: "01",
    title: "Case Section",
    href: "/cases",
    desc: "All 20 HHGoa cases with verdict, pattern, fraud probability, exposure and SAR state. Filter by fraud / uncertain / legitimate, open any case.",
    tags: ["20 CASES", "FILTER", "VERDICT"],
  },
  {
    n: "02",
    title: "Case Investigation",
    href: "/cases/HHG-001",
    desc: "One case, six modules: graph, nine-stage pipeline, evidence, model + SHAP, next best action and the full auditable case record.",
    tags: ["GRAPH", "PIPELINE", "AUDIT"],
  },
  {
    n: "03",
    title: "Run Investigation",
    href: "/investigation",
    desc: "Execute the agent pipeline for any case: trigger → triage → graph → evidence → ML → XAI → uncertainty → policy → next best action.",
    tags: ["DEMO REPLAY", "9 STAGES", "ELAPSED"],
  },
  {
    n: "04",
    title: "Model & XAI",
    href: "/model",
    desc: "The fraud classifier, held-out metrics, feature importance, global SHAP attribution and the learned evidence-signal weights.",
    tags: ["ROC-AUC 0.9308", "SHAP", "32 FEATURES"],
  },
  {
    n: "05",
    title: "System Architecture",
    href: "/architecture",
    desc: "Every layer of the system with an honest status: LIVE VERIFIED, IN PROGRESS or ARCHITECTURAL — each row cites its evidence.",
    tags: ["14 LAYERS", "PROVENANCE"],
  },
  {
    n: "06",
    title: "Evidence Engine",
    href: "/cases/HHG-001",
    desc: "Five evidence categories with a learned support / contradict / context direction, sufficiency scoring and a controlled acquisition chain.",
    tags: ["210 ITEMS", "5 CATEGORIES"],
  },
];

/** Terminal lines shown on the overview — real command output. */
export const VALIDATION_RUN: { cmd: string; out: string[] } = {
  cmd: "python scripts/validate_cases.py",
  out: [
    "files=20/20  passed=20/20  errors=0  status=PASS",
    "verdicts: fraud=6  uncertain=11  legitimate=3  sar=6",
    "graph_write: BLOCKED (documented in docs/GRAPH_WRITE_BLOCKER.md)",
    "tokens=0 (no LLM key in this environment)",
  ],
};

export const DEMO_RUN: { cmd: string; out: string[] } = {
  cmd: "python scripts/demo_hhg001.py",
  out: [
    "case HHG-001  live GSQL calls 5  wall clock 5.35s  status PASS",
    "fraud_probability 0.2973 (pre) -> 0.0473 (post evidence)",
    "verdict legitimate  pattern none  SAR false",
  ],
};
