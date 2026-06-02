"""
Tests for LLM client wrapper — REQ-011, REQ-022.
All tests mock AsyncOpenAI so no real network calls occur.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.fast

SYSTEM_PROMPT = (
    "You are a FreeCAD assistant. When required parameters for a tool call are missing, "
    "ask the user for the missing information instead of guessing."
)


def _make_text_chunk(content: str):
    from openai.types.chat import ChatCompletionChunk
    from openai.types.chat.chat_completion_chunk import Choice, ChoiceDelta

    delta = ChoiceDelta(content=content, role="assistant", tool_calls=None)
    choice = Choice(delta=delta, index=0, finish_reason=None)
    return ChatCompletionChunk(
        id="ch1",
        choices=[choice],
        created=0,
        model="test",
        object="chat.completion.chunk",
    )


def _make_tool_chunk(index: int, tc_id: str, name: str, args_fragment: str):
    from openai.types.chat import ChatCompletionChunk
    from openai.types.chat.chat_completion_chunk import (
        Choice,
        ChoiceDelta,
        ChoiceDeltaToolCall,
        ChoiceDeltaToolCallFunction,
    )

    fn = ChoiceDeltaToolCallFunction(name=name, arguments=args_fragment)
    tc = ChoiceDeltaToolCall(index=index, id=tc_id, function=fn, type="function")
    delta = ChoiceDelta(content=None, role="assistant", tool_calls=[tc])
    choice = Choice(delta=delta, index=0, finish_reason=None)
    return ChatCompletionChunk(
        id="ch2",
        choices=[choice],
        created=0,
        model="test",
        object="chat.completion.chunk",
    )


def _make_done_chunk():
    from openai.types.chat import ChatCompletionChunk
    from openai.types.chat.chat_completion_chunk import Choice, ChoiceDelta

    delta = ChoiceDelta(content=None, role=None, tool_calls=None)
    choice = Choice(delta=delta, index=0, finish_reason="stop")
    return ChatCompletionChunk(
        id="ch3",
        choices=[choice],
        created=0,
        model="test",
        object="chat.completion.chunk",
    )


async def _async_iter(items):
    for item in items:
        yield item


@pytest.fixture()
def client():
    from freecad_ai.llm_client import LLMClient

    return LLMClient(base_url="http://localhost:11434/v1", api_key="test", model="gpt-4o")


# REQ-022: system prompt includes clarification instruction
def test_system_prompt_contains_clarification_instruction():
    assert "ask" in SYSTEM_PROMPT.lower() or "missing" in SYSTEM_PROMPT.lower()


# REQ-011: chat yields text tokens from streamed response
@pytest.mark.asyncio
async def test_chat_yields_text_tokens(client):
    chunks = [
        _make_text_chunk("Hello"),
        _make_text_chunk(" world"),
        _make_done_chunk(),
    ]
    mock_stream = _async_iter(chunks)

    with patch.object(
        client._client.chat.completions, "create", new_callable=AsyncMock, return_value=mock_stream
    ):
        tokens = []
        tool_calls = []
        async for item in client.chat(messages=[], tools=[]):
            if isinstance(item, str):
                tokens.append(item)
            else:
                tool_calls.append(item)

    assert tokens == ["Hello", " world"]
    assert tool_calls == []


# REQ-011: chat yields ToolCall when LLM emits tool_calls
@pytest.mark.asyncio
async def test_chat_yields_tool_calls(client):
    args_json = json.dumps({"length": 50.0, "width": 30.0, "height": 10.0})
    # Args arrive in two fragments (streaming)
    chunks = [
        _make_tool_chunk(0, "tc_abc", "create_box", args_json[:20]),
        _make_tool_chunk(0, "", "", args_json[20:]),
        _make_done_chunk(),
    ]
    mock_stream = _async_iter(chunks)

    with patch.object(
        client._client.chat.completions, "create", new_callable=AsyncMock, return_value=mock_stream
    ):
        results = []
        async for item in client.chat(messages=[], tools=[]):
            results.append(item)

    from freecad_ai.llm_client import ToolCall

    tool_calls = [r for r in results if isinstance(r, ToolCall)]
    assert len(tool_calls) == 1
    assert tool_calls[0].name == "create_box"
    assert tool_calls[0].args["length"] == 50.0
    assert tool_calls[0].id == "tc_abc"


# REQ-011: multiple tool calls in one response
@pytest.mark.asyncio
async def test_chat_yields_multiple_tool_calls(client):
    args1 = json.dumps({"length": 50.0, "width": 30.0, "height": 10.0})
    args2 = json.dumps({"radius": 5.0})
    chunks = [
        _make_tool_chunk(0, "tc1", "create_box", args1),
        _make_tool_chunk(1, "tc2", "create_cylinder", args2),
        _make_done_chunk(),
    ]
    mock_stream = _async_iter(chunks)

    with patch.object(
        client._client.chat.completions, "create", new_callable=AsyncMock, return_value=mock_stream
    ):
        from freecad_ai.llm_client import ToolCall

        results = [r async for r in client.chat(messages=[], tools=[])]
        tool_calls = [r for r in results if isinstance(r, ToolCall)]

    assert len(tool_calls) == 2
    names = {tc.name for tc in tool_calls}
    assert names == {"create_box", "create_cylinder"}


# REQ-011: malformed tool args JSON → args = {}
@pytest.mark.asyncio
async def test_chat_handles_malformed_tool_args(client):
    chunks = [
        _make_tool_chunk(0, "tc_bad", "create_box", "NOT_JSON"),
        _make_done_chunk(),
    ]
    mock_stream = _async_iter(chunks)

    with patch.object(
        client._client.chat.completions, "create", new_callable=AsyncMock, return_value=mock_stream
    ):
        from freecad_ai.llm_client import ToolCall

        results = [r async for r in client.chat(messages=[], tools=[])]
        tool_calls = [r for r in results if isinstance(r, ToolCall)]

    assert len(tool_calls) == 1
    assert tool_calls[0].args == {}


# REQ-011: HTTP error raises LLMError
@pytest.mark.asyncio
async def test_chat_raises_on_http_error(client):
    from openai import APIConnectionError

    err = APIConnectionError(request=MagicMock())

    with patch.object(
        client._client.chat.completions, "create", new_callable=AsyncMock, side_effect=err
    ):
        from freecad_ai.llm_client import LLMError

        with pytest.raises(LLMError):
            async for _ in client.chat(messages=[], tools=[]):
                pass


# REQ-011: messages and tools forwarded to openai create()
@pytest.mark.asyncio
async def test_chat_forwards_messages_and_tools(client):
    messages = [{"role": "user", "content": "make a box"}]
    tools = [{"type": "function", "function": {"name": "create_box"}}]
    mock_create = AsyncMock(return_value=_async_iter([_make_done_chunk()]))

    with patch.object(client._client.chat.completions, "create", mock_create):
        async for _ in client.chat(messages=messages, tools=tools):
            pass

    call_kwargs = mock_create.call_args.kwargs
    assert call_kwargs["messages"] == messages
    assert call_kwargs["tools"] == tools
    assert call_kwargs["model"] == "gpt-4o"
    assert call_kwargs["stream"] is True


# DEC-012 regression: exercise the real openai SDK SSE parser end-to-end on
# whatever Python version CI runs. Without this, the suite mocks past the SDK's
# response-parse path and cannot catch a Protocol-isinstance regression of the
# class that the in-source monkeypatch was trying to work around. This test
# fails loudly if openai SDK upgrades break streaming parse on the current Python.
@pytest.mark.asyncio
async def test_streaming_through_real_sdk_parser():
    import httpx

    from freecad_ai.llm_client import LLMClient

    sse_body = (
        b'data: {"id":"c1","object":"chat.completion.chunk","created":0,'
        b'"model":"m","choices":[{"index":0,"delta":{"role":"assistant",'
        b'"content":"Hello"},"finish_reason":null}]}\n\n'
        b'data: {"id":"c1","object":"chat.completion.chunk","created":0,'
        b'"model":"m","choices":[{"index":0,"delta":{"content":" world"},'
        b'"finish_reason":null}]}\n\n'
        b"data: [DONE]\n\n"
    )

    def handler(_request):
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=sse_body,
        )

    client = LLMClient("http://fake/v1", "k", "gpt-4o")
    client._client._client._transport = httpx.MockTransport(handler)

    out: list = []
    async for piece in client.chat(messages=[{"role": "user", "content": "hi"}], tools=[]):
        out.append(piece)

    assert out == ["Hello", " world"]
