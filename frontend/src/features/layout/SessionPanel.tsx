import { useMemo } from "react";
import { Tile } from "../../components/Tile";
import { Pill } from "../../components/Pill";
import { count } from "../../lib/format";
import type { DemoRole, ToolCall } from "../../api";

interface SessionPanelProps {
  current: DemoRole | null;
  toolCalls: ToolCall[];
}

interface Signals {
  tools: number;
  firs: number;
  rows: number;
  denied: number;
}

function Stat({ label, value, denied = false }: { label: string; value: number; denied?: boolean }) {
  return (
    <div className="stat">
      <span className={`stat-value${denied && value > 0 ? " denied" : ""}`}>{count(value)}</span>
      <span className="stat-label">{label}</span>
    </div>
  );
}

/**
 * The Session context tile: the active RBAC principal + scope (the readout half of the role
 * switcher in the top bar), plus live signals derived from the latest answer's tool calls — the
 * provenance footprint at a glance. Presentation-only; it reads the same tool results the
 * evidence and analysis tiles render.
 */
export function SessionPanel({ current, toolCalls }: SessionPanelProps) {
  const signals = useMemo<Signals>(() => {
    const firs = new Set<string>();
    let rows = 0;
    let denied = 0;
    for (const tc of toolCalls) {
      tc.crime_nos.forEach((c) => firs.add(c));
      rows += tc.row_ids.length;
      if (!tc.ok) denied += 1;
    }
    return { tools: toolCalls.length, firs: firs.size, rows, denied };
  }, [toolCalls]);

  const answered = toolCalls.length > 0;

  return (
    <Tile className="tile-session" ariaLabel="Session" title="Session">
      <div className="session tile-pad">
        <div className="session-role">
          <Pill dot title="Access is enforced at the tool boundary for this role">
            {current?.label ?? "Loading role…"}
          </Pill>
        </div>

        <div className="session-row">
          <span className="session-key">Scope</span>
          <span className="session-val">{current?.scope ?? "—"}</span>
        </div>

        <div className="session-divider" />

        <div className="session-stats">
          <Stat label="Tools" value={signals.tools} />
          <Stat label="FIRs cited" value={signals.firs} />
          <Stat
            label={signals.denied > 0 ? "Denied" : "Rows"}
            value={signals.denied > 0 ? signals.denied : signals.rows}
            denied={signals.denied > 0}
          />
        </div>

        {!answered && (
          <p className="session-hint">
            Ask a question — the tools it runs, the FIRs it cites, and any access denials appear here.
          </p>
        )}
      </div>
    </Tile>
  );
}
