// Derive renderable pane data (network graph, hotspot geography) from a tool result.
//
// Tool payloads are opaque (`ToolData`), so this module owns the narrowing: it is the single
// place that knows the internal shape of specific tools' `data`. Everything downstream consumes
// the typed GraphData / GeoData.

import type { GeoData, GraphData, ToolCall, ToolData } from "./types";

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null ? (value as Record<string, unknown>) : null;
}

/** A record is graph-like if it carries a `nodes` array under `graph`. */
function readGraph(container: Record<string, unknown> | null): GraphData | null {
  const graph = asRecord(container?.graph);
  if (graph && Array.isArray(graph.nodes)) return graph as unknown as GraphData;
  return null;
}

/** Pull a renderable co-offending network out of a tool result, if present. */
export function extractGraph(tc: ToolCall): GraphData | null {
  const data: ToolData | undefined = tc.data;
  if (!data) return null;

  if (tc.tool === "get_person_network" || tc.tool === "find_shortest_path") {
    const graph = readGraph(data);
    if (graph) return { ...graph, seed: data.seed as number | undefined, title: tc.tool.replace(/_/g, " ") };
  }

  if (tc.tool === "detect_communities" && Array.isArray(data.communities) && data.communities.length) {
    const first = asRecord(data.communities[0]);
    const graph = readGraph(first);
    if (graph) return { ...graph, title: `largest community (${first?.size} people)` };
  }

  return null;
}

/** Pull hotspot geography out of a tool result, if present. */
export function extractGeo(tc: ToolCall): GeoData | null {
  const data: ToolData | undefined = tc.data;
  if (tc.tool === "hotspot_scan" && data && Array.isArray(data.hotspots)) {
    return {
      hotspots: data.hotspots as GeoData["hotspots"],
      coverage: data.coverage as GeoData["coverage"],
      title: "crime hotspots",
    };
  }
  return null;
}
