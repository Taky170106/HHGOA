"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  NODE_COLOR,
  NODE_GLYPH,
  graphBounds,
  type GEdge,
  type GNode,
} from "@/lib/graph";

interface View {
  s: number;
  tx: number;
  ty: number;
}

const clamp = (v: number, lo: number, hi: number) =>
  Math.max(lo, Math.min(hi, v));

/** axis-aligned box border crossing for a centre→centre segment */
function edgeEnds(a: GNode, b: GNode) {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const len = Math.hypot(dx, dy) || 1;
  const ux = dx / len;
  const uy = dy / len;
  const cut = (n: GNode) => {
    const hw = n.w / 2;
    const hh = n.h / 2;
    const t = Math.min(
      Math.abs(hw / (ux || 1e-6)),
      Math.abs(hh / (uy || 1e-6)),
    );
    return { x: n.x + ux * t, y: n.y + uy * t };
  };
  return { p0: cut(a), p1: cut(b) };
}

function hexPoints(w: number, h: number) {
  const x = w / 2;
  const y = h / 2;
  const c = x * 0.32;
  return [
    `${-x + c},${-y}`,
    `${x - c},${-y}`,
    `${x},0`,
    `${x - c},${y}`,
    `${-x + c},${y}`,
    `${-x},0`,
  ].join(" ");
}

