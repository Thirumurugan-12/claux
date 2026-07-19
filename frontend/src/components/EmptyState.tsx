import type { ReactNode } from "react";

interface EmptyStateProps {
  icon: ReactNode;
  title: string;
  hint: string;
}

/**
 * Teaching empty state. Carries the one restrained heritage detail in the whole UI: a thin
 * engraved rule with a single Kasuti diamond, drawn at low opacity as a divider — a considered
 * ornament, not a theme skin stamped across every surface.
 */
export function EmptyState({ icon, title, hint }: EmptyStateProps) {
  return (
    <div className="empty">
      <span className="empty-glyph" aria-hidden>
        {icon}
      </span>
      <p className="empty-title">{title}</p>
      <svg
        className="empty-rule"
        width="120"
        height="8"
        viewBox="0 0 120 8"
        aria-hidden
        fill="none"
        stroke="currentColor"
      >
        <path d="M0 4h50M70 4h50" strokeWidth="1" />
        <path d="M60 1l3 3-3 3-3-3 3-3z" strokeWidth="1" />
      </svg>
      <p className="empty-hint">{hint}</p>
    </div>
  );
}
