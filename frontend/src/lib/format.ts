/** Thousands-separated integer for counts shown in prose/coverage notes. */
export const count = (n: number): string => n.toLocaleString();

/** Turn a snake_case tool name into a readable label. */
export const humanize = (s: string): string => s.replace(/_/g, " ");

/** Coerce an unknown thrown value into a human-readable message. */
export function errorMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  return String(err);
}
