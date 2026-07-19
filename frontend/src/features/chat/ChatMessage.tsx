import { ToolTrace } from "./ToolTrace";
import type { ChatTurn } from "../../hooks/useChatStream";

interface ChatMessageProps {
  turn: ChatTurn;
  /** True while this (last, assistant) turn is still streaming. */
  streaming: boolean;
}

/**
 * Two deliberately asymmetric registers: a user question is a compact right-aligned query block;
 * an assistant answer is full-width analyst prose with its source trace — an investigation
 * transcript, not a symmetrical messaging thread.
 */
export function ChatMessage({ turn, streaming }: ChatMessageProps) {
  if (turn.role === "user") {
    return (
      <div className="turn turn-user">
        <div className="query">{turn.text}</div>
      </div>
    );
  }

  const showCursor = streaming && !turn.text;
  return (
    <div className="turn turn-assistant">
      <div className="turn-label">Assistant</div>
      <div className="answer">
        {turn.text}
        {showCursor && (
          <span className="stream-cursor" aria-label="working">
            ▍
          </span>
        )}
      </div>
      {turn.toolCalls && <ToolTrace toolCalls={turn.toolCalls} />}
    </div>
  );
}
