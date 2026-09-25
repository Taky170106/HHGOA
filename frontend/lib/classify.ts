/**
 * Evidence presentation helpers.
 *
 * Two independent axes, both derived from repository content only:
 *
 *  1. CATEGORY   — which of the five evidence families an item belongs to,
 *                  decided by deterministic rules over the stored claim/ref.
 *
 *  2. DIRECTION  — whether the claim supports or contradicts the fraud
 *                  hypothesis. The phrase tables below mirror the signal
 *                  groupings the builder itself uses (STRONG_SIGNALS /
 *                  OTHER_INCRIMINATORY / EXCULPATORY in
 *                  scripts/build_cases.py), so a claim counted as
 *                  exculpatory by the scorer is shown as contradicting here.
 *                  Claims matching no signal are neutral context — they are
 *                  never forced into a side.
 */

import type { EvidenceItem } from "./types";

export type EvCategory =
  | "Graph Evidence"
  | "Transaction Evidence"
  | "Device Evidence"
  | "Historical Evidence"
  | "Policy Evidence";

export type Direction = "support" | "contradict" | "context";

export const CATEGORIES: EvCategory[] = [
  "Graph Evidence",
  "Transaction Evidence",
  "Device Evidence",
  "Historical Evidence",
  "Policy Evidence",
];

/** [phrase, signal] — claims that corroborate the fraud hypothesis. */
const SUPPORT_PHRASES: [string, string][] = [
  ["recorded on confirmed-fraud closed case", "device_prior_fraud"],
  ["already appears in confirmed-fraud closed case", "card_prior_fraud"],
  ["online authorisation(s) in the", "burst"],
  ["is more than", "amount_outlier"],
  ["marked New", "new_device"],
  ["region NOT the cardholder's home", "out_of_region"],
  ["shared with card(s)", "device_ring"],
  ["of under $5", "card_testing"],
  ["did not make", "customer_denial"],
  ["not made by them", "customer_denial"],
  ["I never made", "customer_denial"],
  ["match_status:", "match_anomaly"],
  ["behind ", "proxy"],
  ["product code", "new_product"],
];

/** [phrase, signal] — claims that cut against the fraud hypothesis. */
const CONTRADICT_PHRASES: [string, string][] = [
  ["repeating charge rather than", "recurring"],
  ["(region home)", "home_region"],
  ["confirms they made", "customer_confirmation"],
];

/** Claims that are deliberately neutral — recorded, not scored either way. */
const CONTEXT_PHRASES: string[] = [
  "runs opposite to confirmed outcome",
  "Retrieved prior case memory",
  "Real-time model scored",
  "Model score for transaction",
  "holds no device record",
  "carries no FROM_DEVICE edge",
  "from risk_score trigger",
  "from customer_report trigger",
  "from analyst_report trigger",
];

export function categorize(e: EvidenceItem): EvCategory {
  const c = e.claim;
  const ref = e.ref || "";

  // 1. device — device profiles, FROM_DEVICE edges, device sharing
  if (
    /device profile|FROM_DEVICE|device id|DeviceProfile/i.test(c) ||
    ref.includes("find_device_connections")
  ) {
    return "Device Evidence";
  }

  // 2. historical — prior/closed cases, population calibration, recurring history
  if (
    /confirmed-fraud closed case|prior case memory|earlier transaction\(s\) with the same amount|runs opposite to confirmed outcome/i.test(
      c,
    )
  ) {
    return "Historical Evidence";
  }

  // 3. policy — anything that arrived through the evidence-acquisition policy
  if (
    e.source === "customer" ||
    /customer_report trigger|did not make|not made by them|confirms they made|analyst_report trigger|Analyst confirms|policy R\d/i.test(
      c,
    )
  ) {
    return "Policy Evidence";
  }

  // 4. transaction — the flagged transaction itself, its trigger and its model score
  if (
    ref.includes("get_transaction") ||
    ref.includes("case_pack.csv") ||
    /^Transaction \d+/.test(c) ||
    /^Model score for transaction/.test(c) ||
    /^Case HHG-\d+ opened/.test(c)
  ) {
    return "Transaction Evidence";
  }

  // 5. everything else sourced from the graph
  return "Graph Evidence";
}

export function direction(e: EvidenceItem): {
  dir: Direction;
  signal: string | null;
} {
  const c = e.claim;

  for (const [phrase, signal] of SUPPORT_PHRASES) {
    if (c.includes(phrase)) return { dir: "support", signal };
  }
  for (const [phrase, signal] of CONTRADICT_PHRASES) {
    if (c.includes(phrase)) return { dir: "contradict", signal };
  }
  for (const phrase of CONTEXT_PHRASES) {
    if (c.includes(phrase)) return { dir: "context", signal: null };
  }
  return { dir: "context", signal: null };
}

/** Compact display labels for the policy action names. */
export const ACTION_LABEL: Record<string, string> = {
  VERIFY_WITH_CUSTOMER: "VERIFY",
  STEP_UP_AUTH: "VERIFY",
  MONITOR_CARD: "MONITOR",
  MONITOR_CONNECTED_CARDS: "MONITOR",
  WARN_CUSTOMER: "MONITOR",
  ALLOW_TRANSACTION: "MONITOR",
  ESCALATE_TO_ANALYST: "ESCALATE",
  BLOCK_CARD: "BLOCK",
  BLOCK_ALL_CARDS: "BLOCK",
  DECLINE_TRANSACTION: "BLOCK",
  CLOSE_NO_FRAUD: "RELEASE",
  CREATE_CASE: "ESCALATE",
  FILE_REPORT: "ESCALATE",
  GENERATE_REPORT: "MONITOR",
};

export function actionLabel(action: string): string {
  return ACTION_LABEL[action] ?? "ESCALATE";
}

export function verdictColor(v: string): string {
  if (v === "fraud") return "var(--color-bad)";
  if (v === "legitimate") return "var(--color-ok)";
  return "var(--color-warn)";
}

export function verdictShort(v: string): string {
  if (v === "fraud") return "FRD";
  if (v === "legitimate") return "LEG";
  return "UNC";
}
