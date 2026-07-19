import { useMemo } from "react";
import { extractGeo, extractGraph } from "../api";
import type { GeoData, GraphData, ToolCall } from "../api";

/** Derives the first available network graph and hotspot geography from a set of tool calls. */
export function usePaneData(toolCalls: ToolCall[]): { graph: GraphData | null; geo: GeoData | null } {
  return useMemo(() => {
    let graph: GraphData | null = null;
    let geo: GeoData | null = null;
    for (const tc of toolCalls) {
      graph = graph ?? extractGraph(tc);
      geo = geo ?? extractGeo(tc);
    }
    return { graph, geo };
  }, [toolCalls]);
}
