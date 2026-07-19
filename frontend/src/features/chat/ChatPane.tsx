import { useEffect, useRef } from "react";
import { Tile } from "../../components/Tile";
import { EmptyState } from "../../components/EmptyState";
import { Alert, ChatIcon } from "../../components/icons";
import { useChatStream } from "../../hooks/useChatStream";
import type { Principal, ToolCall } from "../../api";
import { ChatMessage } from "./ChatMessage";
import { ChatComposer } from "./ChatComposer";
import { SUGGESTIONS } from "./suggestions";

interface ChatPaneProps {
  principal: Principal;
  onAnswer: (toolCalls: ToolCall[]) => void;
}

export function ChatPane({ principal, onAnswer }: ChatPaneProps) {
  const { turns, busy, error, send } = useChatStream(principal, onAnswer);
  const logRef = useRef<HTMLDivElement>(null);
  const empty = turns.length === 0;

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: "smooth" });
  }, [turns, busy]);

  return (
    <Tile className="tile-chat" ariaLabel="Conversation" title="Conversation" bodyClassName="tile-flow">
      <div className="chat-log" ref={logRef}>
        {empty ? (
          <EmptyState
            icon={<ChatIcon />}
            title="Ask about cases, people, networks, or trends"
            hint="Answers are assembled only from tool results — the assistant refuses rather than guess, and every figure links back to its source FIR."
          />
        ) : (
          turns.map((turn, i) => (
            <ChatMessage key={i} turn={turn} streaming={busy && i === turns.length - 1} />
          ))
        )}
      </div>

      {error && (
        <div className="banner banner-error" role="alert">
          <Alert />
          <span>{error}</span>
        </div>
      )}

      {empty && (
        <div className="suggestions">
          {SUGGESTIONS.map((s) => (
            <button type="button" key={s} className="suggestion" onClick={() => send(s)} disabled={busy}>
              {s}
            </button>
          ))}
        </div>
      )}

      <ChatComposer busy={busy} onSend={send} />
    </Tile>
  );
}
