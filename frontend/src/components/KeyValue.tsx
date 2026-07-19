import type { ReactNode } from "react";

/** Definition-list grid for label/value pairs (case metadata, accused links). */
export function KeyValueList({ children }: { children: ReactNode }) {
  return <dl className="kv">{children}</dl>;
}

interface RowProps {
  label: ReactNode;
  children: ReactNode;
  /** Render the value in mono (IDs, dates). */
  mono?: boolean;
}

export function KeyValueRow({ label, children, mono = false }: RowProps) {
  return (
    <>
      <dt>{label}</dt>
      <dd className={mono ? "mono" : undefined}>{children}</dd>
    </>
  );
}
