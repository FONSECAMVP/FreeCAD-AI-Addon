"""
Tests for LLMWorker async logic — REQ-011 (non-blocking, tool dispatch).
Tests the pure-async run_chat() function, not the QThread wrapper.
Qt integration tested manually (requires display).
"""

from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.fast


@pytest.fixture()
def mock_registry(registry):
    from freecad_ai.tools.inspection import register_tools

    register_tools(registry)
    return registry


async def _run_worker_logic(messages, tools_for_llm, client, executor):
    """Call the extracted async core so it's testable without Qt."""
    from freecad_ai.worker import run_chat

    tokens = []
    tool_results = []
    errors = []

    async def on_token(t):
        tokens.append(t)

    async def on_tool_call(tc_id, name, args):
        result = executor.dispatch(name, args)
        tool_results.append(result)
        return result

    async def on_error(msg):
        errors.append(msg)

    await run_chat(
        client=client,
        messages=messages,
        tools=tools_for_llm,
        on_token=on_token,
        on_tool_call=on_tool_call,
        on_error=on_error,
    )
    return tokens, tool_results, errors


@pytest.fixture()
def mock_client():
    from freecad_ai.llm_client import LLMClient

    client = MagicMock(spec=LLMClient)
    return client


# REQ-011: tokens delivered via on_token callback
@pytest.mark.asyncio
async def test_run_chat_delivers_tokens(mock_fc, mock_registry, mock_client):
    from freecad_ai.executor import ToolExecutor

    async def fake_chat(messages, tools):
        yield "Hello "
        yield "world"

    mock_client.chat = fake_chat
    ex = ToolExecutor(mock_registry)

    tokens, tool_results, errors = await _run_worker_logic(
        messages=[],
        tools_for_llm=[],
        client=mock_client,
        executor=ex,
    )
    assert tokens == ["Hello ", "world"]
    assert errors == []


# REQ-011: tool calls dispatched via on_tool_call callback
@pytest.mark.asyncio
async def test_run_chat_dispatches_tool_calls(mock_fc, mock_registry, mock_client):
    from freecad_ai.executor import ToolExecutor
    from freecad_ai.llm_client import ToolCall

    async def fake_chat(messages, tools):
        yield ToolCall(id="tc1", name="list_objects", args={})

    mock_client.chat = fake_chat
    ex = ToolExecutor(mock_registry)

    tokens, tool_results, errors = await _run_worker_logic(
        messages=[],
        tools_for_llm=[],
        client=mock_client,
        executor=ex,
    )
    assert len(tool_results) == 1
    assert "error" not in tool_results[0]
    assert "objects" in tool_results[0]


# REQ-011: LLMError captured via on_error, not raised
@pytest.mark.asyncio
async def test_run_chat_captures_llm_error(mock_fc, mock_registry, mock_client):
    from freecad_ai.executor import ToolExecutor
    from freecad_ai.llm_client import LLMError

    async def fake_chat(messages, tools):
        raise LLMError("connection refused")
        yield  # make it a generator

    mock_client.chat = fake_chat
    ex = ToolExecutor(mock_registry)

    tokens, tool_results, errors = await _run_worker_logic(
        messages=[],
        tools_for_llm=[],
        client=mock_client,
        executor=ex,
    )
    assert len(errors) == 1
    assert "connection refused" in errors[0]


# REQ-011: mixed tokens and tool calls — order preserved
@pytest.mark.asyncio
async def test_run_chat_mixed_output(mock_fc, mock_registry, mock_client):
    from freecad_ai.executor import ToolExecutor
    from freecad_ai.llm_client import ToolCall

    async def fake_chat(messages, tools):
        yield "Listing objects..."
        yield ToolCall(id="tc1", name="list_objects", args={})

    mock_client.chat = fake_chat
    ex = ToolExecutor(mock_registry)

    tokens, tool_results, errors = await _run_worker_logic(
        messages=[],
        tools_for_llm=[],
        client=mock_client,
        executor=ex,
    )
    assert tokens == ["Listing objects..."]
    assert len(tool_results) == 1
