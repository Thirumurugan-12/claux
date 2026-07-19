import { ToolCall } from "../api";

// The evidence drawer: the provenance chain for the latest answer. Every CrimeNo is
// clickable and opens the underlying FIR — this is the "never authors a fact" guarantee made
// tangible, and PS1 §9 (explainability) in its list form (P19b turns it into a node diagram).

export default function EvidencePane({
  toolCalls,
  onOpenCase,
}: {
  toolCalls: ToolCall[];
  onOpenCase: (crimeNo: string) => void;
}) {
  if (!toolCalls.length) {
    return <div className="empty">Ask a question — the tools it runs and the records behind
      the answer appear here.</div>;
  }
  return (
    <div>
      <h3>Provenance chain</h3>
      {toolCalls.map((tc, i) => (
        <div className="ev-tool" key={i}>
          <div className="hd">
            <span className="dot" style={{
              width: 8, height: 8, borderRadius: "50%",
              background: tc.ok ? "var(--ok)" : "var(--danger)",
            }} />
            <span className="name">{tc.tool}</span>
            {tc.ok ? (
              <span className="rows">{tc.row_ids.length} rows · {tc.crime_nos.length} FIRs</span>
            ) : (
              <span className="rows" style={{ color: "var(--danger)" }}>denied</span>
            )}
          </div>
          {tc.params && Object.keys(tc.params).length > 0 && (
            <div className="params">{JSON.stringify(tc.params)}</div>
          )}
          {tc.error && <div className="params" style={{ color: "var(--danger)" }}>{tc.error}</div>}
          {tc.crime_nos.length > 0 && (
            <div className="crime-chips">
              {tc.crime_nos.slice(0, 24).map((cn) => (
                <button className="crime-chip" key={cn} onClick={() => onOpenCase(cn)} title="Open this FIR">
                  {cn}
                </button>
              ))}
            </div>
          )}
        </div>
      ))}
      <p className="prov-note">
        Every figure in the answer is drawn from these tool results — the assistant is not
        permitted to state a number, name, or date that a tool did not return. Click any CrimeNo
        to open the source FIR.
      </p>
    </div>
  );
}
