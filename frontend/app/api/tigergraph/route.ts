import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

/**
 * Read-only liveness probe against the running TigerGraph RESTPP endpoint.
 * GET /echo does not touch any graph, schema or data.
 */
export async function GET() {
  const started = Date.now();
  try {
    const res = await fetch("http://localhost:9000/echo", {
      signal: AbortSignal.timeout(5000),
      cache: "no-store",
    });
    const text = await res.text();
    let message = text.slice(0, 200);
    try {
      const parsed = JSON.parse(text) as { message?: string };
      if (parsed.message) message = parsed.message;
    } catch {
      /* keep raw */
    }
    return NextResponse.json({
      ok: res.ok,
      http_status: res.status,
      message,
      latency_ms: Date.now() - started,
      endpoint: "http://localhost:9000/echo",
      probed_at: new Date().toISOString(),
    });
  } catch (err) {
    return NextResponse.json({
      ok: false,
      http_status: 0,
      message: err instanceof Error ? err.message : "unreachable",
      latency_ms: Date.now() - started,
      endpoint: "http://localhost:9000/echo",
      probed_at: new Date().toISOString(),
    });
  }
}
