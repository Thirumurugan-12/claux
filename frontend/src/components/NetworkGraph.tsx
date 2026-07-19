import { GraphData } from "../api";

// A lightweight SVG co-offending graph. P20 upgrades this to Cytoscape.js with proper
// layout + role colouring; here a deterministic radial layout (seed at centre) is enough to
// make the chat→network linkage visible without pulling in a graph library.

const W = 460;
const H = 380;

export default function NetworkGraph({ graph }: { graph: GraphData }) {
  const nodes = graph.nodes.slice(0, 40);
  const ids = nodes.map((n) => n.data.id);
  const idSet = new Set(ids);
  const seedId = graph.seed != null ? String(graph.seed) : ids[0];

  const cx = W / 2;
  const cy = H / 2;
  const R = Math.min(W, H) / 2 - 46;
  const pos = new Map<string, { x: number; y: number }>();
  const ring = nodes.filter((n) => n.data.id !== seedId);
  ring.forEach((n, i) => {
    const a = (2 * Math.PI * i) / Math.max(ring.length, 1) - Math.PI / 2;
    pos.set(n.data.id, { x: cx + R * Math.cos(a), y: cy + R * Math.sin(a) });
  });
  pos.set(seedId, { x: cx, y: cy });

  const maxFirs = Math.max(1, ...nodes.map((n) => n.data.firs ?? 1));
  const radius = (firs?: number) => 6 + 10 * Math.sqrt((firs ?? 1) / maxFirs);

  return (
    <div className="viz-wrap">
      <div className="viz-meta">
        {graph.title} — {graph.nodes.length} people, {graph.edges.length} co-offending links
        {graph.nodes.length > nodes.length && ` (showing ${nodes.length})`}
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="co-offending network">
        {graph.edges.map((e, i) => {
          const a = pos.get(e.data.source);
          const b = pos.get(e.data.target);
          if (!a || !b || !idSet.has(e.data.source) || !idSet.has(e.data.target)) return null;
          return (
            <line
              key={i}
              className="edge"
              x1={a.x}
              y1={a.y}
              x2={b.x}
              y2={b.y}
              strokeWidth={Math.min(4, e.data.weight ?? 1)}
            />
          );
        })}
        {nodes.map((n) => {
          const p = pos.get(n.data.id)!;
          const isSeed = n.data.id === seedId;
          return (
            <g key={n.data.id}>
              <circle className={`node${isSeed ? " seed" : ""}`} cx={p.x} cy={p.y} r={radius(n.data.firs)} strokeWidth={1.5} />
              <text className="node-label" x={p.x} y={p.y - radius(n.data.firs) - 3} textAnchor="middle">
                {(n.data.label ?? n.data.id).slice(0, 16)}
              </text>
            </g>
          );
        })}
      </svg>
      <div className="legend">
        <span className="k"><span className="sw" style={{ background: "var(--accent)" }} />focus person</span>
        <span className="k"><span className="sw" style={{ background: "var(--accent-dim)" }} />co-offender</span>
        <span className="k">node size = linked FIRs</span>
      </div>
    </div>
  );
}
