import type { ReactNode } from "react";

export function Panel({
  title,
  right,
  children,
  className = "",
  bodyClass = "",
  titleClass = "",
}: {
  title: string;
  right?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClass?: string;
  titleClass?: string;
}) {
  return (
    <section
      className={`flex min-h-0 min-w-0 flex-col border border-line bg-ink-900 ${className}`}
    >
      <header className="flex h-7 shrink-0 items-center justify-between gap-2 border-b border-line bg-ink-850 px-2.5">
        <h2 className={`label truncate ${titleClass}`}>{title}</h2>
        {right ? <div className="shrink-0">{right}</div> : null}
      </header>
      <div className={`min-h-0 flex-1 overflow-auto p-2.5 ${bodyClass}`}>
        {children}
      </div>
    </section>
  );
}

export function Chip({
  children,
  tone = "neutral",
  title,
}: {
  children: ReactNode;
  tone?: "neutral" | "ok" | "warn" | "bad" | "accent";
  title?: string;
}) {
  const tones: Record<string, string> = {
    neutral: "border-line text-fg-2",
    ok: "border-ok/50 text-ok",
    warn: "border-warn/50 text-warn",
    bad: "border-bad/50 text-bad",
    accent: "border-accent/50 text-accent",
  };
  return (
    <span
      title={title}
      className={`inline-flex items-center gap-1 rounded border px-1.5 py-[1px] text-[9.5px] font-semibold tracking-[0.1em] ${tones[tone]}`}
    >
      {children}
    </span>
  );
}

export function Metric({
  label,
  value,
  sub,
  tone,
}: {
  label: string;
  value: ReactNode;
  sub?: string;
  tone?: string;
}) {
  return (
    <div className="min-w-0 border border-line bg-ink-850 px-2 py-1.5">
      <div className="label truncate">{label}</div>
      <div
        className="truncate font-mono text-[15px] leading-6 font-semibold"
        style={tone ? { color: tone } : undefined}
      >
        {value}
      </div>
      {sub ? (
        <div className="truncate text-[10px] text-dim">{sub}</div>
      ) : null}
    </div>
  );
}

export function Rule({ label }: { label?: string }) {
  return (
    <div className="my-2 flex items-center gap-2">
      <div className="h-px flex-1 bg-line" />
      {label ? (
        <span className="text-[9px] tracking-[0.16em] text-dim uppercase">
          {label}
        </span>
      ) : null}
      <div className="h-px flex-1 bg-line" />
    </div>
  );
}

export function Empty({ text }: { text: string }) {
  return (
    <div className="border border-dashed border-line px-3 py-4 text-center text-[11px] text-dim">
      {text}
    </div>
  );
}
