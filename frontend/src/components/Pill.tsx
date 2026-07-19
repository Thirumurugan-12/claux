import type { ReactNode } from "react";

interface PillProps {
  children: ReactNode;
  /** Show a leading status dot. */
  dot?: boolean;
  title?: string;
}

/** A compact bordered status indicator (e.g. the RBAC scope). Deliberately a squared tag, not a
 * full pill, to keep the operational, non-decorative register. */
export function Pill({ children, dot = false, title }: PillProps) {
  return (
    <span className="pill" title={title}>
      {dot && <span className="pill-dot" aria-hidden />}
      {children}
    </span>
  );
}
