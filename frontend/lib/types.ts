/**
 * Types mirroring the benchmark answer schema documented in
 * DATASET/README.md "Answer Format" (mirrored by phase0/OUTPUT_SCHEMA.md).
 * Field names are taken from the repository case files — nothing is renamed.
 */

export type Verdict = "fraud" | "legitimate" | "uncertain";
export type CaseStatus = "open" | "closed_fraud" | "closed_legitimate" | "escalated";
export type Route = "auto" | "L1" | "L2";
export type EvidenceSource = "graph" | "document" | "customer" | "external";
export type EvidenceClass = "direct" | "derived_graph" | "model_analytical";

export interface EvidenceItem {
  evidence_id: string;
  claim: string;
  source: EvidenceSource;
  ref: string;
  entity_ids: string[];
  evidence_class: EvidenceClass;
}

export interface ActionItem {
  action: string;
  route: Route;
  reason: string;
}

export interface Finding {
  finding_id: string;
  title: string;
  statement: string;
  evidence_ids: string[];
  type: string;
}

export interface Decision {
  decision: Verdict;
  status: CaseStatus;
  rationale: string;
  supporting_evidence_ids: string[];
  policy_rules: string[];
}

export interface EvidenceRequest {
  type: "customer_validation" | "step_up_auth" | "analyst_info";
  asked_after_step: number;
  assumed_response: string;
}

export interface Sar {
  file: boolean;
  reason: string;
  narrative: string;
  subjects: string[];
  total_amount_usd: number;
  activity_dates: string[];
}

export interface GraphQuery {
  name: string;
  params: Record<string, string>;
  http_status: number;
  latency_ms: number;
}

export interface GraphEdge {
  edge: string;
  from: string;
  to: string;
  from_type: string;
  to_type: string;
}

export interface GraphEvidence {
  single_source_of_truth: string;
  phase_2_baseline: string | Record<string, unknown>;
  queries: GraphQuery[];
  entities: Record<string, string[]>;
  edges: GraphEdge[];
  graph_facts: string[];
  investigation_interpretation: string[];
  graph_fact_vs_interpretation: string;
}

export interface InvestigationStep {
  step: number;
  name: string;
  detail: string;
}

export interface GraphWrite {
  status: string;
  written_to_graph: boolean;
  graph_case_id: string;
  reason: string;
  reference: string;
}

export interface StageState {
  stage: string;
  additional_evidence_received?: boolean;
  additional_evidence?: EvidenceRequest[] | unknown;
  current_evidence?: string[];
  current_findings?: string[];
  preliminary_decision?: {
    verdict: Verdict;
    fraud_probability: number;
    pattern: string;
    status: string;
  };
  preliminary_next_best_action?: ActionItem[];
  updated_decision?: Decision;
  updated_next_best_action?: ActionItem[];
  what_changed?: string;
  note?: string;
  evidence_requested?: EvidenceRequest[];
}

export interface CaseFile {
  case_id: string;
  case: {
    status: CaseStatus;
    verdict: Verdict;
    fraud_probability: number;
    pattern: string;
    pattern_description: string;
    affected_txn_ids: string[];
    first_suspicious_txn_id: string;
    connected_card_ids: string[];
    connected_device_profiles: string[];
    exposure_usd: number;
    evidence: EvidenceItem[];
    similar_prior_cases: string[];
    summary: string;
    written_to_graph: boolean;
    graph_case_id: string;
  };
  evidence_requests: EvidenceRequest[];
  next_best_actions: {
    initial: ActionItem[];
    final: ActionItem[];
    what_changed: string;
  };
  sar: Sar;
  stop_reason: string;
  tool_calls: number;
  tokens: number;
  latency_s: number;
  investigation_record: InvestigationStep[];
  findings: Finding[];
  decision: Decision;
  actions_taken: ActionItem[];
  actions_recommended_awaiting_approval?: ActionItem[];
  graph_evidence: GraphEvidence;
  sar_status: {
    file: boolean;
    reason: string;
    required_approval_route: string;
  };
  required_approval_route: Route[];
  pre_additional_evidence_state: StageState;
  post_additional_evidence_state: StageState;
  graph_write: GraphWrite;
}

/* ---------- API payloads ---------- */

export interface CaseSummaryRow {
  case_id: string;
  ok: boolean;
  verdict: Verdict;
  pattern: string;
  fraud_probability: number;
  exposure_usd: number;
  evidence_items: number;
  sar_file: boolean;
  next_best_action: string;
  approval_route: string[];
  additional_evidence_received: boolean;
  tool_calls: number;
}

export interface SummaryPayload {
  cases: CaseSummaryRow[];
  counts: { fraud: number; legitimate: number; uncertain: number };
  sar_filed: number;
  tool_calls: { live: number; retrieval: number };
  validation_status: string;
  cases_passed: number;
  total_errors: number;
  metrics: {
    model: string;
    n_features: number;
    n_samples: number;
    features_excluded: string[];
    test: { roc_auc: number; accuracy: number; precision: number; recall: number; f1: number };
    trained_at: string;
  };
  graph_write: GraphWrite;
  gsql: Record<string, number | string>;
  mcp: Record<string, unknown>;
}

export interface ShapFeature {
  feature: string;
  value: number;
  shap_value: number;
}

export interface ShapLocalEntry {
  txn_id: string;
  card_id: string;
  customer_id: string;
  risk_score: number;
  model_probability: number;
  model_prediction: string;
  top_contributing_features: ShapFeature[];
  note: string;
}

export interface ShapGlobal {
  scope: string;
  model: string;
  n_rows_explained: number;
  mean_abs_shap_top15: { feature: string; mean_abs_shap: number }[];
  baseline_output_mean: number;
}

export interface E2eRun {
  case_id: string;
  ran_at: string;
  status: string;
  steps: { step: number; name: string; detail: string }[];
  live_gsql_calls: number;
  wall_clock_s: number;
  model_probability: number;
  verdict: string;
}

export interface CasePayload {
  caseFile: CaseFile;
  shapLocal: ShapLocalEntry | null;
  shapGlobal: ShapGlobal | null;
  e2e: E2eRun | null;
}
