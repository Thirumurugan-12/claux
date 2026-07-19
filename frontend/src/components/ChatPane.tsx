import { useEffect, useRef, useState } from "react";
import { ChatMessage, Principal, streamChat, StreamEvent, ToolCall } from "../api";

export interface Turn {
  role: "user" | "assistant";
  text: string;
  toolCalls?: ToolCall[];
}

const SUGGESTIONS = [
  "Who are the most prolific repeat offenders in my jurisdiction?",
  "Show the co-offending network around the top offender.",
  "Where are the crime hotspots?",
  "Which districts are red zones versus their own baseline?",
  "How many Zero FIRs are there and where?",
  "What bank accounts are linked to that person?",
];

export default function ChatPane({
  principal,
  onAnswer,
}: {
  principal: Principal;
  onAnswer: (toolCalls: ToolCall[]) => void;
}) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const history = useRef<ChatMessage[]>([]);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: "smooth" });
  }, [turns, busy]);

  async function send(text: string) {
    const q = text.trim();
    if (!q || busy) return;
    setInput("");
    setError(null);
    setBusy(true);
    setTurns((t) => [...t, { role: "user", text: q }, { role: "assistant", text: "", toolCalls: [] }]);
    const collected: ToolCall[] = [];

    const patchAssistant = (fn: (t: Turn) => Turn) =>
      setTurns((ts) => {
        const copy = ts.slice();
        for (let i = copy.length - 1; i >= 0; i--) {
          if (copy[i].role === "assistant") { copy[i] = fn(copy[i]); break; }
        }
        return copy;
      });

    try {
      await streamChat(principal, q, history.current, (e: StreamEvent) => {
        if (e.type === "tool_call") {
          const tc: ToolCall = {
            tool: e.tool, ok: e.ok, crime_nos: e.crime_nos, row_ids: e.row_ids,
            error: e.error, params: e.params, data: e.data,
          };
          collected.push(tc);
          patchAssistant((t) => ({ ...t, toolCalls: [...(t.toolCalls ?? []), tc] }));
        } else if (e.type === "result") {
          patchAssistant((t) => ({ ...t, text: e.answer }));
          history.current = [
            ...history.current,
            { role: "user" as const, content: q },
            { role: "assistant" as const, content: e.answer },
          ].slice(-12);
        }
      });
      onAnswer(collected);
    } catch (err: any) {
      setError(String(err.message ?? err));
      patchAssistant((t) => ({ ...t, text: t.text || "—" }));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="chat-col">
      <div className="chat-log" ref={logRef}>
        {turns.length === 0 && (
          <div className="empty">
            Ask about cases, people, networks, or trends. Answers are assembled only from tool
            results — the assistant will refuse rather than guess.
          </div>
        )}
        {turns.map((t, i) => (
          <div className={`msg ${t.role}`} key={i}>
            <div className="who">{t.role === "user" ? "you" : "assistant"}</div>
            <div className="bubble">
              {t.text || (busy && t.role === "assistant" ? "…" : "")}
              {t.role === "assistant" && t.toolCalls && t.toolCalls.length > 0 && (
                <div className="tool-trace">
                  {t.toolCalls.map((tc, j) => (
                    <span className={`tool-chip${tc.ok ? "" : " denied"}`} key={j}>
                      <span className="dot" />{tc.tool}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {error && <div className="banner error">{error}</div>}

      {turns.length === 0 && (
        <div className="suggestions">
          {SUGGESTIONS.map((s) => (
            <button key={s} onClick={() => send(s)} disabled={busy}>{s}</button>
          ))}
        </div>
      )}

      <form
        className="chat-input"
        onSubmit={(e) => { e.preventDefault(); send(input); }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask the crime intelligence assistant…"
          disabled={busy}
        />
        <button type="submit" disabled={busy || !input.trim()}>{busy ? "…" : "Send"}</button>
      </form>
    </div>
  );
}
