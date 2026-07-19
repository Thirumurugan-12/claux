import { useEffect, useMemo, useState } from "react";
import {
  DemoRole,
  extractGeo,
  extractGraph,
  fetchDemoRoles,
  GeoData,
  GraphData,
  Principal,
  ToolCall,
} from "./api";
import ChatPane from "./components/ChatPane";
import EvidencePane from "./components/EvidencePane";
import NetworkGraph from "./components/NetworkGraph";
import HotspotMap from "./components/HotspotMap";
import CaseDrawer from "./components/CaseDrawer";

type Tab = "evidence" | "network" | "map";

export default function App() {
  const [roles, setRoles] = useState<DemoRole[]>([]);
  const [roleIdx, setRoleIdx] = useState(0);
  const [toolCalls, setToolCalls] = useState<ToolCall[]>([]);
  const [tab, setTab] = useState<Tab>("evidence");
  const [openCase, setOpenCase] = useState<string | null>(null);

  useEffect(() => {
    // default to SP — a district officer who can see people, networks, and trends in scope
    fetchDemoRoles()
      .then((r) => {
        setRoles(r);
        const sp = r.findIndex((x) => x.role === "sp");
        if (sp >= 0) setRoleIdx(sp);
      })
      .catch(() => setRoles([]));
  }, []);

  const current: DemoRole | null = roles[roleIdx] ?? null;
  const principal: Principal = current?.principal ?? { name: "SP", role: "sp" };

  const { graph, geo } = useMemo(() => {
    let g: GraphData | null = null;
    let ge: GeoData | null = null;
    for (const tc of toolCalls) {
      g = g ?? extractGraph(tc);
      ge = ge ?? extractGeo(tc);
    }
    return { graph: g, geo: ge };
  }, [toolCalls]);

  function onAnswer(tcs: ToolCall[]) {
    setToolCalls(tcs);
    // surface the most visual result: network > map > evidence
    if (tcs.some(extractGraph)) setTab("network");
    else if (tcs.some(extractGeo)) setTab("map");
    else setTab("evidence");
  }

  useEffect(() => {
    // when the role changes, reset the panes (fresh RBAC context)
    setToolCalls([]);
    setTab("evidence");
    setOpenCase(null);
  }, [roleIdx]);

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          KSP Crime Intelligence
          <span className="sub">Karnataka State Police · SCRB</span>
        </div>
        <div className="spacer" />
        {current && <span className="role-scope">{current.scope}</span>}
        <div className="role-switcher">
          <label htmlFor="role">Acting as</label>
          <select
            id="role"
            value={roleIdx}
            onChange={(e) => setRoleIdx(Number(e.target.value))}
            disabled={!roles.length}
          >
            {roles.map((r, i) => (
              <option value={i} key={r.role}>{r.label}</option>
            ))}
          </select>
        </div>
      </header>

      <div className="workspace">
        <ChatPane key={principal.role} principal={principal} onAnswer={onAnswer} />

        <div className="pane-col">
          <div className="tabs">
            <button className={tab === "evidence" ? "active" : ""} onClick={() => setTab("evidence")}>
              Evidence
            </button>
            <button className={tab === "network" ? "active" : ""} onClick={() => setTab("network")}>
              Network{graph && <span className="badge">●</span>}
            </button>
            <button className={tab === "map" ? "active" : ""} onClick={() => setTab("map")}>
              Map{geo && <span className="badge">●</span>}
            </button>
          </div>

          <div className="pane">
            {tab === "evidence" && <EvidencePane toolCalls={toolCalls} onOpenCase={setOpenCase} />}
            {tab === "network" &&
              (graph ? <NetworkGraph graph={graph} /> : (
                <div className="empty">Ask about a person's network or co-offending groups —
                  the graph renders here.</div>
              ))}
            {tab === "map" &&
              (geo ? <HotspotMap geo={geo} /> : (
                <div className="empty">Run a hotspot scan — the map renders here, honest about
                  precise vs inferred coverage.</div>
              ))}
          </div>
        </div>
      </div>

      {openCase && (
        <CaseDrawer crimeNo={openCase} principal={principal} onClose={() => setOpenCase(null)} />
      )}
    </div>
  );
}
