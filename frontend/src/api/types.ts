// Wire types for the KSP chat backend (P14).
//
// These mirror the backend contract exactly and must not drift: the request/response JSON
// shapes and SSE event names are what the backend depends on. Presentation code narrows the
// loosely-typed `data` payloads through the guards in `extract.ts` rather than widening here.

export type Role = "sho" | "dysp" | "sp" | "scrb_analyst" | "policymaker";

export interface Principal {
  name: string;
  role: Role;
  unit_id?: number | null;
  district_id?: number | null;
}

export interface DemoRole {
  role: Role;
  label: string;
  scope: string;
  principal: Principal;
}

/** The backend returns tool payloads with a tool-specific shape; treated as opaque here. */
export type ToolData = Record<string, unknown>;

export interface ToolCall {
  tool: string;
  params?: Record<string, unknown>;
  ok: boolean;
  crime_nos: string[];
  row_ids: number[];
  error?: string | null;
  data?: ToolData;
}

/** Minimal text-only turn used to carry multi-turn context back to the backend. */
export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export type StreamEvent =
  | { type: "thinking"; text: string }
  | {
      type: "tool_call";
      tool: string;
      ok: boolean;
      crime_nos: string[];
      row_ids: number[];
      error?: string | null;
      params?: Record<string, unknown>;
      data?: ToolData;
    }
  | { type: "result"; answer: string; crime_nos: string[]; row_ids: number[]; rounds: number };

export interface Provenance {
  sql_hash: string;
  row_ids: number[];
  crime_nos: string[];
}

export interface CaseData {
  data: CaseRecord;
  provenance: Provenance;
}

/** The subset of a FIR record the case drawer renders. All fields are best-effort. */
export interface CaseRecord {
  case_master_id?: number;
  registered?: string;
  station?: string;
  district_id?: number;
  heinous?: boolean;
  chargesheet?: { cs_type?: string } | null;
  sections?: string[];
  accused?: AccusedRef[];
  victims?: { name: string }[];
}

export interface AccusedRef {
  name: string;
  person_cluster_id?: number | null;
  resolution_confidence?: number | null;
}

// --- pane data (derived from tool results) ----------------------------------

export interface GraphNode {
  data: { id: string; label?: string; firs?: number; person_cluster_id?: number };
}

export interface GraphEdge {
  data: { source: string; target: string; weight?: number };
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  seed?: number;
  title: string;
}

export interface Hotspot {
  hotspot_id: number;
  size: number;
  center_lat: number;
  center_lon: number;
}

export interface GeoCoverage {
  total_cases: number;
  precise: number;
  inferred_centroid_only: number;
  precise_pct: number;
}

export interface GeoData {
  hotspots: Hotspot[];
  coverage: GeoCoverage;
  title: string;
}
