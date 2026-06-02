"""
Tests for conversation history — REQ-010, REQ-021.
"""

import pytest

pytestmark = pytest.mark.fast

SYSTEM_PROMPT = "You are a FreeCAD assistant."


@pytest.fixture()
def history():
    from freecad_ai.conversation import ConversationHistory

    return ConversationHistory(system_prompt=SYSTEM_PROMPT, max_tokens=200)


def test_initial_history_has_system_message(history):
    msgs = history.messages()
    assert msgs[0]["role"] == "system"
    assert msgs[0]["content"] == SYSTEM_PROMPT


def test_add_user_message(history):
    history.add_user("make a box")
    msgs = history.messages()
    assert msgs[-1] == {"role": "user", "content": "make a box"}


def test_add_assistant_message(history):
    history.add_assistant("Sure, creating box.", tool_calls=None)
    msgs = history.messages()
    assert msgs[-1]["role"] == "assistant"


def test_add_tool_result(history):
    history.add_tool_result(tool_call_id="tc1", content='{"label":"Box"}')
    msgs = history.messages()
    assert msgs[-1]["role"] == "tool"
    assert msgs[-1]["tool_call_id"] == "tc1"


# REQ-021: truncation keeps system message, drops oldest non-system
def test_truncation_keeps_system_message(history):
    # Fill history beyond max_tokens with user messages
    for i in range(50):
        history.add_user(f"message {i} " * 10)
    msgs = history.messages()
    assert msgs[0]["role"] == "system"


def test_truncation_respects_max_tokens(history):
    import json

    for i in range(50):
        history.add_user(f"message {i} " * 10)
    msgs = history.messages()
    token_estimate = len(json.dumps(msgs)) // 4
    assert token_estimate <= 200


def test_clear_resets_to_system_only(history):
    history.add_user("make a box")
    history.clear()
    msgs = history.messages()
    assert len(msgs) == 1
    assert msgs[0]["role"] == "system"


# Regression: OpenAI API rejects role=assistant + content=null + no tool_calls
# with `'content' must be string`. messages() must coerce None -> "" in that case.
def test_assistant_null_content_without_tool_calls_coerced_to_empty_string(history):
    history.add_assistant(None, tool_calls=None)
    msgs = history.messages()
    assistant_msg = msgs[-1]
    assert assistant_msg["role"] == "assistant"
    assert assistant_msg["content"] == ""
    assert "tool_calls" not in assistant_msg


# Regression: truncation must not leave orphaned tool/assistant messages at the
# start of history — OpenAI rejects "tool" messages with no preceding tool_calls.
def test_truncation_never_leaves_orphaned_tool_message():
    from freecad_ai.conversation import ConversationHistory

    # Small budget so the first turn gets evicted
    h = ConversationHistory(system_prompt=SYSTEM_PROMPT, max_tokens=50)
    tc = [{"id": "tc1", "type": "function", "function": {"name": "create_box", "arguments": "{}"}}]
    h.add_user("make a box")
    h.add_assistant(None, tool_calls=tc)
    h.add_tool_result("tc1", '{"label":"Box"}')
    # Second user turn pushes the first turn out of the token budget
    h.add_user("now make a cylinder " * 20)
    msgs = h.messages()
    roles = [m["role"] for m in msgs]
    assert roles[0] == "system"
    # First non-system message must be a user message, never tool or assistant
    non_system = [r for r in roles if r != "system"]
    assert not non_system or non_system[0] == "user", f"Orphaned leading role: {non_system}"


def test_assistant_null_content_with_tool_calls_kept_as_none(history):
    """When tool_calls is present, content=None is valid per OpenAI API; preserve it."""
    tc = [{"id": "tc1", "type": "function", "function": {"name": "f", "arguments": "{}"}}]
    history.add_assistant(None, tool_calls=tc)
    msgs = history.messages()
    assistant_msg = msgs[-1]
    assert assistant_msg["role"] == "assistant"
    assert assistant_msg["content"] is None
    assert assistant_msg["tool_calls"] == tc
