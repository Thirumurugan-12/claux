// HTTP client for the KSP backend. The frontend calls /api/* which the Vite proxy (dev) or the
// deploy rewrites to the backend. The request/response wire behaviour here is intentionally
// identical to the backend contract — reorganise freely, but do not change what goes on the wire.

import type { CaseData, ChatMessage, DemoRole, Principal, StreamEvent } from "./types";

/** Thrown when the backend has no LLM configured (503) — surfaced as an actionable banner. */
export const LLM_NOT_CONFIGURED =
  "LLM not configured. Set UNIAI_BASE_URL / UNIAI_API_KEY / UNIAI_MODEL on the backend " +
  "(Catalyst QuickML LLM Serving) to enable chat.";

export async function fetchDemoRoles(): Promise<DemoRole[]> {
  const r = await fetch("/api/demo/principals");
  if (!r.ok) throw new Error(`principals ${r.status}`);
  return (await r.json()).roles as DemoRole[];
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

/** Stream a chat turn, invoking `onEvent` for each SSE event. Resolves when the stream ends. */
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
  if (resp.status === 503) throw new Error(LLM_NOT_CONFIGURED);
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
