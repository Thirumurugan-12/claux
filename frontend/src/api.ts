// API types + client for the KSP chat backend (P14/P19).
// The frontend calls /api/* which the Vite proxy (dev) / the deploy rewrites to the backend.

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

export interface ToolCall {
  tool: string;
  params?: Record<string, unknown>;
  ok: boolean;
  crime_nos: string[];
  row_ids: number[];
  error?: string | null;
  data?: any;
}

// A minimal message for multi-turn context (text-only turns; the backend also accepts the
// full tool-block format, but the shell keeps history simple).
export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export type StreamEvent =
  | { type: "thinking"; text: string }
  | { type: "tool_call"; tool: string; ok: boolean; crime_nos: string[]; row_ids: number[]; error?: string | null; params?: Record<string, unknown>; data?: any }
  | { type: "result"; answer: string; crime_nos: string[]; row_ids: number[]; rounds: number };

export async function fetchDemoRoles(): Promise<DemoRole[]> {
  const r = await fetch("/api/demo/principals");
  if (!r.ok) throw new Error(`principals ${r.status}`);
  return (await r.json()).roles as DemoRole[];
}

export interface CaseData {
  data: any;
  provenance: { sql_hash: string; row_ids: number[]; crime_nos: string[] };
}

export async function fetchCase(
  principal: Principal,
  ref: { crime_no?: string; case_master_id?: number },
): Promise<CaseData> {
  const r = await fetch("/api/case", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ principal, ...ref }),
  });
  if (r.status === 403) throw new Error("Out of your jurisdiction");
  if (!r.ok) throw new Error(`case ${r.status}`);
  return (await r.json()) as CaseData;
}

// Stream a chat turn, invoking onEvent for each SSE event. Resolves when the stream ends.
export async function streamChat(
  principal: Principal,
  message: string,
  history: ChatMessage[],
  onEvent: (e: StreamEvent) => void,
): Promise<void> {
  const resp = await fetch("/api/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ principal, message, history }),
  });
  if (resp.status === 503) {
    throw new Error(
      "LLM not configured. Set UNIAI_BASE_URL / UNIAI_API_KEY / UNIAI_MODEL on the backend " +
        "(Catalyst QuickML LLM Serving) to enable chat.",
    );
  }
  if (!resp.ok || !resp.body) throw new Error(`chat ${resp.status}`);

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() ?? "";
    for (const chunk of chunks) {
      const line = chunk.trim();
      if (!line.startsWith("data:")) continue;
      try {
        onEvent(JSON.parse(line.slice(5).trim()) as StreamEvent);
      } catch {
        // ignore malformed keep-alive fragments
      }
    }
  }
}

// --- pane data extraction ----------------------------------------------------

export interface GraphData {
  nodes: { data: { id: string; label?: string; firs?: number; person_cluster_id?: number } }[];
  edges: { data: { source: string; target: string; weight?: number } }[];
  seed?: number;
  title: string;
}

export interface GeoData {
  hotspots: { hotspot_id: number; size: number; center_lat: number; center_lon: number }[];
  coverage: { total_cases: number; precise: number; inferred_centroid_only: number; precise_pct: number };
  title: string;
}

// Pull a renderable network graph out of a tool result, if present.
export function extractGraph(tc: ToolCall): GraphData | null {
  const d = tc.data;
  if (!d) return null;
  if ((tc.tool === "get_person_network" || tc.tool === "find_shortest_path") && d.graph?.nodes) {
    return { ...d.graph, seed: d.seed, title: tc.tool.replace(/_/g, " ") };
  }
  if (tc.tool === "detect_communities" && Array.isArray(d.communities) && d.communities.length) {
    const c = d.communities[0];
    if (c.graph?.nodes) return { ...c.graph, title: `largest community (${c.size} people)` };
  }
  return null;
}

// Pull hotspot geography out of a tool result, if present.
export function extractGeo(tc: ToolCall): GeoData | null {
  const d = tc.data;
  if (tc.tool === "hotspot_scan" && d?.hotspots) {
    return { hotspots: d.hotspots, coverage: d.coverage, title: "crime hotspots" };
  }
  return null;
}
