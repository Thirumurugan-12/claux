"""Run the P14 evaluation set and print a pass rate + a multi-turn transcript.

    python -m app.api.run_eval            # offline: golden scripts drive a ScriptedClient
    python -m app.api.run_eval --live      # live: the real model picks the tools

The offline path proves the loop mechanics, provenance chaining, the RBAC-denial path, and
the refusal path deterministically with no API key. The live path additionally proves that
Claude routes each question to the right tool. Grading is identical on both paths:

  * TOOL_OK  — the expected tool fired and succeeded.
  * DENIED   — the expected tool fired and was denied at the boundary (RBAC works).
  * REFUSE   — no tool returned data and the answer declined to invent one.
"""

from __future__ import annotations

import argparse
import sys

from app.api.eval_set import (
    EvalCase,
    Expect,
    build_cases,
    load_fixtures,
    multi_turn_demo,
)
from app.api.llm import LLMClient, ScriptedClient
from app.api.orchestrator import ChatResult, Orchestrator
from app.config import get_settings
from app.db import SessionLocal
from app.tools.catalog import build_registry


def grade(case: EvalCase, result: ChatResult) -> tuple[bool, str]:
    """Return (passed, note). Grading depends only on which tools fired and whether they
    succeeded — never on the exact wording of the answer."""
    ok_calls = [c for c in result.tool_calls if c.ok]
    denied_calls = [c for c in result.tool_calls if not c.ok]

    if case.expect is Expect.TOOL_OK:
        hit = any(c.tool == case.tool for c in ok_calls)
        return hit, f"expected ok call to {case.tool}; tools ran: {_names(result)}"
    if case.expect is Expect.DENIED:
        hit = any(c.tool == case.tool for c in denied_calls)
        # and it must NOT have leaked data via some other successful person/case call
        clean = not ok_calls
        return (hit and clean), f"expected denial of {case.tool}; tools ran: {_names(result)}"
    # REFUSE: nothing should have returned data; the model must not have invented a tool call
    return (not ok_calls), f"expected refusal, no data tool; tools ran: {_names(result)}"


def _names(result: ChatResult) -> str:
    if not result.tool_calls:
        return "(none)"
    return ", ".join(f"{c.tool}{'' if c.ok else '!denied'}" for c in result.tool_calls)


def client_for(case: EvalCase, live: bool) -> LLMClient:
    if live:
        from app.api.llm import AnthropicClient

        s = get_settings()
        return AnthropicClient(model=s.orchestration_model, api_key=s.anthropic_api_key or None)
    return ScriptedClient(case.turns)


def run(live: bool) -> int:
    session = SessionLocal()
    try:
        fx = load_fixtures(session)
        registry = build_registry()
        cases = build_cases(fx)

        print(f"\nP14 orchestration eval — {len(cases)} cases  ({'LIVE' if live else 'offline'})")
        print("=" * 72)
        passed = 0
        by_kind: dict[str, list[int]] = {"tool_ok": [0, 0], "denied": [0, 0], "refuse": [0, 0]}
        for case in cases:
            orch = Orchestrator(registry, client_for(case, live))
            try:
                result = orch.chat(case.principal, case.question, session)
            except Exception as exc:  # a crash is a failure, not a stop
                print(f"  ✗ {case.id:28s} EXCEPTION {exc}")
                by_kind[case.expect.value][1] += 1
                continue
            ok, note = grade(case, result)
            by_kind[case.expect.value][0 if ok else 1] += 1
            passed += ok
            mark = "✓" if ok else "✗"
            print(f"  {mark} {case.id:28s} [{case.expect.value:8s}] {_names(result)}")
            if not ok:
                print(f"      ↳ {note}")

        total = len(cases)
        print("-" * 72)
        for kind, (p, f) in by_kind.items():
            print(f"  {kind:8s}: {p}/{p + f} passed")
        rate = passed / total * 100 if total else 0.0
        print(f"\nPASS RATE: {passed}/{total} = {rate:.1f}%\n")

        _print_multi_turn(session, registry, fx, live)
        return 0 if passed == total else 1
    finally:
        session.close()


def _print_multi_turn(session, registry, fx, live) -> None:
    """A single conversation across turns: resolve a person, drill into one of their cases,
    then ask something unanswerable — showing context carried forward AND the refusal."""
    print("MULTI-TURN TRANSCRIPT")
    print("=" * 72)
    steps = multi_turn_demo(fx)
    if live:
        from app.api.llm import AnthropicClient

        s = get_settings()
        llm = AnthropicClient(model=s.orchestration_model, api_key=s.anthropic_api_key or None)
        orch = Orchestrator(registry, llm)
        history = None
        for principal, msg, _turns in steps:
            print(f"\n  USER ({principal.role.value}): {msg}")
            result = orch.chat(principal, msg, session, history)
            history = result.messages
            print(f"  ASSISTANT: {result.answer}")
            print(f"  provenance — crime_nos: {result.crime_nos or '(none)'}")
        return
    # offline: one ScriptedClient replays all turns of the single conversation in order
    flat = [t for _, _, turns in steps for t in turns]
    llm = ScriptedClient(flat)
    orch = Orchestrator(registry, llm)
    history = None
    for principal, msg, _turns in steps:
        print(f"\n  USER ({principal.role.value}): {msg}")
        result = orch.chat(principal, msg, session, history)
        history = result.messages
        print(f"  ASSISTANT: {result.answer}")
        print(f"  provenance — crime_nos: {result.crime_nos or '(none)'}")
    print()


def main() -> None:
    ap = argparse.ArgumentParser(description="Run the P14 orchestration eval set.")
    ap.add_argument("--live", action="store_true", help="use the real Anthropic model")
    args = ap.parse_args()
    sys.exit(run(args.live))


if __name__ == "__main__":
    main()
