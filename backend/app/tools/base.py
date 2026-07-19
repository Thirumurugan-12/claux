"""The tool framework — where CLAUDE.md's non-negotiable rules are enforced.

Every capability the LLM can invoke is a :class:`Tool`. The base class makes the rules
structural rather than a matter of discipline:

  * **Provenance is mandatory.** A tool returns :class:`ToolResult` — ``data`` *and*
    ``provenance`` — so it is physically impossible to return a bare number. Every
    answer can be traced back to the CrimeNos and row ids it came from.
  * **RBAC lives at the tool boundary, never in the prompt.** Every call takes a
    :class:`Principal`; scope is resolved from ``unit.parent_unit`` (recursive CTE) and
    the role ladder (PLAN.md §6). Out-of-scope access is denied here, not requested-nicely.
  * **k-anonymity** blanks any aggregate cell with a count below 5 for the analyst and
    policymaker roles, who see aggregates only.
  * **Every call is audited** — principal, tool, params, row count, timestamp, and
    whether it was denied. The audit log and the evidence trail are the same artifact.

The LLM never writes SQL; it picks a registered tool, and the registry emits the
Anthropic tool-use JSON schema for each from its Pydantic params model.
"""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict
from sqlalchemy import text
from sqlalchemy.orm import Session

K_ANONYMITY_THRESHOLD = 5


# -----------------------------------------------------------------------------
# Principal and roles (PLAN.md §6)
# -----------------------------------------------------------------------------


class Role(StrEnum):
    CONSTABLE = "constable"
    SHO = "sho"
    DYSP = "dysp"
    SP = "sp"
    SCRB_ANALYST = "scrb_analyst"
    POLICYMAKER = "policymaker"


# Roles that see aggregates only — person-level rows are suppressed / person tools denied.
AGGREGATE_ONLY_ROLES = {Role.SCRB_ANALYST, Role.POLICYMAKER}
# Roles for whom person-level tools are disabled outright.
PERSON_TOOL_DISABLED_ROLES = {Role.SCRB_ANALYST, Role.POLICYMAKER}
# Roles whose scope is the whole state (no unit filter).
STATE_SCOPE_ROLES = {Role.SCRB_ANALYST, Role.POLICYMAKER}


class Principal(BaseModel):
    """Who is calling. Scope is derived from role + unit/district, not trusted from
    the caller's word: the tool boundary resolves the actual in-scope units."""

    employee_id: int | None = None
    name: str = "unknown"
    role: Role
    unit_id: int | None = None
    district_id: int | None = None
    rank_hierarchy: int | None = None


# -----------------------------------------------------------------------------
# Result envelope — provenance is not optional
# -----------------------------------------------------------------------------


class Provenance(BaseModel):
    sql_hash: str
    row_ids: list[int] = []
    crime_nos: list[str] = []


class ToolResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    data: Any
    provenance: Provenance


class ToolDenied(Exception):
    """Raised at the tool boundary when a principal is out of scope or lacks the role."""


