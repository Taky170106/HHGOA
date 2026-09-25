import { NextResponse } from "next/server";
import { readJson, readJsonOrNull } from "@/lib/repo";
import type {
  E2eRun,
  EvidenceWeights,
  MetricsFull,
  ModelPayload,
  ShapGlobal,
} from "@/lib/types";

export const dynamic = "force-dynamic";

/** Global model artifacts for the Model & XAI module (read-only). */
export async function GET() {
  const metrics = readJson<MetricsFull>("models/metrics.json");
  const shapGlobal = readJsonOrNull<ShapGlobal>("xai/shap_global.json");
  const weights = readJsonOrNull<EvidenceWeights>("models/evidence_weights.json");
  const e2e = readJsonOrNull<E2eRun>("validation/phase3_e2e.json");

  const payload: ModelPayload = { metrics, shapGlobal, weights, e2e };

  return NextResponse.json(payload, {
    headers: { "cache-control": "no-store" },
  });
}