export default function GraphCanvas({
  nodes,
  edges,
  selected,
  onSelect,
}: {
  nodes: GNode[];
  edges: GEdge[];
  selected: string | null;
  onSelect: (id: string | null) => void;
}) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const [view, setView] = useState<View>({ s: 1, tx: 0, ty: 0 });
  const [hover, setHover] = useState<string | null>(null);
  const [panning, setPanning] = useState(false);
  const pan = useRef<{ px: number; py: number; tx: number; ty: number } | null>(
    null,
  );

  const byId = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes]);

  const fit = useCallback(() => {
    const el = wrapRef.current;
    if (!el || !nodes.length) return;
    const W = el.clientWidth;
    const H = el.clientHeight;
    const b = graphBounds(nodes);
    const pad = 56;
    const bw = Math.max(1, b.maxX - b.minX);
    const bh = Math.max(1, b.maxY - b.minY);
    const s = clamp(Math.min((W - pad * 2) / bw, (H - pad * 2) / bh), 0.2, 1.5);
    const cx = (b.minX + b.maxX) / 2;
    const cy = (b.minY + b.maxY) / 2;
    setView({ s, tx: W / 2 - cx * s, ty: H / 2 - cy * s });
  }, [nodes]);

  useEffect(() => {
    fit();
  }, [fit]);

  useEffect(() => {
    const onResize = () => fit();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [fit]);

  // wheel zoom about the pointer (needs a non-passive listener)
  useEffect(() => {
    const el = svgRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const rect = el.getBoundingClientRect();
      const px = e.clientX - rect.left;
      const py = e.clientY - rect.top;
      setView((v) => {
        const s2 = clamp(v.s * Math.exp(-e.deltaY * 0.0015), 0.2, 3);
        const wx = (px - v.tx) / v.s;
        const wy = (py - v.ty) / v.s;
        return { s: s2, tx: px - wx * s2, ty: py - wy * s2 };
      });
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, []);

  const onPointerDown = (e: React.PointerEvent) => {
    const target = e.target as Element;
    if (target.closest("[data-node]")) return; // node handles its own click
    pan.current = { px: e.clientX, py: e.clientY, tx: view.tx, ty: view.ty };
    setPanning(true);
    (e.currentTarget as SVGSVGElement).setPointerCapture(e.pointerId);
    onSelect(null);
  };
  const onPointerMove = (e: React.PointerEvent) => {
    const p = pan.current;
    if (!p) return;
    setView((v) => ({
      ...v,
      tx: p.tx + (e.clientX - p.px),
      ty: p.ty + (e.clientY - p.py),
    }));
  };
  const endPan = (e: React.PointerEvent) => {
    if (pan.current) {
      pan.current = null;
      try {
        (e.currentTarget as SVGSVGElement).releasePointerCapture(e.pointerId);
      } catch {
        /* pointer already released */
      }
    }
  };

  const active = hover ?? selected;
  const linked = useMemo(() => {
    if (!active) return null;
    const s = new Set<string>([active]);
    for (const e of edges) {
      if (e.from === active) s.add(e.to);
      if (e.to === active) s.add(e.from);
    }
    return s;
  }, [active, edges]);

  const showLabels = view.s > 0.55 || !!active;

  return (
    <div ref={wrapRef} className="relative h-full w-full overflow-hidden">
      <svg
        ref={svgRef}
        className="h-full w-full touch-none select-none"
        style={{ cursor: panning ? "grabbing" : "grab" }}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endPan}
        onPointerCancel={endPan}
        onPointerLeave={() => setHover(null)}
      >
        <defs>
          <marker
            id="arrow"
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="6"
            markerHeight="6"
            orient="auto-start-reverse"
          >
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#4b6180" />
          </marker>
          <pattern
            id="grid"
            width="34"
            height="34"
            patternUnits="userSpaceOnUse"
          >
            <path
              d="M 34 0 L 0 0 0 34"
              fill="none"
              stroke="#131b26"
              strokeWidth="1"
            />
          </pattern>
        </defs>

        <rect width="100%" height="100%" fill="url(#grid)" />

        <g transform={`translate(${view.tx} ${view.ty}) scale(${view.s})`}>
          {/* edges */}
          {edges.map((e) => {
            const a = byId.get(e.from);
            const b = byId.get(e.to);
            if (!a || !b) return null;
            const { p0, p1 } = edgeEnds(a, b);
            const on = active ? e.from === active || e.to === active : false;
            const mx = (p0.x + p1.x) / 2;
            const my = (p0.y + p1.y) / 2;
            const labelW = e.edge.length * 6 + 12;
            return (
              <g key={e.id} opacity={active ? (on ? 1 : 0.22) : 0.85}>
                <line
                  x1={p0.x}
                  y1={p0.y}
                  x2={p1.x}
                  y2={p1.y}
                  stroke={on ? "#38bdf8" : "#31435c"}
                  strokeWidth={on ? 1.7 : 1.2}
                  markerEnd="url(#arrow)"
                  strokeDasharray={e.edge === "TRIGGERS" ? "5 3" : undefined}
                />
                {showLabels && (
                  <>
                    <rect
                      x={mx - labelW / 2}
                      y={my - 9}
                      width={labelW}
                      height={16}
                      rx={3}
                      fill="#0a0f16"
                      stroke={on ? "#38bdf8" : "#1e2a3a"}
                      strokeWidth="1"
                      opacity={on ? 1 : 0.8}
                    />
                    <text
                      x={mx}
                      y={my + 3}
                      textAnchor="middle"
                      fontSize="9.5"
                      fontFamily="var(--font-mono)"
                      fill={on ? "#9ee0ff" : "#8ea3bd"}
                      letterSpacing="0.06em"
                    >
                      {e.edge}
                    </text>
                  </>
                )}
              </g>
            );
          })}

          {/* nodes */}
          {nodes.map((n) => {
            const color = NODE_COLOR[n.type] ?? "#94a3b8";
            const on = !active || linked?.has(n.id);
            const isSel = selected === n.id;
            const isHov = hover === n.id;
            const halfW = n.w / 2;
            const halfH = n.h / 2;
            return (
              <g
                key={n.id}
                data-node={n.id}
                transform={`translate(${n.x} ${n.y})`}
                opacity={on ? 1 : 0.28}
                style={{ cursor: "pointer" }}
                onPointerDown={(e) => e.stopPropagation()}
                onClick={(e) => {
                  e.stopPropagation();
                  onSelect(isSel ? null : n.id);
                }}
                onPointerEnter={() => setHover(n.id)}
                onPointerLeave={() => setHover((h) => (h === n.id ? null : h))}
              >
                {isSel && (
                  <rect
                    x={-halfW - 7}
                    y={-halfH - 7}
                    width={n.w + 14}
                    height={n.h + 14}
                    rx={8}
                    fill="none"
                    stroke={color}
                    strokeWidth="1"
                    strokeDasharray="3 3"
                    opacity="0.75"
                  />
                )}
                <Shape n={n} color={color} glow={isSel || isHov} />
                <text
                  x={0}
                  y={1}
                  textAnchor="middle"
                  dominantBaseline="middle"
                  fontSize={n.w > 140 ? "11.5" : "10.5"}
                  fontWeight="600"
                  fontFamily="var(--font-mono)"
                  fill="#eaf2ff"
                >
                  {n.id.length > 22 ? `${n.id.slice(0, 21)}…` : n.id}
                </text>
                <text
                  x={0}
                  y={halfH + 13}
                  textAnchor="middle"
                  fontSize="9"
                  letterSpacing="0.1em"
                  fill={color}
                  opacity="0.85"
                  style={{ textTransform: "uppercase" }}
                >
                  {NODE_GLYPH[n.type] ?? "•"} {n.type}
                </text>
              </g>
            );
          })}
        </g>
      </svg>

      {/* legend */}
      <div className="pointer-events-none absolute bottom-2 left-2 flex flex-wrap gap-x-3 gap-y-1 rounded border border-line bg-ink-900/85 px-2.5 py-1.5">
        {Object.entries(NODE_COLOR).map(([type, color]) => (
          <span
            key={type}
            className="flex items-center gap-1.5 text-[9.5px] tracking-wide text-fg-2"
          >
            <span
              className="inline-block h-2 w-2 rounded-sm"
              style={{ background: color }}
            />
            {type}
          </span>
        ))}
      </div>

      {/* zoom controls */}
      <div className="absolute right-2 bottom-2 flex overflow-hidden rounded border border-line bg-ink-900/90">
        {[
          ["−", () => setView((v) => ({ ...v, s: clamp(v.s / 1.2, 0.2, 3) }))],
          ["+", () => setView((v) => ({ ...v, s: clamp(v.s * 1.2, 0.2, 3) }))],
          ["⤢", fit],
        ].map(([label, fn], i) => (
          <button
            key={i}
            type="button"
            onClick={fn as () => void}
            className="h-7 w-8 border-l border-line text-[13px] text-fg-2 first:border-l-0 hover:bg-ink-700 hover:text-fg"
          >
            {label as string}
          </button>
        ))}
      </div>

      <div className="pointer-events-none absolute top-2 left-2 rounded border border-line bg-ink-900/85 px-2 py-1 text-[10px] font-mono text-dim">
        zoom {view.s.toFixed(2)}× · {nodes.length} nodes · {edges.length} edges
        {active ? ` · focus ${active}` : ""}
      </div>
    </div>
  );
}

