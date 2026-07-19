import { MAP } from "../../lib/constants";
import { count } from "../../lib/format";
import type { GeoData } from "../../api";

const { width: W, height: H, maxHotspots: MAX_HOTSPOTS, bbox } = MAP;
const GRID = [0.2, 0.4, 0.6, 0.8];

export function HotspotMap({ geo }: { geo: GeoData }) {
  const { hotspots, coverage } = geo;
  const maxSize = Math.max(1, ...hotspots.map((h) => h.size));
  const px = (lon: number) => 20 + ((lon - bbox.lon0) / (bbox.lon1 - bbox.lon0)) * (W - 40);
  const py = (lat: number) => H - 20 - ((lat - bbox.lat0) / (bbox.lat1 - bbox.lat0)) * (H - 40);

  return (
    <div className="viz">
      <p className="viz-meta">
        {geo.title} — <b>{hotspots.length}</b> clusters over precise-coordinate cases
      </p>

      <svg className="viz-svg" viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="crime hotspots">
        <rect className="map-frame" x={10} y={10} width={W - 20} height={H - 20} rx={6} />
        {GRID.map((f, i) => (
          <line
            key={`v${i}`}
            className="map-grid"
            x1={20 + f * (W - 40)}
            y1={12}
            x2={20 + f * (W - 40)}
            y2={H - 12}
          />
        ))}
        {GRID.map((f, i) => (
          <line
            key={`h${i}`}
            className="map-grid"
            x1={12}
            y1={20 + f * (H - 40)}
            x2={W - 12}
            y2={20 + f * (H - 40)}
          />
        ))}
        {hotspots.slice(0, MAX_HOTSPOTS).map((h) => (
          <circle
            key={h.hotspot_id}
            className="map-hotspot"
            cx={px(h.center_lon)}
            cy={py(h.center_lat)}
            r={4 + 14 * Math.sqrt(h.size / maxSize)}
          >
            <title>{`hotspot #${h.hotspot_id}: ${h.size} cases`}</title>
          </circle>
        ))}
      </svg>

      <div className="legend">
        <span className="legend-key">
          <span className="legend-swatch swatch-heat" />
          hotspot (size = case count)
        </span>
      </div>

      <p className="prov-note">
        Honest coverage: {count(coverage.precise)} of {count(coverage.total_cases)} cases (
        {coverage.precise_pct}%) carry precise coordinates and are clustered here. The other{" "}
        {count(coverage.inferred_centroid_only)} have no coordinates and are placed at their district
        centroid, <b>not</b> shown as points — an inferred location is never drawn as if it were precise.
      </p>
    </div>
  );
}
