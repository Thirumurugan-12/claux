"""Tests for the Catalyst UniAI / OpenAI-compatible gateway client.

All offline via httpx.MockTransport — these pin the wire-format translation in both
directions, which is the risky part of swapping providers:

  * request: our Anthropic-style message list (tool_use / tool_result blocks) must become
    OpenAI chat-completions messages (assistant.tool_calls / role:"tool" results), and the
    registry's {name, description, input_schema} tools must become {"type": "function", ...};
  * response: choices[0].message.tool_calls must come back as ToolUseBlock with parsed args,
    and finish_reason "tool_calls" must map to stop_reason "tool_use" so the orchestration
    loop keeps running.

Plus an end-to-end orchestrator round-trip against a fake gateway, proving the whole P14
loop works over this client — i.e. the demo path with a Catalyst-issued key.
"""

from __future__ import annotations

import json

import httpx
import pytest

from app.api.llm import OpenAICompatClient, client_from_settings


def make_client(handler, **kwargs) -> OpenAICompatClient:
    defaults = dict(
        base_url="https://uniai.test",
        api_key="demo-key",
        model="demo-model",
        transport=httpx.MockTransport(handler),
    )
    defaults.update(kwargs)
    return OpenAICompatClient(**defaults)


def _ok(payload: dict) -> httpx.Response:
    return httpx.Response(200, json=payload)


def _final_text_response(text="hello"):
    return _ok(
        {
            "choices": [
                {"finish_reason": "stop", "message": {"role": "assistant", "content": text}}
            ]
        }
    )


# --- request translation ------------------------------------------------------


def test_request_carries_auth_model_and_openai_tools():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["Authorization"]
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return _final_text_response()

    client = make_client(handler, tool_mode="native")
    tools = [
        {
            "name": "get_case",
            "description": "Fetch one FIR.",
            "input_schema": {"type": "object", "properties": {"case_master_id": {}}},
        }
    ]
    client.complete("SYS", [{"role": "user", "content": "hi"}], tools)

    assert seen["auth"] == "Bearer demo-key"
    assert seen["url"] == "https://uniai.test/v1/chat/completions"
    body = seen["body"]
    assert body["model"] == "demo-model"
    assert body["messages"][0] == {"role": "system", "content": "SYS"}
    assert body["messages"][1] == {"role": "user", "content": "hi"}
    tool = body["tools"][0]
    assert tool["type"] == "function"
    assert tool["function"]["name"] == "get_case"
    assert tool["function"]["parameters"]["type"] == "object"


def test_zoho_oauthtoken_auth_scheme():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["Authorization"]
        return _final_text_response()

    client = make_client(handler, auth_scheme="zoho-oauthtoken")
    client.complete("s", [{"role": "user", "content": "q"}], [])
    assert seen["auth"] == "Zoho-oauthtoken demo-key"


def test_anthropic_blocks_translate_to_openai_shape():
    """A full prior round — assistant tool_use + user tool_result — must serialise as
    assistant.tool_calls followed by a role:'tool' message with the matching id."""
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return _final_text_response()

    history = [
        {"role": "user", "content": "show case 7"},
        {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Looking it up."},
                {"type": "tool_use", "id": "call_1", "name": "get_case",
                 "input": {"case_master_id": 7}},
            ],
        },
        {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "call_1", "content": '{"data": 1}'}
            ],
        },
    ]
    make_client(handler, tool_mode="native").complete("s", history, [])

    msgs = seen["body"]["messages"]
    assistant = msgs[2]
    assert assistant["role"] == "assistant"
    assert assistant["content"] == "Looking it up."
    tc = assistant["tool_calls"][0]
    assert tc == {
        "id": "call_1",
        "type": "function",
        "function": {"name": "get_case", "arguments": '{"case_master_id": 7}'},
    }
    tool_msg = msgs[3]
    assert tool_msg == {"role": "tool", "tool_call_id": "call_1", "content": '{"data": 1}'}


# --- response mapping ---------------------------------------------------------


def test_tool_calls_response_maps_to_tool_use():
    def handler(request: httpx.Request) -> httpx.Response:
        return _ok(
            {
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_9",
                                    "type": "function",
                                    "function": {
                                        "name": "search_cases",
                                        "arguments": '{"district_id": 3, "limit": 5}',
                                    },
                                }
                            ],
                        },
                    }
                ]
            }
        )

    resp = make_client(handler, tool_mode="native").complete(
        "s", [{"role": "user", "content": "q"}], []
    )
    assert resp.stop_reason == "tool_use"
    (tu,) = resp.tool_uses
    assert tu.id == "call_9"
    assert tu.name == "search_cases"
    assert tu.input == {"district_id": 3, "limit": 5}  # arguments string was parsed


