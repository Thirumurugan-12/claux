import { useEffect, useState } from "react";
import { Tile } from "../../components/Tile";
import { Tabs } from "../../components/Tabs";
import type { TabItem } from "../../components/Tabs";
import { EmptyState } from "../../components/EmptyState";
import { EvidenceIcon, MapIcon, NetworkIcon } from "../../components/icons";
import { usePaneData } from "../../hooks/usePaneData";
import type { ToolCall } from "../../api";
import { EvidencePane } from "../evidence/EvidencePane";
import { NetworkGraph } from "../network/NetworkGraph";
import { HotspotMap } from "../map/HotspotMap";

type PaneId = "evidence" | "network" | "map";

interface WorkspaceProps {
  toolCalls: ToolCall[];
  onOpenCase: (crimeNo: string) => void;
}

/** The right-hand analysis column: evidence / network / map, fed by the latest answer's tools.
 * When a new answer arrives it auto-surfaces the most visual pane available. */
export function Workspace({ toolCalls, onOpenCase }: WorkspaceProps) {
  const { graph, geo } = usePaneData(toolCalls);
  const [tab, setTab] = useState<PaneId>("evidence");

  useEffect(() => {
    if (graph) setTab("network");
    else if (geo) setTab("map");
    else setTab("evidence");
  }, [graph, geo]);

  const tabs: TabItem<PaneId>[] = [
    { id: "evidence", label: "Evidence", icon: <EvidenceIcon width={15} height={15} /> },
    { id: "network", label: "Network", icon: <NetworkIcon width={15} height={15} />, hasData: !!graph },
    { id: "map", label: "Map", icon: <MapIcon width={15} height={15} />, hasData: !!geo },
  ];

  return (
    <Tile
      className="tile-analysis"
      ariaLabel="Analysis"
      bodyClassName="tile-flow"
      head={<Tabs items={tabs} value={tab} onChange={setTab} ariaLabel="Analysis views" />}
    >
      <div className="pane" role="tabpanel">
        {tab === "evidence" && <EvidencePane toolCalls={toolCalls} onOpenCase={onOpenCase} />}
        {tab === "network" &&
          (graph ? (
            <NetworkGraph graph={graph} />
          ) : (
            <EmptyState
              icon={<NetworkIcon />}
              title="Co-offending networks render here"
              hint="Ask about a person's network or cross-jurisdiction gangs — the resolved-person graph draws in this pane."
            />
          ))}
        {tab === "map" &&
          (geo ? (
            <HotspotMap geo={geo} />
          ) : (
            <EmptyState
              icon={<MapIcon />}
              title="Crime hotspots render here"
              hint="Run a hotspot scan — the map plots clusters and stays honest about precise vs inferred coverage."
            />
          ))}
      </div>
    </Tile>
  );
}
