"""
AI Chat Panel — DES-008, REQ-002, REQ-011, REQ-012, REQ-015.

Qt import is deferred so this module is importable in headless mode.
All FreeCAD API calls happen in _on_tool_call_ready (main thread slot).
"""

from __future__ import annotations

import html
import json
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from freecad_ai.conversation import ConversationHistory
    from freecad_ai.executor import ToolExecutor
    from freecad_ai.llm_client import LLMClient
    from freecad_ai.preferences import AIPreferences
    from freecad_ai.registry import ToolRegistry

try:
    from PySide2.QtCore import QThread, Slot
    from PySide2.QtGui import QTextCursor
    from PySide2.QtWidgets import (
        QDockWidget,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QPushButton,
        QSizePolicy,
        QTextBrowser,
        QVBoxLayout,
        QWidget,
    )

    _QT_OK = True
except ImportError:
    try:
        from PySide6.QtCore import QThread, Slot
        from PySide6.QtGui import QTextCursor
        from PySide6.QtWidgets import (
            QDockWidget,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QPushButton,
            QSizePolicy,
            QTextBrowser,
            QVBoxLayout,
            QWidget,
        )

        _QT_OK = True
    except ImportError:
        _QT_OK = False

_STYLE_USER = "color:#1a73e8;font-weight:bold;"
_STYLE_ASSISTANT = "color:#202124;"
_STYLE_ERROR = "color:#d32f2f;font-style:italic;"
_STYLE_TOOL = "color:#555;font-size:11px;"
_STYLE_THINKING = "color:#999;font-style:italic;"

_TOOL_DETAIL_TMPL = (
    '<details style="{style}">'
    "<summary>{status} tool: {name}</summary>"
    '<pre style="margin:2px 0 0 8px;">args:\n{args}\n\nresult:\n{result}</pre>'
    "</details>"
)


