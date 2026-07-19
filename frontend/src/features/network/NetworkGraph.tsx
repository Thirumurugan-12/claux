import { useMemo } from "react";
import { GRAPH } from "../../lib/constants";
import type { GraphData } from "../../api";

const { width: W, height: H, maxNodes: MAX_NODES } = GRAPH;

interface Point {
  x: number;
  y: number;
}

/** Deterministic radial layout: the focus person at the centre, co-offenders on a ring. */
function useLayout(graph: GraphData) {
  return useMemo(() => {
    const nodes = graph.nodes.slice(0, MAX_NODES);
    const ids = new Set(nodes.map((n) => n.data.id));
    const seedId = graph.seed != null ? String(graph.seed) : nodes[0]?.data.id;

    const cx = W / 2;
    const cy = H / 2;
    const radius = Math.min(W, H) / 2 - 46;
    const pos = new Map<string, Point>();

    const ring = nodes.filter((n) => n.data.id !== seedId);
    ring.forEach((n, i) => {
      const angle = (2 * Math.PI * i) / Math.max(ring.length, 1) - Math.PI / 2;
      pos.set(n.data.id, { x: cx + radius * Math.cos(angle), y: cy + radius * Math.sin(angle) });
    });
    if (seedId) pos.set(seedId, { x: cx, y: cy });

    const maxFirs = Math.max(1, ...nodes.map((n) => n.data.firs ?? 1));
    const maxWeight = Math.max(1, ...graph.edges.map((e) => e.data.weight ?? 1));

    return { nodes, ids, seedId, pos, maxFirs, maxWeight };
  }, [graph]);
}

export function NetworkGraph({ graph }: { graph: GraphData }) {
  const { nodes, ids, seedId, pos, maxFirs, maxWeight } = useLayout(graph);
  const nodeRadius = (firs?: number) => 6 + 10 * Math.sqrt((firs ?? 1) / maxFirs);

  return (
    <div className="viz">
      <p className="viz-meta">
        {graph.title} — <b>{graph.nodes.length}</b> people, <b>{graph.edges.length}</b> co-offending links
        {graph.nodes.length > nodes.length && ` (showing ${nodes.length})`}
      </p>

      <svg
        className="viz-svg"
        viewBox={`0 0 ${W} ${H}`}
        width="100%"
        role="img"
        aria-label="co-offending network"
      >
        {graph.edges.map((e, i) => {
          const a = pos.get(e.data.source);
          const b = pos.get(e.data.target);
          if (!a || !b || !ids.has(e.data.source) || !ids.has(e.data.target)) return null;
          const weight = e.data.weight ?? 1;
          return (
            <line
              key={i}
              className="graph-edge"
              x1={a.x}
              y1={a.y}
              x2={b.x}
              y2={b.y}
              strokeWidth={Math.min(4, 1 + weight * 0.6)}
              strokeOpacity={0.3 + 0.5 * (weight / maxWeight)}
            />
          );
        })}

        {nodes.map((n) => {
          const p = pos.get(n.data.id);
          if (!p) return null;
          const isSeed = n.data.id === seedId;
          const r = nodeRadius(n.data.firs);
          return (
            <g key={n.data.id}>
              <circle className={isSeed ? "graph-node seed" : "graph-node"} cx={p.x} cy={p.y} r={r}>
                <title>{`${n.data.label ?? n.data.id} — ${n.data.firs ?? 1} linked FIRs`}</title>
              </circle>
              <text className="graph-label" x={p.x} y={p.y - r - 4} textAnchor="middle">
                {(n.data.label ?? n.data.id).slice(0, 16)}
              </text>
            </g>
          );
        })}
      </svg>

      <div className="legend">
        <span className="legend-key">
          <span className="legend-swatch swatch-accent" />
          focus person
        </span>
        <span className="legend-key">
          <span className="legend-swatch swatch-info" />
          co-offender
        </span>
        <span className="legend-key">node size = linked FIRs · line = shared cases</span>
      </div>
    </div>
  );
}
