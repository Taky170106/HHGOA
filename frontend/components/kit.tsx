"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type ReactNode } from "react";

/* ------------------------------------------------------------------ */
/* motion — reveal on scroll (UI-THEME.md §6 signature motion)         */
/* ------------------------------------------------------------------ */

/**
 * Fades/rises its children in the first time they enter the viewport.
 * Falls back to visible immediately when IntersectionObserver is missing,
 * and always reveals after a short safety timeout so content can never
 * stay hidden (recording / automated checks).
 */
export function Reveal({
  children,
  delay = 0,
  className = "",
}: {
  children: ReactNode;
  delay?: number;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [shown, setShown] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el || typeof IntersectionObserver === "undefined") {
      setShown(true);
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setShown(true);
          io.disconnect();
        }
      },
      { rootMargin: "0px 0px -60px 0px", threshold: 0.05 },
    );
    io.observe(el);
    const safety = window.setTimeout(() => setShown(true), 2500);
    return () => {
      io.disconnect();
      window.clearTimeout(safety);
    };
  }, []);

  return (
    <div
      ref={ref}
      style={delay ? { transitionDelay: `${delay}ms` } : undefined}
      className={`reveal ${shown ? "is-in" : ""} ${className}`}
    >
      {children}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* layout                                                              */
/* ------------------------------------------------------------------ */

export function Container({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={`mx-auto w-full max-w-[1520px] px-8 ${className}`}>
      {children}
    </div>
  );
}

export function Eyebrow({
  children,
  tone = "accent",
}: {
  children: ReactNode;
  tone?: "accent" | "ok" | "warn" | "bad" | "dim";
}) {
  const tones: Record<string, string> = {
    accent: "text-accent",
    ok: "text-ok",
    warn: "text-warn",
    bad: "text-bad",
    dim: "text-dim",
  };
  return (
    <div
      className={`flex items-center gap-2 text-[10.5px] font-bold tracking-[0.28em] uppercase ${tones[tone]}`}
    >
      <span className="h-px w-6 bg-current opacity-60" />
      {children}
    </div>
  );
}

export function PageHeader({
  eyebrow,
  title,
  lede,
  actions,
  meta,
}: {
  eyebrow: string;
  title: ReactNode;
  lede?: ReactNode;
  actions?: ReactNode;
  meta?: ReactNode;
}) {
  return (
    <header className="border-b border-line bg-ink-950 pt-9 pb-7">
      <Container>
        <Eyebrow>{eyebrow}</Eyebrow>
        <div className="mt-3 flex flex-wrap items-end justify-between gap-5">
          <div className="max-w-[820px]">
            <h1 className="font-display text-[34px] leading-[1.12] font-semibold tracking-[-0.01em] text-fg">
              {title}
            </h1>
            {lede ? (
              <p className="mt-3 max-w-[760px] text-[13.5px] leading-[22px] text-fg-2">
                {lede}
              </p>
            ) : null}
          </div>
          <div className="flex flex-col items-end gap-2">
            {actions ? <div className="flex gap-2">{actions}</div> : null}
            {meta}
          </div>
        </div>
      </Container>
    </header>
  );
}

export function Section({
  eyebrow,
  title,
  lede,
  right,
  children,
  className = "",
}: {
  eyebrow?: string;
  title?: string;
  lede?: ReactNode;
  right?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`py-8 ${className}`}>
      <Container>
        {(eyebrow || title) && (
          <div className="mb-4 flex items-end justify-between gap-6">
            <div>
              {eyebrow ? <Eyebrow>{eyebrow}</Eyebrow> : null}
              {title ? (
                <h2 className="font-display mt-2 text-[21px] font-semibold tracking-tight text-fg">
                  {title}
                </h2>
              ) : null}
              {lede ? (
                <p className="mt-1.5 max-w-[820px] text-[12.5px] leading-[19px] text-fg-2">
                  {lede}
                </p>
              ) : null}
            </div>
            {right ? <div className="shrink-0">{right}</div> : null}
          </div>
        )}
        {children}
      </Container>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* primitives                                                          */
/* ------------------------------------------------------------------ */

export function Tag({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "accent" | "ok" | "warn" | "bad" | "violet";
}) {
  const tones: Record<string, string> = {
    neutral: "border-line text-dim",
    accent: "border-accent/45 text-accent",
    ok: "border-ok/45 text-ok",
    warn: "border-warn/45 text-warn",
    bad: "border-bad/45 text-bad",
    violet: "border-violet/45 text-violet",
  };
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-sm border px-1.5 py-[2px] font-mono text-[9px] tracking-[0.1em] uppercase ${tones[tone]}`}
    >
      {children}
    </span>
  );
}

export function Button({
  href,
  onClick,
  children,
  variant = "ghost",
  disabled,
  title,
}: {
  href?: string;
  onClick?: () => void;
  children: ReactNode;
  variant?: "primary" | "ghost";
  disabled?: boolean;
  title?: string;
}) {
  const base =
    "inline-flex h-9 items-center gap-2 rounded-sm px-4 text-[11.5px] font-bold tracking-[0.12em] uppercase transition duration-200 ease-[cubic-bezier(.16,1,.3,1)] hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-55 disabled:hover:translate-y-0";
  const styles =
    variant === "primary"
      ? "border border-accent/70 bg-accent/15 text-accent hover:bg-accent/25"
      : "border border-line bg-ink-900 text-fg-2 hover:border-ink-600 hover:text-fg";

  if (href) {
    return (
      <Link href={href} className={`${base} ${styles}`} title={title}>
        {children}
      </Link>
    );
  }
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={title}
      className={`${base} ${styles}`}
    >
      {children}
    </button>
  );
}

export function StatTile({
  label,
  value,
  sub,
  tone,
  source,
}: {
  label: string;
  value: ReactNode;
  sub?: string;
  tone?: string;
  source?: string;
}) {
  return (
    <div
      className="lift border border-line bg-ink-900 px-3.5 py-3"
      title={source}
    >
      <div className="text-[9.5px] font-semibold tracking-[0.16em] text-dim uppercase">
        {label}
      </div>
      <div
        className="mt-1 font-mono text-[26px] leading-8 font-bold"
        style={tone ? { color: tone } : undefined}
      >
        {value}
      </div>
      {sub ? (
        <div className="mt-0.5 text-[10px] leading-[14px] text-dim">{sub}</div>
      ) : null}
    </div>
  );
}

export function Terminal({
  title,
  lines,
  className = "",
}: {
  title: string;
  lines: string[];
  className?: string;
}) {
  return (
    <div
      className={`overflow-hidden rounded-md border border-line bg-ink-900 ${className}`}
    >
      <div className="flex items-center gap-2 border-b border-line bg-ink-850 px-3 py-1.5">
        <span className="h-2 w-2 rounded-full bg-bad/70" />
        <span className="h-2 w-2 rounded-full bg-warn/70" />
        <span className="h-2 w-2 rounded-full bg-ok/70" />
        <span className="ml-1 font-mono text-[10px] text-dim">{title}</span>
      </div>
      <div className="space-y-1.5 px-3.5 py-3 font-mono text-[11.5px] leading-[17px]">
        <div className="text-fg">
          <span className="mr-2 text-ok">$</span>
          {title}
        </div>
        {lines.map((l, i) => (
          <div key={i} className="text-fg-2">
            <span className="mr-2 text-dim">→</span>
            {l}
          </div>
        ))}
      </div>
    </div>
  );
}

export function ModuleCard({
  n,
  title,
  href,
  desc,
  tags,
}: {
  n: string;
  title: string;
  href: string;
  desc: string;
  tags: string[];
}) {
  return (
    <Link
      href={href}
      className="lift group flex flex-col border border-line bg-ink-900 p-5 hover:border-accent/50"
    >
      <div className="flex items-center justify-between">
        <span className="font-mono text-[11px] tracking-[0.2em] text-accent">
          MODULE {n}
        </span>
        <span className="text-[16px] text-dim transition group-hover:translate-x-0.5 group-hover:text-accent">
          →
        </span>
      </div>
      <h3 className="mt-3 text-[16.5px] font-bold text-fg">{title}</h3>
      <p className="mt-2 flex-1 text-[12px] leading-[19px] text-fg-2">{desc}</p>
      <div className="mt-3.5 flex flex-wrap gap-1.5">
        {tags.map((t) => (
          <Tag key={t}>{t}</Tag>
        ))}
      </div>
    </Link>
  );
}

export function Bar({
  value,
  max,
  tone = "var(--color-accent)",
  height = 8,
}: {
  value: number;
  max: number;
  tone?: string;
  height?: number;
}) {
  const pct = max > 0 ? Math.max(0, Math.min(100, (value / max) * 100)) : 0;
  return (
    <div
      className="w-full border border-line bg-ink-850"
      style={{ height }}
      role="presentation"
    >
      <div
        className="h-full transition-[width] duration-500"
        style={{ width: `${pct}%`, background: tone, opacity: 0.9 }}
      />
    </div>
  );
}

export function Segmented({
  options,
  value,
  onChange,
}: {
  options: { key: string; label: string; count?: number }[];
  value: string;
  onChange: (k: string) => void;
}) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {options.map((o) => {
        const active = o.key === value;
        return (
          <button
            key={o.key}
            type="button"
            onClick={() => onChange(o.key)}
            className={`rounded-sm border px-3 py-1.5 text-[10.5px] font-semibold tracking-[0.1em] uppercase transition ${
              active
                ? "border-accent/70 bg-accent/15 text-accent"
                : "border-line bg-ink-900 text-fg-2 hover:border-ink-600 hover:text-fg"
            }`}
          >
            {o.label}
            {o.count !== undefined ? (
              <span className="ml-1.5 font-mono opacity-70">{o.count}</span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}

export function Card({
  title,
  right,
  children,
  className = "",
  bodyClass = "",
}: {
  title?: string;
  right?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClass?: string;
}) {
  return (
    <section
      className={`flex min-w-0 flex-col border border-line bg-ink-900 ${className}`}
    >
      {title ? (
        <header className="flex h-9 shrink-0 items-center justify-between gap-2 border-b border-line bg-ink-850 px-3">
          <h3 className="label truncate">{title}</h3>
          {right ? <div className="shrink-0">{right}</div> : null}
        </header>
      ) : null}
      <div className={`min-h-0 flex-1 p-3.5 ${bodyClass}`}>{children}</div>
    </section>
  );
}

/**
 * Gives a fixed-height column to a Panel/Card child that does not accept a
 * className prop: the wrapper is a flex column and the direct <section>
 * stretches to fill it.
 */
export function Fill({
  className = "h-[620px]",
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  return (
    <div className={`flex min-w-0 flex-col ${className} [&>section]:flex-1`}>
      {children}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* states                                                              */
/* ------------------------------------------------------------------ */

export function Loading({ what }: { what: string }) {
  return (
    <div className="flex min-h-[340px] items-center justify-center">
      <div className="text-center">
        <div className="pulse-dot mx-auto mb-3 h-2.5 w-2.5 rounded-full bg-accent" />
        <div className="text-[10.5px] font-bold tracking-[0.24em] text-fg-2 uppercase">
          Loading
        </div>
        <div className="mt-1 font-mono text-[11px] text-dim">{what}</div>
      </div>
    </div>
  );
}

export function ErrorNote({ what, message }: { what: string; message: string }) {
  return (
    <div className="mx-auto my-16 max-w-[640px] border border-bad/50 bg-bad/10 p-6">
      <div className="text-[11px] font-bold tracking-[0.2em] text-bad uppercase">
        Could not load {what}
      </div>
      <p className="mt-2 font-mono text-[11.5px] text-fg-2">{message}</p>
      <p className="mt-3 text-[11px] text-dim">
        The console reads repository artifacts at runtime — make sure the dev
        server is running from the repository root (npm run dev in frontend/).
      </p>
    </div>
  );
}
