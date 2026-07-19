import { EmptyState } from "../../components/EmptyState";
import { EvidenceIcon } from "../../components/icons";
import { ProvenanceCard } from "./ProvenanceCard";
import type { ToolCall } from "../../api";

interface EvidencePaneProps {
  toolCalls: ToolCall[];
  onOpenCase: (crimeNo: string) => void;
}

/**
 * The provenance chain for the latest answer — PS1 §9 (explainability) in list form. Every
 * CrimeNo is clickable and opens the underlying FIR through the same RBAC-checked get_case tool,
 * making the "never authors a fact" guarantee tangible.
 */
export function EvidencePane({ toolCalls, onOpenCase }: EvidencePaneProps) {
  if (!toolCalls.length) {
    return (
      <EmptyState
        icon={<EvidenceIcon />}
        title="The evidence trail appears here"
        hint="Ask a question — the tools it runs and the records behind every figure are listed here, each CrimeNo clickable to its source FIR."
      />
    );
  }

  return (
    <div className="evidence">
      <h3 className="section-label">Provenance chain</h3>
      {toolCalls.map((tc, i) => (
        <ProvenanceCard key={i} toolCall={tc} onOpenCase={onOpenCase} />
      ))}
      <p className="prov-note">
        Every figure in the answer is drawn from these tool results — the assistant is not permitted to state
        a number, name, or date that a tool did not return. Click any CrimeNo to open the source FIR.
      </p>
    </div>
  );
}