def test_plain_answer_maps_to_end_turn():
    resp = make_client(lambda r: _final_text_response("The answer.")).complete(
        "s", [{"role": "user", "content": "q"}], []
    )
    assert resp.stop_reason == "stop" or resp.stop_reason == "end_turn"
    assert resp.text == "The answer."
    assert resp.tool_uses == []


def test_gateway_error_raises_with_status():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="bad key")

    with pytest.raises(RuntimeError, match="401"):
        make_client(handler).complete("s", [{"role": "user", "content": "q"}], [])


# --- configuration ------------------------------------------------------------


def test_missing_config_raises_actionable_errors():
    with pytest.raises(RuntimeError, match="UNIAI_BASE_URL"):
        OpenAICompatClient(base_url="", api_key="k", model="m")
    with pytest.raises(RuntimeError, match="UNIAI_API_KEY"):
        OpenAICompatClient(base_url="https://x", api_key="", model="m")
    with pytest.raises(RuntimeError, match="UNIAI_MODEL"):
        OpenAICompatClient(base_url="https://x", api_key="k", model="")


def test_client_from_settings_dispatches_uniai():
    class S:
        llm_provider = "uniai"
        uniai_base_url = "https://uniai.test"
        uniai_api_key = "k"
        uniai_model = "m"
        uniai_chat_path = "/v1/chat/completions"
        uniai_auth_scheme = "bearer"

    client = client_from_settings(S())
    assert isinstance(client, OpenAICompatClient)


def test_client_from_settings_rejects_unknown_provider():
    class S:
        llm_provider = "wat"

    with pytest.raises(RuntimeError, match="LLM_PROVIDER"):
        client_from_settings(S())


# --- prompted tool-calling mode (works with any chat model) ------------------


def test_prompted_mode_injects_catalogue_and_omits_tools_param():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return _ok(
            {"choices": [{"finish_reason": "stop",
                          "message": {"role": "assistant", "content": '{"final": "hi"}'}}]}
        )

    client = make_client(handler, tool_mode="prompted")
    tools = [
        {"name": "get_case", "description": "Fetch one FIR.",
         "input_schema": {"type": "object", "properties": {"case_master_id": {}}}}
    ]
    client.complete("SYS", [{"role": "user", "content": "hi"}], tools)

    body = seen["body"]
    assert "tools" not in body, "prompted mode must NOT send the OpenAI tools param"
    system_msg = body["messages"][0]["content"]
    assert "get_case" in system_msg and '{"tool"' in system_msg  # catalogue + protocol


def test_prompted_mode_parses_tool_call_json():
    def handler(request: httpx.Request) -> httpx.Response:
        return _ok(
            {"choices": [{"finish_reason": "stop", "message": {"role": "assistant",
             "content": '{"tool": "get_case", "input": {"case_master_id": 7}}'}}]}
        )

    resp = make_client(handler, tool_mode="prompted").complete(
        "s", [{"role": "user", "content": "q"}], [{"name": "get_case", "description": "d",
                                                   "input_schema": {}}]
    )
    assert resp.stop_reason == "tool_use"
    (tu,) = resp.tool_uses
    assert tu.name == "get_case" and tu.input == {"case_master_id": 7}


def test_prompted_mode_parses_final_answer_and_tolerates_fences():
    def handler(request: httpx.Request) -> httpx.Response:
        return _ok(
            {"choices": [{"finish_reason": "stop", "message": {"role": "assistant",
             "content": '```json\n{"final": "The case is closed."}\n```'}}]}
        )

    resp = make_client(handler, tool_mode="prompted").complete(
        "s", [{"role": "user", "content": "q"}], [{"name": "t", "description": "d",
                                                   "input_schema": {}}]
    )
    assert resp.stop_reason == "end_turn"
    assert resp.text == "The case is closed."
    assert resp.tool_uses == []


def test_prompted_mode_non_json_degrades_to_plain_answer():
    def handler(request: httpx.Request) -> httpx.Response:
        return _ok(
            {"choices": [{"finish_reason": "stop", "message": {"role": "assistant",
             "content": "I cannot answer that with the available tools."}}]}
        )

    resp = make_client(handler, tool_mode="prompted").complete(
        "s", [{"role": "user", "content": "q"}], [{"name": "t", "description": "d",
                                                   "input_schema": {}}]
    )
    assert resp.stop_reason == "end_turn"
    assert "cannot answer" in resp.text


def test_prompted_mode_renders_tool_result_as_user_text():
    """A prior tool_result must come back as readable user text (not role:'tool'), since the
    endpoint may not accept OpenAI tool messages."""
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return _ok({"choices": [{"finish_reason": "stop",
                    "message": {"role": "assistant", "content": '{"final": "ok"}'}}]})

    history = [
        {"role": "user", "content": "show case 7"},
        {"role": "assistant", "content": [
            {"type": "tool_use", "id": "c1", "name": "get_case", "input": {"case_master_id": 7}}]},
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "c1", "content": '{"crime_no": "X"}'}]},
    ]
    make_client(handler, tool_mode="prompted").complete("s", history, [])

    roles = [m["role"] for m in seen["body"]["messages"]]
    assert "tool" not in roles  # never emits an OpenAI tool message in prompted mode
    joined = " ".join(m["content"] for m in seen["body"]["messages"] if m["role"] == "user")
    assert "TOOL RESULT" in joined and '{"crime_no": "X"}' in joined


