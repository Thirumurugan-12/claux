import { useEffect, useState } from "react";
import { Drawer } from "../../components/Drawer";
import { KeyValueList, KeyValueRow } from "../../components/KeyValue";
import { fetchCase } from "../../api";
import type { CaseData, Principal } from "../../api";
import { errorMessage } from "../../lib/format";

interface CaseDrawerProps {
  crimeNo: string;
  principal: Principal;
  onClose: () => void;
}

type LoadState =
  { status: "loading" } | { status: "error"; message: string } | { status: "ready"; data: CaseData };

/** Opens one FIR when a CrimeNo is clicked. Runs through the same get_case tool + RBAC, so an
 * out-of-jurisdiction click honestly shows "denied". */
export function CaseDrawer({ crimeNo, principal, onClose }: CaseDrawerProps) {
  const [state, setState] = useState<LoadState>({ status: "loading" });

  useEffect(() => {
    let live = true;
    setState({ status: "loading" });
    fetchCase(principal, { crime_no: crimeNo })
      .then((c) => live && setState({ status: "ready", data: c }))
      .catch((e) => live && setState({ status: "error", message: errorMessage(e) }));
    return () => {
      live = false;
    };
  }, [crimeNo, principal]);

  return (
    <Drawer title="Case file" subtitle={<span className="mono">FIR {crimeNo}</span>} onClose={onClose}>
      {state.status === "loading" && <p className="muted">Loading…</p>}
      {state.status === "error" && <p className="drawer-error">{state.message}</p>}
      {state.status === "ready" && <CaseBody data={state.data.data} />}
    </Drawer>
  );
}

function CaseBody({ data: d }: { data: CaseData["data"] }) {
  const accused = d.accused ?? [];
  const victims = d.victims ?? [];
  const sections = d.sections ?? [];

  return (
    <>
      <div className="tag-row">
        {d.heinous && <span className="tag tag-heinous">HEINOUS</span>}
        <span className="tag tag-status">
          {d.chargesheet ? `chargesheet ${d.chargesheet.cs_type}` : "open"}
        </span>
      </div>

      <KeyValueList>
        <KeyValueRow label="Case ID" mono>
          {d.case_master_id}
        </KeyValueRow>
        <KeyValueRow label="Registered" mono>
          {d.registered}
        </KeyValueRow>
        <KeyValueRow label="Station">
          {d.station} <span className="muted">(dist {d.district_id})</span>
        </KeyValueRow>
        <KeyValueRow label="Sections">
          <span className="section-list">
            {sections.map((s, i) => (
              <span className="tag tag-mono" key={i}>
                {s}
              </span>
            ))}
          </span>
        </KeyValueRow>
      </KeyValueList>

      <h3 className="section-label">Accused ({accused.length})</h3>
      <KeyValueList>
        {accused.map((a, i) => (
          <KeyValueRow key={i} label={a.name}>
            {a.person_cluster_id != null ? (
              <span className="link-strong">
                → person #{a.person_cluster_id}
                {a.resolution_confidence != null ? ` (${a.resolution_confidence.toFixed(2)})` : ""}
              </span>
            ) : (
              <span className="muted">unresolved</span>
            )}
          </KeyValueRow>
        ))}
      </KeyValueList>

      {victims.length > 0 && (
        <>
          <h3 className="section-label">Victims ({victims.length})</h3>
          <div className="section-list">
            {victims.map((v, i) => (
              <span className="tag" key={i}>
                {v.name}
              </span>
            ))}
          </div>
        </>
      )}

      <p className="prov-note">
        Accused are linked to a resolved <b>person</b> via entity resolution (person_cluster), never by
        treating the per-FIR accused id as an identity.
      </p>
    </>
  );
}
