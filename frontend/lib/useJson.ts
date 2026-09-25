"use client";

import { useEffect, useState } from "react";
import type { SummaryPayload } from "./types";

export interface TgProbe {
  ok: boolean;
  http_status: number;
  latency_ms: number;
  endpoint?: string;
  message?: string;
  probed_at?: string;
}

export interface Async<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
}

/** Minimal read-only fetch hook — no cache, no stale state. */
export function useJson<T>(url: string): Async<T> {
  const [state, setState] = useState<Async<T>>({
    data: null,
    error: null,
    loading: true,
  });

  useEffect(() => {
    let alive = true;
    setState({ data: null, error: null, loading: true });

    fetch(url)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`${r.status} ${url}`))))
      .then((data: T) => {
        if (alive) setState({ data, error: null, loading: false });
      })
      .catch((e: unknown) => {
        if (alive)
          setState({
            data: null,
            error: e instanceof Error ? e.message : String(e),
            loading: false,
          });
      });

    return () => {
      alive = false;
    };
  }, [url]);

  return state;
}

/** Convenience: the summary payload every page shares. */
export function useSummary(): Async<SummaryPayload> {
  return useJson<SummaryPayload>("/api/summary");
}

/** Read-only TigerGraph RESTPP probe, refreshed every 30s. */
export function useTigerGraph(): TgProbe | null {
  const [tg, setTg] = useState<TgProbe | null>(null);

  useEffect(() => {
    let alive = true;
    const probe = () =>
      fetch("/api/tigergraph")
        .then((r) => (r.ok ? r.json() : null))
        .then((t: TgProbe | null) => {
          if (alive && t) setTg(t);
        })
        .catch(() => undefined);

    void probe();
    const id = setInterval(probe, 30000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  return tg;
}