def sql_hash(sql: str, params: dict | None = None) -> str:
    payload = sql.strip() + "|" + json.dumps(params or {}, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


# -----------------------------------------------------------------------------
# Scope resolution — Unit.parent_unit recursive CTE + role ladder
# -----------------------------------------------------------------------------

_SUBTREE_SQL = text(
    """
    WITH RECURSIVE subtree AS (
        SELECT unit_id FROM ksp.unit WHERE unit_id = :root
        UNION ALL
        SELECT u.unit_id FROM ksp.unit u JOIN subtree s ON u.parent_unit = s.unit_id
    )
    SELECT unit_id FROM subtree
    """
)


def units_in_scope(principal: Principal, session: Session) -> set[int] | None:
    """The set of station/unit ids this principal may see. ``None`` means unrestricted
    (state-wide). SHO/Constable → own unit; DySP → the parent_unit subtree; SP → their
    district; analyst/policymaker → state (None)."""
    role = principal.role
    if role in STATE_SCOPE_ROLES:
        return None
    if role == Role.SP:
        rows = session.execute(
            text("SELECT unit_id FROM ksp.unit WHERE district_id = :d"),
            {"d": principal.district_id},
        )
        return {r[0] for r in rows}
    if role == Role.DYSP:
        rows = session.execute(_SUBTREE_SQL, {"root": principal.unit_id})
        return {r[0] for r in rows}
    # SHO / Constable: their own station only
    return {principal.unit_id} if principal.unit_id is not None else set()


def apply_k_anonymity(
    rows: list[dict], count_field: str, k: int = K_ANONYMITY_THRESHOLD
) -> list[dict]:
    """Drop any row whose count is below ``k`` — small cells can re-identify individuals."""
    return [r for r in rows if (r.get(count_field) or 0) >= k]


# -----------------------------------------------------------------------------
# Tool base class
# -----------------------------------------------------------------------------


class Tool(ABC):
    name: ClassVar[str]
    description: ClassVar[str]
    Params: ClassVar[type[BaseModel]]
    # returns rows about identifiable people? then analyst/policymaker are denied.
    person_level: ClassVar[bool] = False
    # is this an aggregate/statistics tool? then k-anonymity applies for aggregate roles.
    aggregate: ClassVar[bool] = False
    # for aggregate tools: which field in each data row holds the suppressible count.
    count_field: ClassVar[str | None] = None

    def run(self, principal: Principal, raw_params: dict, session: Session) -> ToolResult:
        """Validate params, enforce RBAC, execute, apply k-anonymity, and audit —
        every path writes exactly one audit row."""
        params = self.Params.model_validate(raw_params or {})
        try:
            if self.person_level and principal.role in PERSON_TOOL_DISABLED_ROLES:
                raise ToolDenied(f"role '{principal.role.value}' may not access person-level data")
            result = self._run(principal, params, session)
        except ToolDenied as denied:
            self._audit(session, principal, params, 0, denied=True, reason=str(denied))
            raise

        if self.aggregate and self.count_field and principal.role in AGGREGATE_ONLY_ROLES:
            if isinstance(result.data, list):
                result.data = apply_k_anonymity(result.data, self.count_field)

        self._audit(session, principal, params, len(result.provenance.row_ids), denied=False)
        return result

    @abstractmethod
    def _run(self, principal: Principal, params: BaseModel, session: Session) -> ToolResult:
        """The tool's actual work. Must return a ToolResult with populated provenance.
        Raise ToolDenied for out-of-scope access (the base class audits it)."""

    # --- scope helpers a tool can call in _run ---

    def assert_unit_in_scope(
        self, principal: Principal, unit_id: int | None, session: Session
    ) -> None:
        scope = units_in_scope(principal, session)
        if scope is not None and unit_id not in scope:
            raise ToolDenied(
                f"unit {unit_id} is outside the scope of role '{principal.role.value}'"
            )

    def scope_clause(
        self, principal: Principal, session: Session, column: str = "police_station_id"
    ):
        """Return (sql_fragment, params) restricting ``column`` to the principal's units,
        or ('', {}) if state-wide. Lets aggregate tools filter without leaking scope logic."""
        scope = units_in_scope(principal, session)
        if scope is None:
            return "", {}
        if not scope:
            return f" AND {column} = -1", {}  # empty scope -> match nothing
        return f" AND {column} = ANY(:scope_units)", {"scope_units": list(scope)}

    # --- audit ---

    def _audit(self, session, principal, params, row_count, denied, reason=None) -> None:
        session.execute(
            text(
                "INSERT INTO derived.audit_log "
                "(principal_name, principal_role, principal_unit, principal_district, "
                " tool, params, row_count, denied, denial_reason) "
                "VALUES (:name, :role, :unit, :district, :tool, "
                "        CAST(:params AS jsonb), :rows, :denied, :reason)"
            ),
            {
                "name": principal.name,
                "role": principal.role.value,
                "unit": principal.unit_id,
                "district": principal.district_id,
                "tool": self.name,
                "params": params.model_dump_json(),
                "rows": row_count,
                "denied": denied,
                "reason": reason,
            },
        )
        session.commit()


# -----------------------------------------------------------------------------
# Registry — emits Anthropic tool-use schemas
# -----------------------------------------------------------------------------


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> Tool:
        if tool.name in self._tools:
            raise ValueError(f"tool '{tool.name}' already registered")
        self._tools[tool.name] = tool
        return tool

    def get(self, name: str) -> Tool:
        if name not in self._tools:
            raise KeyError(f"unknown tool '{name}'")
        return self._tools[name]

    def names(self) -> list[str]:
        return sorted(self._tools)

    def anthropic_schemas(self) -> list[dict]:
        """The tool-use JSON schema block passed to the Claude API (P14)."""
        out = []
        for name in self.names():
            tool = self._tools[name]
            out.append(
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.Params.model_json_schema(),
                }
            )
        return out

    def call(
        self, name: str, principal: Principal, raw_params: dict, session: Session
    ) -> ToolResult:
        return self.get(name).run(principal, raw_params, session)
