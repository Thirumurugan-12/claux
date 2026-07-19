"""The tool catalogue — the registry of real tools the orchestration loop (P14) uses.

As each prompt lands its tools, it registers them here. This is the single source of
truth for "what can the LLM call"; ``python -m app.tools`` prints their schemas.
"""

from __future__ import annotations

from app.tools.base import ToolRegistry
from app.tools.compliance import ChargesheetDeadlineWatchTool, RegistrationDelayReportTool
from app.tools.demo import CaseCountByDistrictTool, GetCaseTool


def build_registry() -> ToolRegistry:
    registry = ToolRegistry()
    # P9 demo tools (P10 will replace get_case with a person_cluster-backed version)
    registry.register(GetCaseTool())
    registry.register(CaseCountByDistrictTool())
    # P11 compliance tools
    registry.register(ChargesheetDeadlineWatchTool())
    registry.register(RegistrationDelayReportTool())
    return registry
