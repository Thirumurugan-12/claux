import { GeoData } from "../api";

// A lightweight SVG plot of hotspot centres over a Karnataka-ish bounding box. P20 upgrades
// this to MapLibre + deck.gl with real district boundaries; here the point is to show the
// hotspots the query returned AND the geo-honesty coverage (precise vs centroid-only), which
// the map must never blur.

const W = 460;
const H = 420;
// Rough Karnataka bounding box (lon, lat).
const LON0 = 74.0, LON1 = 78.6, LAT0 = 11.5, LAT1 = 18.6;

export default function HotspotMap({ geo }: { geo: GeoData }) {
  const { hotspots, coverage } = geo;
  const maxSize = Math.max(1, ...hotspots.map((h) => h.size));
  const px = (lon: number) => 20 + ((lon - LON0) / (LON1 - LON0)) * (W - 40);
  const py = (lat: number) => H - 20 - ((lat - LAT0) / (LAT1 - LAT0)) * (H - 40);

  return (
    <div className="viz-wrap">
      <div className="viz-meta">
        {geo.title} — {hotspots.length} clusters over precise-coordinate cases
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="crime hotspots">
        <rect x={1} y={1} width={W - 2} height={H - 2} fill="none" stroke="var(--border)" />
        {hotspots.slice(0, 120).map((h) => (
          <circle
            key={h.hotspot_id}
            className="hot"
            cx={px(h.center_lon)}
            cy={py(h.center_lat)}
            r={4 + 14 * Math.sqrt(h.size / maxSize)}
            strokeWidth={1}
          >
            <title>{`hotspot #${h.hotspot_id}: ${h.size} cases`}</title>
          </circle>
        ))}
      </svg>
      <div className="legend">
        <span className="k"><span className="sw hot" style={{ background: "var(--danger)" }} />hotspot (size = case count)</span>
      </div>
      <p className="prov-note">
        Honest coverage: {coverage.precise.toLocaleString()} of {coverage.total_cases.toLocaleString()} cases
        ({coverage.precise_pct}%) carry precise coordinates and are clustered here. The other{" "}
        {coverage.inferred_centroid_only.toLocaleString()} have no coordinates and are placed at
        their district centroid, <b>not</b> shown as points — an inferred location is never drawn
        as if it were precise.
      </p>
    </div>
  );
}
