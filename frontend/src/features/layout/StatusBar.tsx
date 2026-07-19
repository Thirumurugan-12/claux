/** Slim footer strip stating the platform's core guarantee. */
export function StatusBar() {
  return (
    <footer className="statusbar">
      <span className="statusbar-item">
        <span className="statusbar-dot" aria-hidden />
        Tool-grounded — every fact carries provenance
      </span>
      <span className="statusbar-spacer" />
      <span className="statusbar-item mono">Datathon 2026 · PS1</span>
    </footer>
  );
}
