"""The tool catalogue — the registry of real tools the orchestration loop (P14) uses.

As each prompt lands its tools, it registers them here. This is the single source of
truth for "what can the LLM call"; ``python -m app.tools`` prints their schemas.
"""

from __future__ import annotations

from app.tools.base import ToolRegistry
from app.tools.compliance import ChargesheetDeadlineWatchTool, RegistrationDelayReportTool
from app.tools.demo import CaseCountByDistrictTool
from app.tools.mo import FindSimilarCasesTool, GetMoClusterTool
from app.tools.network import (
    DetectCommunitiesTool,
    FindShortestPathTool,
    GetPersonNetworkTool,
    GetRepeatOffendersTool,
)
from app.tools.retrieval import (
    GetCaseTimelineTool,
    GetCaseTool,
    GetChargesheetStatusTool,
    GetPersonTool,
    SearchCasesTool,
    SearchPersonsTool,
)
from app.tools.trends import (
    CompareToBaselineTool,
    CrimeTrendTool,
    HotspotScanTool,
    SeasonalityTool,
    SpatioTemporalClustersTool,
    ZeroFirFlowsTool,
)


def build_registry() -> ToolRegistry:
    registry = ToolRegistry()
    # P10 retrieval tools
    registry.register(GetCaseTool())
    registry.register(SearchCasesTool())
    registry.register(GetPersonTool())
    registry.register(SearchPersonsTool())
    registry.register(GetCaseTimelineTool())
    registry.register(GetChargesheetStatusTool())
    # P11 compliance tools
    registry.register(ChargesheetDeadlineWatchTool())
    registry.register(RegistrationDelayReportTool())
    # P12 network tools (over the resolved-person co-offending graph)
    registry.register(GetPersonNetworkTool())
    registry.register(FindShortestPathTool())
    registry.register(DetectCommunitiesTool())
    registry.register(GetRepeatOffendersTool())
    # P13 trend + hotspot tools
    registry.register(CrimeTrendTool())
    registry.register(HotspotScanTool())
    registry.register(SpatioTemporalClustersTool())
    registry.register(CompareToBaselineTool())
    registry.register(SeasonalityTool())
    registry.register(ZeroFirFlowsTool())
    # P15 MO fingerprinting tools
    registry.register(GetMoClusterTool())
    registry.register(FindSimilarCasesTool())
    # a general aggregate demo tool (kept until a richer trends catalogue lands in P13)
    registry.register(CaseCountByDistrictTool())
    return registry
