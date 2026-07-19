import { useCallback, useRef, useState } from "react";
import { streamChat } from "../api";
import type { ChatMessage, Principal, StreamEvent, ToolCall } from "../api";
import { errorMessage } from "../lib/format";
import { HISTORY_LIMIT } from "../lib/constants";

export interface ChatTurn {
  role: "user" | "assistant";
  text: string;
  toolCalls?: ToolCall[];
}

interface UseChatStream {
  turns: ChatTurn[];
  busy: boolean;
  error: string | null;
  send: (text: string) => void;
}

/**
 * Owns a single principal's chat conversation: streaming turns, inline tool-call chips, the
 * text-only multi-turn history, and error state. View components stay declarative.
 *
 * `onAnswer` fires once per completed turn with that turn's tool calls, so the workspace panes
 * can repaint from the same tool results the answer was built from.
 */
export function useChatStream(
  principal: Principal,
  onAnswer: (toolCalls: ToolCall[]) => void,
): UseChatStream {
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const history = useRef<ChatMessage[]>([]);

  const patchAssistant = useCallback((fn: (t: ChatTurn) => ChatTurn) => {
    setTurns((ts) => {
      const copy = ts.slice();
      for (let i = copy.length - 1; i >= 0; i--) {
        if (copy[i].role === "assistant") {
          copy[i] = fn(copy[i]);
          break;
        }
      }
      return copy;
    });
  }, []);

  const send = useCallback(
    (text: string) => {
      const question = text.trim();
      if (!question || busy) return;

      setError(null);
      setBusy(true);
      setTurns((t) => [
        ...t,
        { role: "user", text: question },
        { role: "assistant", text: "", toolCalls: [] },
      ]);

      const collected: ToolCall[] = [];

      const onEvent = (e: StreamEvent) => {
        if (e.type === "tool_call") {
          const tc: ToolCall = {
            tool: e.tool,
            ok: e.ok,
            crime_nos: e.crime_nos,
            row_ids: e.row_ids,
            error: e.error,
            params: e.params,
            data: e.data,
          };
          collected.push(tc);
          patchAssistant((t) => ({ ...t, toolCalls: [...(t.toolCalls ?? []), tc] }));
        } else if (e.type === "result") {
          patchAssistant((t) => ({ ...t, text: e.answer }));
          history.current = [
            ...history.current,
            { role: "user" as const, content: question },
            { role: "assistant" as const, content: e.answer },
          ].slice(-HISTORY_LIMIT);
        }
      };

      streamChat(principal, question, history.current, onEvent)
        .then(() => onAnswer(collected))
        .catch((err: unknown) => {
          setError(errorMessage(err));
          patchAssistant((t) => ({ ...t, text: t.text || "—" }));
        })
        .finally(() => setBusy(false));
    },
    [busy, principal, onAnswer, patchAssistant],
  );

  return { turns, busy, error, send };
}
