import { useEffect, useState } from "react";
import { CaseData, fetchCase, Principal } from "../api";

// Opens one FIR when a CrimeNo is clicked in the evidence pane. Runs through the same
// get_case tool + RBAC, so an out-of-jurisdiction click honestly shows "denied".

export default function CaseDrawer({
  crimeNo,
  principal,
  onClose,
}: {
  crimeNo: string;
  principal: Principal;
  onClose: () => void;
}) {
  const [state, setState] = useState<{ case?: CaseData; error?: string } | null>(null);

  useEffect(() => {
    let live = true;
    setState(null);
    fetchCase(principal, { crime_no: crimeNo })
      .then((c) => live && setState({ case: c }))
      .catch((e) => live && setState({ error: String(e.message ?? e) }));
    return () => {
      live = false;
    };
  }, [crimeNo, principal]);

  const d = state?.case?.data;
  return (
    <div className="drawer-scrim" onClick={onClose}>
      <div className="drawer" onClick={(e) => e.stopPropagation()}>
        <button className="x" onClick={onClose} aria-label="close">×</button>
        <h2>FIR {crimeNo}</h2>
        {!state && <p className="muted">Loading…</p>}
        {state?.error && <p style={{ color: "var(--danger)" }}>{state.error}</p>}
        {d && (
          <>
            <div>
              {d.heinous && <span className="tag heinous">HEINOUS</span>}{" "}
              <span className="tag">{d.chargesheet ? `chargesheet ${d.chargesheet.cs_type}` : "open"}</span>
            </div>
            <dl className="kv">
              <dt>Case ID</dt><dd>{d.case_master_id}</dd>
              <dt>Registered</dt><dd>{d.registered}</dd>
              <dt>Station</dt><dd>{d.station} (dist {d.district_id})</dd>
              <dt>Sections</dt>
              <dd className="section-list">
                {(d.sections ?? []).map((s: string, i: number) => <span className="tag" key={i}>{s}</span>)}
              </dd>
            </dl>
            <h3>Accused ({(d.accused ?? []).length})</h3>
            <dl className="kv">
              {(d.accused ?? []).map((a: any, i: number) => (
                <div key={i} style={{ display: "contents" }}>
                  <dt>{a.name}</dt>
                  <dd className="muted">
                    {a.person_cluster_id != null
                      ? `→ person #${a.person_cluster_id}` +
                        (a.resolution_confidence != null ? ` (${a.resolution_confidence.toFixed(2)})` : "")
                      : "unresolved"}
                  </dd>
                </div>
              ))}
            </dl>
            {d.victims?.length > 0 && (
              <>
                <h3>Victims ({d.victims.length})</h3>
                <div className="section-list">
                  {d.victims.map((v: any, i: number) => <span className="tag" key={i}>{v.name}</span>)}
                </div>
              </>
            )}
            <p className="prov-note" style={{ marginTop: 16 }}>
              Accused are linked to a resolved <b>person</b> via entity resolution
              (person_cluster), never by treating the per-FIR accused id as an identity.
            </p>
          </>
        )}
      </div>
    </div>
  );
}