def test_unknown_tool_mode_rejected():
    with pytest.raises(RuntimeError, match="tool_mode"):
        OpenAICompatClient(base_url="https://x", api_key="k", model="m", tool_mode="wat")


# --- end-to-end: the P14 loop over the gateway client ------------------------


def _a_case(session):
    from sqlalchemy import text as sql_text

    return (
        session.execute(
            sql_text(
                "SELECT c.case_master_id, c.crime_no, u.district_id "
                "FROM ksp.case_master c JOIN ksp.unit u ON u.unit_id = c.police_station_id "
                "WHERE c.police_station_id IS NOT NULL LIMIT 1"
            )
        )
        .mappings()
        .first()
    )


def test_orchestrator_round_trip_native_mode():
    """The native path end to end: the fake endpoint asks for get_case via OpenAI tool_calls,
    the orchestrator executes it through the registry (RBAC + provenance + audit), feeds the
    result back as a role:'tool' message, and the endpoint answers from it."""
    from app.api.orchestrator import Orchestrator
    from app.db import SessionLocal
    from app.tools.base import Principal, Role
    from app.tools.catalog import build_registry

    session = SessionLocal()
    try:
        case = _a_case(session)
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            calls["n"] += 1
            if calls["n"] == 1:
                return _ok(
                    {
                        "choices": [
                            {
                                "finish_reason": "tool_calls",
                                "message": {
                                    "role": "assistant",
                                    "content": None,
                                    "tool_calls": [
                                        {
                                            "id": "call_1",
                                            "type": "function",
                                            "function": {
                                                "name": "get_case",
                                                "arguments": json.dumps(
                                                    {"case_master_id": case["case_master_id"]}
                                                ),
                                            },
                                        }
                                    ],
                                },
                            }
                        ]
                    }
                )
            tool_msgs = [m for m in body["messages"] if m["role"] == "tool"]
            assert tool_msgs and tool_msgs[0]["tool_call_id"] == "call_1"
            crime_no = json.loads(tool_msgs[0]["content"])["data"]["crime_no"]
            return _final_text_response(f"Case {crime_no} retrieved.")

        orch = Orchestrator(build_registry(), make_client(handler, tool_mode="native"))
        principal = Principal(name="sp", role=Role.SP, district_id=case["district_id"])
        result = orch.chat(principal, "show me the case", session)

        assert result.answer == f"Case {case['crime_no']} retrieved."
        assert result.tool_calls[0].tool == "get_case" and result.tool_calls[0].ok
        assert case["crime_no"] in result.crime_nos
    finally:
        session.rollback()
        session.close()


def test_orchestrator_round_trip_prompted_mode():
    """The Catalyst-default path end to end: a plain chat model with NO native tool calling.
    It emits {"tool": ...} JSON, the orchestrator runs the tool and feeds the result back as
    TOOL RESULT user text, and the model then emits {"final": ...}."""
    from app.api.orchestrator import Orchestrator
    from app.db import SessionLocal
    from app.tools.base import Principal, Role
    from app.tools.catalog import build_registry

    session = SessionLocal()
    try:
        case = _a_case(session)
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            calls["n"] += 1
            if calls["n"] == 1:
                # never sent the OpenAI tools param; catalogue is in the system prompt
                assert "tools" not in body
                assert "get_case" in body["messages"][0]["content"]
                content = json.dumps(
                    {"tool": "get_case", "input": {"case_master_id": case["case_master_id"]}}
                )
            else:
                joined = " ".join(
                    m["content"] for m in body["messages"] if m["role"] == "user"
                )
                assert "TOOL RESULT" in joined
                crime_no = json.loads(joined.split("TOOL RESULT:", 1)[1])["data"]["crime_no"]
                content = json.dumps({"final": f"Case {crime_no} retrieved."})
            return _ok({"choices": [{"finish_reason": "stop",
                        "message": {"role": "assistant", "content": content}}]})

        orch = Orchestrator(build_registry(), make_client(handler, tool_mode="prompted"))
        principal = Principal(name="sp", role=Role.SP, district_id=case["district_id"])
        result = orch.chat(principal, "show me the case", session)

        assert result.answer == f"Case {case['crime_no']} retrieved."
        assert result.tool_calls[0].tool == "get_case" and result.tool_calls[0].ok
        assert case["crime_no"] in result.crime_nos
    finally:
        session.rollback()
        session.close()
