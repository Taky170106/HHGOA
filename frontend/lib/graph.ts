/**
 * Graph construction and layout for the investigation canvas.
 *
 * Nodes and edges come straight from `graph_evidence` in the case file — the
 * TigerGraph-derived record. Nothing is added: a node exists only if the case
 * file names it (in `entities` or on an edge), and an edge exists only if the
 * file lists it. Positions are purely presentational.
 */

import type { CaseFile, GraphEdge } from "./types";

export interface GNode {
  id: string;
  type: string;
  x: number;
  y: number;
  w: number;
  h: number;
  shape: "rect" | "round" | "pill" | "circle" | "ellipse" | "hex" | "double";
}

export interface GEdge {
  id: string;
  edge: string;
  from: string;
  to: string;
}

const VERTEX_TYPES = new Set([
  "BenchmarkCase",
  "Transaction",
  "Card",
  "Customer",
  "DeviceProfile",
  "EmailDomain",
  "BillingRegion",
  "ClosedCase",
]);

const SHAPE: Record<string, GNode["shape"]> = {
  BenchmarkCase: "round",
  Transaction: "rect",
  Card: "round",
  Customer: "circle",
  ClosedCase: "double",
  DeviceProfile: "hex",
  EmailDomain: "ellipse",
  BillingRegion: "pill",
};

const SIZE: Record<string, [number, number]> = {
  BenchmarkCase: [154, 52],
  Transaction: [138, 46],
  Card: [138, 46],
  Customer: [74, 74],
  ClosedCase: [128, 46],
  DeviceProfile: [156, 46],
  EmailDomain: [144, 46],
  BillingRegion: [134, 46],
};

/* presentational anchors — left→right flow: case → transaction → card → customer */
const ANCHORS: Record<string, [number, number][]> = {
  BenchmarkCase: [[-430, -230]],
  DeviceProfile: [[-430, -110]],
  EmailDomain: [[-430, 10]],
  BillingRegion: [[0, -175]],
  Card: [[0, 155]],
  Customer: [[0, 305]],
  ClosedCase: [
    [440, -200],
    [440, -105],
    [440, -10],
    [440, 85],
    [440, 180],
    [440, 275],
    [440, 370],
  ],
  Transaction: [],
};

function sizeOf(type: string): [number, number] {
  return SIZE[type] ?? [130, 44];
}

/** Build nodes + edges for one case, with deterministic positions. */
export function buildGraph(cf: CaseFile): { nodes: GNode[]; edges: GEdge[] } {
  const ge = cf.graph_evidence;
  const raw: GraphEdge[] = ge.edges ?? [];

  const types = new Map<string, string>();

  const register = (id: string, type: string) => {
    if (!id) return;
    const prev = types.get(id);
    if (!prev || prev === "Transaction" || prev === "ClosedCase") {
      if (!prev) types.set(id, type);
    }
  };

  for (const e of raw) {
    register(e.from, e.from_type);
    register(e.to, e.to_type);
  }

  // entities named by the case but carrying no edge in this view
  for (const [key, ids] of Object.entries(ge.entities ?? {})) {
    const type = key === "connected_card_ids" ? "Card" : key;
    if (!VERTEX_TYPES.has(type)) continue;
    for (const id of ids ?? []) register(id, type);
  }

  const flagged =
    cf.case.first_suspicious_txn_id ||
    (ge.entities?.Transaction?.[0] ?? "");

  // ---- positions -------------------------------------------------------
  const pos = new Map<string, { x: number; y: number }>();
  const placedByType = new Map<string, number>();

  const slotsFor = (type: string, id: string): [number, number][] => {
    if (type === "Transaction") return []; // handled explicitly
    const base = ANCHORS[type];
    if (base && base.length) return base;
    return [];
  };

  const place = (id: string, type: string) => {
    if (pos.has(id)) return;
    const slots = slotsFor(type, id);
    const idx = placedByType.get(type) ?? 0;
    if (slots.length > 0 && idx < slots.length) {
      pos.set(id, { x: slots[idx][0], y: slots[idx][1] });
      placedByType.set(type, idx + 1);
    } else {
      // overflow: continue downward in a fresh column for that type
      const col = ANCHORS[type]?.[0]?.[0] ?? 640;
      const startY = ANCHORS[type]?.[0]?.[1] ?? -260;
      pos.set(id, { x: col, y: startY + (idx + 1) * 100 });
      placedByType.set(type, idx + 1);
    }
  };

  // flagged transaction at the centre
  if (flagged) {
    types.set(flagged, types.get(flagged) ?? "Transaction");
    pos.set(flagged, { x: 0, y: 0 });
  }

  // its immediate neighbours from NEXT edges sit on the same axis
  for (const e of raw) {
    if (e.edge !== "NEXT") continue;
    if (e.to === flagged && !pos.has(e.from)) pos.set(e.from, { x: -245, y: 0 });
    if (e.from === flagged && !pos.has(e.to)) pos.set(e.to, { x: 245, y: 0 });
  }

  // deterministic order for everything else: by edge order, then id
  const ordered = [...types.entries()].sort((a, b) => {
    if (pos.has(a[0]) !== pos.has(b[0])) return pos.has(a[0]) ? -1 : 1;
    return a[0].localeCompare(b[0]);
  });
  for (const [id, type] of ordered) place(id, type);

  const nodes: GNode[] = [...types.entries()].map(([id, type]) => {
    const [w, h] = sizeOf(type);
    const p = pos.get(id) ?? { x: 640, y: -260 };
    return { id, type, x: p.x, y: p.y, w, h, shape: SHAPE[type] ?? "rect" };
  });

  const edges: GEdge[] = raw.map((e, i) => ({
    id: `${e.edge}-${e.from}-${e.to}-${i}`,
    edge: e.edge,
    from: e.from,
    to: e.to,
  }));

  return { nodes, edges };
}

export function graphBounds(nodes: GNode[]) {
  if (!nodes.length) return { minX: -400, minY: -250, maxX: 400, maxY: 250 };
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const n of nodes) {
    minX = Math.min(minX, n.x - n.w / 2);
    maxX = Math.max(maxX, n.x + n.w / 2);
    minY = Math.min(minY, n.y - n.h / 2);
    maxY = Math.max(maxY, n.y + n.h / 2);
  }
  return { minX, minY, maxX, maxY };
}

export const NODE_COLOR: Record<string, string> = {
  BenchmarkCase: "#f59e0b",
  Transaction: "#38bdf8",
  Card: "#a78bfa",
  Customer: "#34d399",
  ClosedCase: "#94a3b8",
  DeviceProfile: "#fb7185",
  EmailDomain: "#f472b6",
  BillingRegion: "#facc15",
};

export const NODE_GLYPH: Record<string, string> = {
  BenchmarkCase: "◆",
  Transaction: "▤",
  Card: "▣",
  Customer: "●",
  ClosedCase: "◈",
  DeviceProfile: "⬡",
  EmailDomain: "✉",
  BillingRegion: "▦",
};
