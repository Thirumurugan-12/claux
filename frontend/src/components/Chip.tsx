import type { ReactNode } from "react";

export type ChipTone = "neutral" | "success" | "danger" | "info";

interface ChipProps {
  children: ReactNode;
  tone?: ChipTone;
  /** Leading status dot (tinted to the tone). */
  dot?: boolean;
  /** Render as mono (for IDs / tool names). */
  mono?: boolean;
  /** If provided, the chip becomes an interactive button. */
  onClick?: () => void;
  title?: string;
}

/** Small labelled token used for tool-call traces, tags, and clickable references. */
export function Chip({ children, tone = "neutral", dot = false, mono = false, onClick, title }: ChipProps) {
  const className = `chip chip-${tone}${mono ? " chip-mono" : ""}${onClick ? " chip-btn" : ""}`;
  const content = (
    <>
      {dot && <span className="chip-dot" aria-hidden />}
      {children}
    </>
  );
  if (onClick) {
    return (
      <button type="button" className={className} onClick={onClick} title={title}>
        {content}
      </button>
    );
  }
  return (
    <span className={className} title={title}>
      {content}
    </span>
  );
}
