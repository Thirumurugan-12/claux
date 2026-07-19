"""The tool catalogue — the registry of real tools the orchestration loop (P14) uses.

As each prompt lands its tools, it registers them here. This is the single source of
truth for "what can the LLM call"; ``python -m app.tools`` prints their schemas.
"""

from __future__ import annotations

from app.tools.base import ToolRegistry
from app.tools.compliance import ChargesheetDeadlineWatchTool, RegistrationDelayReportTool
from app.tools.demo import CaseCountByDistrictTool
from app.tools.retrieval import (
    GetCaseTimelineTool,
    GetCaseTool,
    GetChargesheetStatusTool,
    GetPersonTool,
    SearchCasesTool,
    SearchPersonsTool,
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
    # a general aggregate demo tool (kept until a richer trends catalogue lands in P13)
    registry.register(CaseCountByDistrictTool())
    return registry
