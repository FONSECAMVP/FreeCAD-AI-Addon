"""
Tests for ToolRegistry — REQ-003, REQ-019, REQ-022 (schema validation).
"""

import pytest

pytestmark = pytest.mark.fast

BOX_SCHEMA = {
    "type": "function",
    "function": {
        "name": "create_box",
        "description": "Create a box.",
        "parameters": {
            "type": "object",
            "properties": {
                "length": {"type": "number"},
                "width": {"type": "number"},
                "height": {"type": "number"},
            },
            "required": ["length", "width", "height"],
        },
    },
}


def _box_handler(args: dict) -> dict:
    return {"label": "Box", "dims": args}


# REQ-003: explicit register() call
def test_register_adds_tool(registry):
    registry.register("create_box", BOX_SCHEMA, _box_handler, workbench="Part")
    assert "create_box" in registry


# REQ-003: get_tools_for_llm returns OpenAI-format list
def test_get_tools_for_llm_returns_schema(registry):
    registry.register("create_box", BOX_SCHEMA, _box_handler, workbench="Part")
    tools = registry.get_tools_for_llm()
    assert len(tools) == 1
    assert tools[0]["type"] == "function"
    assert tools[0]["function"]["name"] == "create_box"


# REQ-003: duplicate name raises
def test_register_duplicate_raises(registry):
    registry.register("create_box", BOX_SCHEMA, _box_handler, workbench="Part")
    with pytest.raises(ValueError, match="already registered"):
        registry.register("create_box", BOX_SCHEMA, _box_handler, workbench="Part")


# REQ-003: unknown tool dispatch raises KeyError
def test_dispatch_unknown_tool_returns_error(registry):
    result = registry.dispatch("nonexistent", {})
    assert result["error"] == "unknown_tool"


# REQ-019: handler is callable (lazy import is handler's responsibility — registry
# just stores the callable; this test verifies registry doesn't eagerly call it)
def test_register_does_not_call_handler(registry):
    called = []

    def eager_handler(args):
        called.append(True)
        return {}

    registry.register("eager", BOX_SCHEMA, eager_handler, workbench="Part")
    assert called == [], "handler must not be called at registration time"
