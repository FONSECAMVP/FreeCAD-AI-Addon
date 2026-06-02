"""
A3 hardening tests — mutation targets, boundary sweeps, negative paths.
REQ: all "must" REQs, especially REQ-020/024/025 safety properties.
"""

import json
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.fast


# ------------------------------------------------------------------ Registry


def test_registry_empty_on_init(registry):
    assert registry.get_tools_for_llm() == []


def test_registry_dispatch_unknown_tool_never_raises(registry):
    result = registry.dispatch("__nonexistent__", {"x": 1})
    assert isinstance(result, dict)
    assert result["error"] == "unknown_tool"


def test_registry_handler_exception_does_not_propagate_raw(mock_fc, registry):
    """Executor must absorb handler exception — never raise to caller."""
    from freecad_ai.executor import ToolExecutor

    schema = {
        "type": "function",
        "function": {
            "name": "boom",
            "description": "",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    }
    registry.register(
        "boom", schema, lambda a: (_ for _ in ()).throw(RuntimeError("kaboom")), workbench="Part"
    )
    ex = ToolExecutor(registry)
    result = ex.dispatch("boom", {})
    assert result["error"] == "execution"
    assert "kaboom" in result["message"]


# ------------------------------------------------------------------ Executor boundaries


@pytest.mark.parametrize(
    "label",
    [
        "",  # empty string
        " ",  # space only
        "a" * 129,  # over 128 chars
        "../etc",  # path traversal
        "$(rm -rf /)",  # shell injection attempt
        "<script>",  # xss attempt
        "a\x00b",  # null byte
    ],
)
def test_executor_rejects_all_invalid_string_args(mock_fc, registry, label):
    from freecad_ai.executor import ToolExecutor

    schema = {
        "type": "function",
        "function": {
            "name": "labeled",
            "description": "",
            "parameters": {
                "type": "object",
                "properties": {"label": {"type": "string"}},
                "required": ["label"],
            },
        },
    }
    registry.register("labeled", schema, lambda a: {"ok": True}, workbench="Part")
    ex = ToolExecutor(registry)
    result = ex.dispatch("labeled", {"label": label})
    assert result.get("error") == "validation", f"should reject label={label!r}"


@pytest.mark.parametrize(
    "label",
    [
        "Box",
        "My Part",
        "Part-001",
        "part_v2",
        "A",
        "a" * 128,  # exactly 128 — boundary
    ],
)
def test_executor_accepts_all_valid_string_args(mock_fc, registry, label):
    from freecad_ai.executor import ToolExecutor

    schema = {
        "type": "function",
        "function": {
            "name": "labeled",
            "description": "",
            "parameters": {
                "type": "object",
                "properties": {"label": {"type": "string"}},
                "required": ["label"],
            },
        },
    }
    # Fresh registry per param (avoid duplicate registration)
    from freecad_ai.registry import ToolRegistry

    r = ToolRegistry()
    r.register("labeled", schema, lambda a: {"ok": True}, workbench="Part")
    ex = ToolExecutor(r)
    result = ex.dispatch("labeled", {"label": label})
    assert "error" not in result, f"should accept label={label!r}"


def test_executor_missing_required_arg_returns_validation_error(mock_fc, registry):
    from freecad_ai.executor import ToolExecutor

    schema = {
        "type": "function",
        "function": {
            "name": "needs_x",
            "description": "",
            "parameters": {
                "type": "object",
                "properties": {"x": {"type": "number"}},
                "required": ["x"],
            },
        },
    }
    registry.register("needs_x", schema, lambda a: {"ok": True}, workbench="Part")
    ex = ToolExecutor(registry)
    result = ex.dispatch("needs_x", {})  # x missing
    assert result["error"] == "validation"
    assert result["field"] == "x"


def test_executor_wrong_type_arg_returns_validation_error(mock_fc, registry):
    from freecad_ai.executor import ToolExecutor

    schema = {
        "type": "function",
        "function": {
            "name": "num_tool",
            "description": "",
            "parameters": {
                "type": "object",
                "properties": {"x": {"type": "number"}},
                "required": ["x"],
            },
        },
    }
    registry.register("num_tool", schema, lambda a: {"ok": True}, workbench="Part")
    ex = ToolExecutor(registry)
    result = ex.dispatch("num_tool", {"x": "not_a_number"})
    assert result["error"] == "validation"


def test_executor_busy_flag_blocks_dispatch(mock_fc, registry):
    from freecad_ai.executor import ToolExecutor

    schema = {
        "type": "function",
        "function": {
            "name": "t",
            "description": "",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    }
    registry.register("t", schema, lambda a: {"ok": True}, workbench="Part")
    ex = ToolExecutor(registry)
    ex.set_busy(True)
    result = ex.dispatch("t", {})
    assert result["error"] == "busy"


def test_executor_aborts_on_mid_call_exception(mock_fc, registry):
    from freecad_ai.executor import ToolExecutor

    schema = {
        "type": "function",
        "function": {
            "name": "mid_fail",
            "description": "",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    }

    def handler(args):
        raise ValueError("mid-call failure")

    registry.register("mid_fail", schema, handler, workbench="Part")
    ex = ToolExecutor(registry)
    ex.dispatch("mid_fail", {})
    mock_fc.ActiveDocument.abortTransaction.assert_called_once()
    mock_fc.ActiveDocument.commitTransaction.assert_not_called()


# ------------------------------------------------------------------ Conversation boundaries


def test_conversation_system_message_never_dropped():
    from freecad_ai.conversation import ConversationHistory

    h = ConversationHistory(system_prompt="SYS", max_tokens=1)
    for i in range(100):
        h.add_user(f"message {i} " * 50)
    assert h.messages()[0]["role"] == "system"
    assert h.messages()[0]["content"] == "SYS"


def test_conversation_truncation_never_exceeds_max():
    from freecad_ai.conversation import ConversationHistory

    h = ConversationHistory(system_prompt="SYS", max_tokens=500)
    for _ in range(200):
        h.add_user("word " * 30)
    estimate = len(json.dumps(h.messages())) // 4
    assert estimate <= 500


def test_conversation_clear_preserves_system_only():
    from freecad_ai.conversation import ConversationHistory

    h = ConversationHistory(system_prompt="SYS", max_tokens=8000)
    h.add_user("hello")
    h.add_assistant("hi", tool_calls=None)
    h.clear()
    msgs = h.messages()
    assert len(msgs) == 1
    assert msgs[0]["role"] == "system"


# ------------------------------------------------------------------ Context boundaries


def test_context_with_25_objects_caps_at_20(mock_fc):
    from freecad_ai.context import build_context

    objs = []
    for i in range(25):
        o = MagicMock()
        o.Label = f"Obj{i:02d}"
        o.TypeId = "Part::Box"
        objs.append(o)
    mock_fc.ActiveDocument.Objects = objs
    mock_fc.ActiveDocument.Name = "BigDoc"
    ctx = build_context()
    assert "Obj24" not in ctx


def test_context_total_length_never_exceeds_500(mock_fc):
    from freecad_ai.context import build_context

    objs = []
    for i in range(20):
        o = MagicMock()
        o.Label = "VeryLongObjectLabelThatTakesUpLotsOfSpace" + str(i)
        o.TypeId = "Part::Box"
        objs.append(o)
    mock_fc.ActiveDocument.Objects = objs
    mock_fc.ActiveDocument.Name = "Doc"
    ctx = build_context()
    assert len(ctx) <= 500


# ------------------------------------------------------------------ No exec/eval in source


def test_no_exec_eval_in_source():
    import os
    import re

    pattern = re.compile(r"\bexec\s*\(|\beval\s*\(")
    src_root = os.path.join(os.path.dirname(__file__), "..", "freecad_ai")
    violations = []
    for dirpath, _, files in os.walk(src_root):
        for fname in files:
            if not fname.endswith(".py"):
                continue
            fpath = os.path.join(dirpath, fname)
            with open(fpath) as f:
                for lineno, line in enumerate(f, 1):
                    if pattern.search(line):
                        violations.append(f"{fpath}:{lineno}: {line.rstrip()}")
    assert violations == [], "exec/eval found in source:\n" + "\n".join(violations)


# ------------------------------------------------------------------ LLM client


@pytest.mark.asyncio
async def test_llm_client_empty_tools_sends_none():
    """If no tools registered, tools param must be None not []."""
    from unittest.mock import AsyncMock, patch

    from freecad_ai.llm_client import LLMClient

    async def empty_stream():
        return
        yield

    client = LLMClient("http://localhost", "key", "gpt-4o")
    mock_create = AsyncMock(return_value=empty_stream())
    with patch.object(client._client.chat.completions, "create", mock_create):
        async for _ in client.chat(messages=[], tools=[]):
            pass
    call_kwargs = mock_create.call_args.kwargs
    assert call_kwargs["tools"] is None


@pytest.mark.asyncio
async def test_llm_client_with_tools_sends_tool_list():
    from unittest.mock import AsyncMock, patch

    from freecad_ai.llm_client import LLMClient

    async def empty_stream():
        return
        yield

    tools = [{"type": "function", "function": {"name": "t"}}]
    client = LLMClient("http://localhost", "key", "gpt-4o")
    mock_create = AsyncMock(return_value=empty_stream())
    with patch.object(client._client.chat.completions, "create", mock_create):
        async for _ in client.chat(messages=[], tools=tools):
            pass
    assert mock_create.call_args.kwargs["tools"] == tools
