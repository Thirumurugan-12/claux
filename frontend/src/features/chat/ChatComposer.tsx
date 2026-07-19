import { useState } from "react";
import { IconButton } from "../../components/IconButton";
import { Send } from "../../components/icons";

interface ChatComposerProps {
  busy: boolean;
  onSend: (text: string) => void;
}

/** Message input row. Enter submits; the send button doubles as the busy indicator. */
export function ChatComposer({ busy, onSend }: ChatComposerProps) {
  const [input, setInput] = useState("");

  const submit = () => {
    const text = input.trim();
    if (!text || busy) return;
    onSend(text);
    setInput("");
  };

  return (
    <form
      className="composer"
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
    >
      <input
        className="composer-input"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder="Ask the crime intelligence assistant…"
        aria-label="Ask the crime intelligence assistant"
        disabled={busy}
      />
      <IconButton label="Send" type="submit" className="composer-send" disabled={busy || !input.trim()}>
        {busy ? <span className="spinner" aria-hidden /> : <Send />}
      </IconButton>
    </form>
  );
}
