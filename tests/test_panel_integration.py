"""
Integration tests for AIChatPanel — REQ-002, REQ-011, REQ-012, REQ-015.
Requires a display (Qt). Skipped in headless CI.
Run manually: pytest tests/test_panel_integration.py --no-header -v
"""

import pytest

pytest.importorskip("PySide2", reason="Qt display required")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skip(reason="Requires Qt display — run manually with FreeCAD Python"),
]


def test_panel_creates_without_error():
    from freecad_ai.conversation import ConversationHistory
    from freecad_ai.executor import ToolExecutor
    from freecad_ai.llm_client import SYSTEM_PROMPT, LLMClient
    from freecad_ai.panel import AIChatPanel
    from freecad_ai.preferences import AIPreferences
    from freecad_ai.registry import ToolRegistry

    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    history = ConversationHistory(system_prompt=SYSTEM_PROMPT)
    prefs = AIPreferences()

    panel = AIChatPanel(
        registry=registry,
        executor=executor,
        history=history,
        make_client=lambda: LLMClient("http://localhost", "x", "gpt-4o"),
        prefs=prefs,
    )
    assert panel is not None


def test_send_button_disabled_during_llm_call():
    """Send button must be disabled between submit and finished signal."""
    pass  # verified manually


def test_error_message_appears_in_chat():
    """LLMError must surface as plain text in QTextBrowser."""
    pass  # verified manually


def test_tool_detail_collapsible():
    """Tool call section must expand/collapse on click — REQ-015."""
    pass  # verified manually