function Shape({
  n,
  color,
  glow,
}: {
  n: GNode;
  color: string;
  glow: boolean;
}) {
  const hw = n.w / 2;
  const hh = n.h / 2;
  const common = {
    fill: color,
    fillOpacity: glow ? 0.34 : 0.18,
    stroke: color,
    strokeWidth: glow ? 2.2 : 1.4,
  };
  switch (n.shape) {
    case "circle":
      return <circle r={hh} {...common} />;
    case "ellipse":
      return <ellipse rx={hw} ry={hh} {...common} />;
    case "hex":
      return <polygon points={hexPoints(n.w, n.h)} {...common} />;
    case "pill":
      return <rect x={-hw} y={-hh} width={n.w} height={n.h} rx={hh} {...common} />;
    case "double":
      return (
        <>
          <rect x={-hw} y={-hh} width={n.w} height={n.h} rx={4} {...common} />
          <rect
            x={-hw + 4}
            y={-hh + 4}
            width={n.w - 8}
            height={n.h - 8}
            rx={2}
            fill="none"
            stroke={color}
            strokeWidth="1"
            opacity="0.7"
          />
        </>
      );
    case "round":
      return <rect x={-hw} y={-hh} width={n.w} height={n.h} rx={7} {...common} />;
    default:
      return <rect x={-hw} y={-hh} width={n.w} height={n.h} rx={2} {...common} />;
  }
}
