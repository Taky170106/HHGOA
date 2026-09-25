"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Tag } from "./kit";
import { useSummary, useTigerGraph } from "@/lib/useJson";

const NAV = [
  { href: "/dashboard", label: "DASHBOARD" },
  { href: "/cases", label: "CASES" },
  { href: "/investigation", label: "RUN INVESTIGATION" },
  { href: "/model", label: "MODEL & XAI" },
  { href: "/architecture", label: "ARCHITECTURE" },
];

export function SiteNav() {
  const path = usePathname();
  const tg = useTigerGraph();

  const isActive = (href: string) => path.startsWith(href);

  return (
    <header className="glass-bar z-30 shrink-0 border-b">
      <div className="flex h-14 items-center gap-5 overflow-x-auto px-5">
        {/* identity */}
        <Link href="/" className="group flex shrink-0 items-center gap-2.5">
          <span className="flex h-8 w-8 items-center justify-center rounded-sm border border-accent/50 bg-accent/10 font-display text-[15px] text-accent transition group-hover:rotate-[30deg] duration-[320ms] ease-[cubic-bezier(.16,1,.3,1)]">
            ⬡
          </span>
          <span className="leading-none">
            <span className="block font-display text-[14px] font-bold tracking-[0.2em] text-fg">
              GRAVEX <span className="text-accent">//</span> FRAUD INTELLIGENCE
            </span>
            <span className="mt-[3px] block font-mono text-[8.5px] tracking-[0.22em] text-dim">
              TIGERGRAPH AGENTIC INVESTIGATION · HHGOA 2026
            </span>
          </span>
        </Link>

        <span className="hidden h-6 w-px shrink-0 bg-line xl:block" />

        {/* module navigation */}
        <nav className="hidden shrink-0 items-center gap-1 xl:flex">
          {NAV.map((n) => {
            const active = isActive(n.href);
            return (
              <Link
                key={n.href}
                href={n.href}
                className={`relative px-3 py-2 text-[11px] font-bold tracking-[0.12em] transition duration-200 ease-[cubic-bezier(.16,1,.3,1)] ${
                  active
                    ? "text-accent"
                    : "text-fg-2 hover:-translate-y-px hover:text-fg"
                }`}
              >
                {n.label}
                <span
                  className={`absolute inset-x-2 -bottom-[1px] h-[2px] origin-left transition-transform duration-200 ease-[cubic-bezier(.16,1,.3,1)] ${
                    active
                      ? "scale-x-100 bg-accent"
                      : "scale-x-0 bg-accent/60"
                  }`}
                />
              </Link>
            );
          })}
        </nav>

        <div className="ml-auto flex shrink-0 items-center gap-2">
          <span className="hidden items-center gap-1.5 border border-ok/40 bg-ok/10 px-2 py-1 text-[9.5px] font-bold tracking-[0.14em] text-ok md:inline-flex">
            <span className="pulse-dot h-1.5 w-1.5 rounded-full bg-ok" />
            AGENT ONLINE
          </span>

          <span className="hidden lg:block">
            <Tag tone={tg?.ok ? "ok" : tg ? "bad" : "neutral"}>
              TIGERGRAPH {tg ? tg.http_status : "…"}
            </Tag>
          </span>

          <Link
            href="/investigation"
            className="lift inline-flex h-8 items-center gap-1.5 rounded-sm border border-accent/60 bg-accent/15 px-3 text-[10.5px] font-bold tracking-[0.1em] text-accent hover:bg-accent/25"
          >
            ▶ RUN INVESTIGATION
          </Link>
        </div>
      </div>
    </header>
  );
}

export function StatusFooter() {
  const { data } = useSummary();
  const tg = useTigerGraph();

  return (
    <footer className="glass-bar z-30 flex h-7 shrink-0 items-center gap-5 overflow-x-auto border-t px-5 font-mono text-[9.5px] whitespace-nowrap text-dim">
      <span>
        VALIDATION{" "}
        <span className="text-ok">{data?.validation_status ?? "…"}</span>{" "}
        {data ? `${data.cases_passed}/${data.cases.length}` : ""}
      </span>
      <span>
        GRAPH WRITE <span className="text-bad">BLOCKED</span>
      </span>
      <span>
        SAR <span className="text-bad">{data?.sar_filed ?? "…"}</span>/20
      </span>
      <span>
        TOOL CALLS live {data?.tool_calls.live ?? "…"} · retrieval{" "}
        {data?.tool_calls.retrieval ?? "…"}
      </span>
      <span>
        GSQL {data ? `${data.gsql.queries_executed}/${data.gsql.total_investigation_queries}` : "…"}
      </span>
      <span>
        MCP{" "}
        {data?.mcp
          ? `${data.mcp.live_pass}/${data.mcp.live_total}`
          : "…"}
      </span>
      <span className="ml-auto">
        TIGERGRAPH {tg ? `${tg.http_status} · ${tg.latency_ms}ms` : "…"}
      </span>
      <span>tokens 0</span>
    </footer>
  );
}
