"""P14 — assert the orchestration eval set passes end to end on the offline (scripted) path.

This is the acceptance test: every registered tool has a question that routes to it, every
RBAC case is denied at the boundary, and every unanswerable question is refused with no tool
call. It also checks the eval covers every tool in the catalogue, so a newly-registered tool
without a question fails the suite loudly.
"""

from __future__ import annotations

import pytest

from app.api.eval_set import Expect, build_cases, load_fixtures
from app.api.llm import ScriptedClient
from app.api.orchestrator import Orchestrator
from app.api.run_eval import grade
from app.db import SessionLocal
from app.tools.catalog import build_registry


@pytest.fixture(scope="module")
def session():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def test_eval_set_passes_offline(session):
    fx = load_fixtures(session)
    registry = build_registry()
    cases = build_cases(fx)
    assert len(cases) >= 25, "expected ~30 eval questions"

    failures = []
    for case in cases:
        orch = Orchestrator(registry, ScriptedClient(case.turns))
        result = orch.chat(case.principal, case.question, session)
        ok, note = grade(case, result)
        if not ok:
            failures.append(f"{case.id}: {note}")
    assert not failures, "eval cases failed:\n" + "\n".join(failures)


def test_every_tool_has_a_question(session):
    fx = load_fixtures(session)
    registry = build_registry()
    covered = {c.tool for c in build_cases(fx) if c.expect is Expect.TOOL_OK}
    registered = set(registry.names())
    assert registered <= covered, f"tools with no eval question: {registered - covered}"


def test_eval_has_refusal_and_rbac_cases(session):
    fx = load_fixtures(session)
    cases = build_cases(fx)
    assert sum(c.expect is Expect.REFUSE for c in cases) >= 4
    assert sum(c.expect is Expect.DENIED for c in cases) >= 2