class AIChatPanel(QDockWidget if _QT_OK else object):  # type: ignore[misc]
    """Dockable chat panel. Requires Qt."""

    def __init__(
        self,
        registry: ToolRegistry,
        executor: ToolExecutor,
        history: ConversationHistory,
        make_client: Callable[[], LLMClient],
        prefs: AIPreferences,
        parent=None,
    ) -> None:
        if not _QT_OK:
            raise RuntimeError("Qt not available — cannot create AIChatPanel")
        super().__init__("AI Chat", parent)
        # objectName required for QMainWindow::saveState (Qt warning otherwise)
        self.setObjectName("AIChatPanel")
        self._registry = registry
        self._executor = executor
        self._history = history
        self._make_client = make_client
        self._prefs = prefs
        self._worker: QThread | None = None
        self._pending_tool_results: list[dict] = []
        self._tool_rounds: int = 0

        self._build_ui()
        self._connect_freecad_events()

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self._history_view = QTextBrowser()
        self._history_view.setOpenLinks(False)
        self._history_view.setAcceptRichText(True)
        self._history_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self._history_view)

        self._thinking_label = QLabel("● Thinking…")
        self._thinking_label.setStyleSheet(_STYLE_THINKING)
        self._thinking_label.setVisible(False)
        layout.addWidget(self._thinking_label)

        input_row = QHBoxLayout()
        self._input = QLineEdit()
        self._input.setPlaceholderText("Describe what to design…")
        self._input.returnPressed.connect(self._on_send)
        input_row.addWidget(self._input)

        self._send_btn = QPushButton("Send")
        self._send_btn.clicked.connect(self._on_send)
        input_row.addWidget(self._send_btn)

        layout.addLayout(input_row)
        self.setWidget(container)

    def _connect_freecad_events(self) -> None:
        try:
            import FreeCADGui

            FreeCADGui.getMainWindow().workbenchActivated.connect(
                lambda _: self._executor.set_busy(False)
            )
        except Exception:
            pass

    # ------------------------------------------------------------------ Slots

    @Slot()
    def _on_send(self) -> None:
        text = self._input.text().strip()
        if not text or self._worker is not None:
            return

        if not self._prefs.is_configured:
            self._append_error("API key not set. Open Edit > Preferences > AI Addon.")
            return

        self._input.clear()
        self._append_user(text)
        self._tool_rounds = 0

        from freecad_ai.context import build_context

        ctx = build_context()
        full_text = f"{ctx}\n{text}" if ctx else text
        self._history.add_user(full_text)

        self._set_busy(True)
        self._start_worker()

    def _start_worker(self) -> None:
        from freecad_ai.worker import LLMWorker

        if LLMWorker is None:
            self._append_error("Qt thread support unavailable.")
            self._set_busy(False)
            return

        client = self._make_client()
        messages = self._history.messages()
        tools = self._registry.get_tools_for_llm()

        self._worker = LLMWorker(client=client, messages=messages, tools=tools, parent=self)
        self._worker.token_received.connect(self._on_token)
        self._worker.tool_call_ready.connect(self._on_tool_call_ready)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    @Slot(str)
    def _on_token(self, token: str) -> None:
        self._append_assistant_token(token)

    @Slot(str, str, object)
    def _on_tool_call_ready(self, tc_id: str, name: str, args: dict) -> None:
        # FreeCAD API called here — main thread only (DES-005)
        result = self._executor.dispatch(name, args)
        self._pending_tool_results.append({"tc_id": tc_id, "name": name, "args": args, "result": result})
        self._append_tool_detail(name, args, result)

    @Slot()
    def _on_finished(self) -> None:
        had_tool_calls = bool(self._pending_tool_results)

        if had_tool_calls:
            tool_calls = [
                {
                    "id": entry["tc_id"],
                    "type": "function",
                    "function": {
                        "name": entry["name"],
                        "arguments": json.dumps(entry["args"]),
                    },
                }
                for entry in self._pending_tool_results
            ]
            self._history.add_assistant(content=None, tool_calls=tool_calls)
            for entry in self._pending_tool_results:
                self._history.add_tool_result(
                    tool_call_id=entry["tc_id"],
                    content=json.dumps(entry["result"]),
                )
        else:
            self._history.add_assistant(content=None, tool_calls=None)

        self._pending_tool_results.clear()

        # Clean up the finished worker before potentially starting another
        if self._worker:
            self._worker.quit()
            self._worker.wait(2000)
            self._worker = None

        if had_tool_calls and self._tool_rounds < 5:
            # Re-prompt so the LLM interprets tool results in plain language
            self._tool_rounds += 1
            self._start_worker()
        else:
            self._tool_rounds = 0
            self._set_busy(False)

    @Slot(str)
    def _on_error(self, message: str) -> None:
        self._append_error(message)
        self._cleanup_worker()

    def _cleanup_worker(self) -> None:
        if self._worker:
            self._worker.quit()
            self._worker.wait(2000)
            self._worker = None
        self._set_busy(False)

    # ------------------------------------------------------------------ HTML helpers

    def _append_user(self, text: str) -> None:
        cursor = self._history_view.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertHtml(f'<p style="{_STYLE_USER}">[You] {html.escape(text)}</p>')
        cursor.insertBlock()
        self._history_view.setTextCursor(cursor)
        self._history_view.ensureCursorVisible()

    def _append_assistant_token(self, token: str) -> None:
        cursor = self._history_view.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(token)
        self._history_view.setTextCursor(cursor)
        self._history_view.ensureCursorVisible()

    def _append_tool_detail(self, name: str, args: dict, result: dict) -> None:
        args_str = html.escape(json.dumps(args, indent=2))
        result_str = html.escape(json.dumps(result, indent=2))
        if isinstance(result, dict) and "error" in result:
            status = "✗"
            style = _STYLE_TOOL + _STYLE_ERROR
        else:
            status = "✓"
            style = _STYLE_TOOL
        block = _TOOL_DETAIL_TMPL.format(
            style=style,
            status=status,
            name=html.escape(name),
            args=args_str,
            result=result_str,
        )
        cursor = self._history_view.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertHtml(block)
        cursor.insertBlock()
        self._history_view.setTextCursor(cursor)
        self._history_view.ensureCursorVisible()

    def _append_error(self, message: str) -> None:
        cursor = self._history_view.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertHtml(f'<p style="{_STYLE_ERROR}">⚠ {html.escape(message)}</p>')
        cursor.insertBlock()
        self._history_view.setTextCursor(cursor)

    # ------------------------------------------------------------------ State

    def _set_busy(self, busy: bool) -> None:
        # UI lockout only. The executor.busy flag is for external concurrent-use
        # protection — setting it here would block the worker's own dispatches
        # from inside this same turn (busy=True before LLM call, executor
        # then refuses the tool call the LLM returned).
        self._send_btn.setEnabled(not busy)
        self._input.setEnabled(not busy)
        self._thinking_label.setVisible(busy)
