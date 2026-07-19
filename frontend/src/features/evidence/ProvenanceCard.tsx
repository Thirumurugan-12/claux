import { Chip } from "../../components/Chip";
import { MAX_CRIME_CHIPS } from "../../lib/constants";
import type { ToolCall } from "../../api";

interface ProvenanceCardProps {
  toolCall: ToolCall;
  onOpenCase: (crimeNo: string) => void;
}

/** One tool call in the provenance chain: outcome, parameters, and clickable source FIRs. */
export function ProvenanceCard({ toolCall, onOpenCase }: ProvenanceCardProps) {
  const { tool, ok, row_ids, crime_nos, params, error } = toolCall;
  const hasParams = params && Object.keys(params).length > 0;

  return (
    <article className="prov-card">
      <div className="prov-head">
        <span className={`prov-status ${ok ? "ok" : "no"}`} aria-hidden />
        <span className="prov-name mono">{tool}</span>
        <span className={`prov-count mono${ok ? "" : " denied"}`}>
          {ok ? `${row_ids.length} rows · ${crime_nos.length} FIRs` : "denied"}
        </span>
      </div>

      {hasParams && <div className="prov-params mono">{JSON.stringify(params)}</div>}
      {error && <div className="prov-params error mono">{error}</div>}

      {crime_nos.length > 0 && (
        <div className="prov-chips">
          {crime_nos.slice(0, MAX_CRIME_CHIPS).map((cn) => (
            <Chip key={cn} tone="info" mono onClick={() => onOpenCase(cn)} title="Open this FIR">
              {cn}
            </Chip>
          ))}
        </div>
      )}
    </article>
  );
}
