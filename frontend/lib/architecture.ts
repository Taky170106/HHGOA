/**
 * SYSTEM ARCHITECTURE view.
 *
 * Every row is tagged from what the repository actually contains — no layer is
 * marked LIVE unless there is an artifact (or a runtime probe) behind it.
 *
 *   live  = verifiable artifact exists and passed validation
 *   wip   = dependency/state exists, pipeline not wired end-to-end
 *   arch  = described by the design, not implemented in this repository
 */

export type LayerStatus = "live" | "wip" | "arch";

export interface Layer {
  name: string;
  status: LayerStatus;
  detail: string;
  evidence: string;
}

export const ARCHITECTURE: Layer[] = [
  {
    name: "Analyst",
    status: "live",
    detail: "Operator driving the console; opens a case, reviews evidence, approves the route.",
    evidence: "20 cases opened from DATASET/case_pack.csv",
  },
  {
    name: "Next.js",
    status: "live",
    detail: "Gravex — this console (landing, dashboard, cases, run investigation, model & XAI, architecture), reading the repository artifacts over local API routes.",
    evidence: "frontend/ · http://localhost:3000",
  },
  {
    name: "FastAPI",
    status: "arch",
    detail: "No backend/ directory exists in the repository and nothing is listening on :8000. The console reads files directly instead of proxying to a Python service.",
    evidence: "backend/ — not present",
  },
  {
    name: "LangGraph",
    status: "wip",
    detail: "The langgraph package is installed and agent/state.py declares the state shape, but there is no graph.py or nodes/ implementation. The pipeline that produced the 20 answers is the deterministic builder.",
    evidence: "agent/state.py only · scripts/build_cases.py",
  },
  {
    name: "Gemma",
    status: "wip",
    detail: "No LLM API key is present in this environment, so no model call was made. Every case file records tokens = 0 rather than a fabricated token count.",
    evidence: "cases/*.json → tokens: 0",
  },
  {
    name: "Controlled Tools",
    status: "live",
    detail: "MCP tool layer with an allow/deny policy: 7 of 7 live tools answered, 5 dangerous tools refused, policy denials recorded.",
    evidence: "mcp/validation/phase3_mcp_live.json",
  },
  {
    name: "TigerGraph",
    status: "live",
    detail: "Investigation memory. 10 GSQL queries compiled, installed and executed with zero 404s; RESTPP is probed live when this console loads.",
    evidence: "docs/PHASE3_QUERY_CATALOG.json · RESTPP /echo probe",
  },
  {
    name: "Evidence Engine",
    status: "live",
    detail: "Evidence is read from the graph, classified, sufficiency is checked before anything is recommended.",
    evidence: "210 evidence items across cases/HHG-001..020.json",
  },
  {
    name: "ML",
    status: "live",
    detail: "RandomForest over 32 graph/transaction features trained on real labels with risk_score excluded as leakage.",
    evidence: "models/metrics.json → ROC-AUC 0.9308",
  },
  {
    name: "XAI",
    status: "live",
    detail: "SHAP explanations — one global set plus one local explanation per benchmark case.",
    evidence: "xai/shap_global.json · xai/shap_local_benchmark_cases.json",
  },
  {
    name: "Counterfactual",
    status: "arch",
    detail: "Defined as a workflow stage. No counterfactual/ module exists and no counterfactual calculation was executed, so the console labels its panel ARCHITECTURAL WORKFLOW.",
    evidence: "counterfactual/ — not present",
  },
  {
    name: "Policy",
    status: "live",
    detail: "Rules R1–R10 plus Sections 3a/6 constrain every recommendation; the validator fails any action whose reason does not cite a rule.",
    evidence: "DATASET/POLICY rules · scripts/validate_cases.py",
  },
  {
    name: "Next Best Action",
    status: "live",
    detail: "Initial and final action sets with the sentence explaining what changed between them.",
    evidence: "next_best_actions.{initial,final,what_changed} in all 20 cases",
  },
  {
    name: "Case / Audit / Memory",
    status: "live",
    detail: "Each answer is an auditable case record; the case-result write-back to the graph is deliberately blocked and documented rather than performed.",
    evidence: "cases/validation_report.json → PASS 20/20 · docs/GRAPH_WRITE_BLOCKER.md",
  },
];

export const FLOW = ARCHITECTURE.map((l) => l.name);

export const STATUS_LABEL: Record<LayerStatus, string> = {
  live: "LIVE VERIFIED",
  wip: "IN PROGRESS",
  arch: "ARCHITECTURAL",
};
