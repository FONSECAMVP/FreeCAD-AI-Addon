"""
LLM worker — DES-005, REQ-011.

Architecture (resolves A1-C1):
  run_chat()     — pure async function, fully testable without Qt
  LLMWorker      — QThread wrapper; calls run_chat via asyncio.run();
                   delivers results to main thread via pyqtSignal
                   FreeCAD API only called from main thread slots.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from freecad_ai.llm_client import LLMClient, LLMError, ToolCall


async def run_chat(
    client: LLMClient,
    messages: list[dict],
    tools: list[dict],
    on_token: Callable[[str], Awaitable[None]],
    on_tool_call: Callable[[str, str, dict], Awaitable[dict]],
    on_error: Callable[[str], Awaitable[None]],
) -> None:
    """
    Core async chat loop. Provider-agnostic; Qt-free; fully unit-testable.

    Calls on_token for each text chunk, on_tool_call for each tool request
    (returns the tool result dict), on_error on LLMError. Never raises.
    """
    try:
        async for item in client.chat(messages=messages, tools=tools):
            if isinstance(item, str):
                await on_token(item)
            elif isinstance(item, ToolCall):
                await on_tool_call(item.id, item.name, item.args)
    except LLMError as exc:
        await on_error(str(exc))
    except Exception as exc:
        # Catch anything the provider client didn't wrap as LLMError
        # (httpx internals, import failures, unexpected response shapes, etc.)
        await on_error(f"Unexpected error: {type(exc).__name__}: {exc}")


# --- Qt wrapper (not imported in headless/test mode) ---


def _make_llm_worker_class():
    """Deferred import so QThread is not required at module load time (REQ-026)."""
    try:
        from PySide2.QtCore import QThread, Signal
    except ImportError:
        try:
            from PySide6.QtCore import QThread, Signal
        except ImportError:
            return None

    class LLMWorker(QThread):
        """
        Runs run_chat() on a background thread.
        Emits signals consumed by AIChatPanel on the main thread.
        FreeCAD API is NEVER called from this thread.
        """

        token_received = Signal(str)
        tool_call_ready = Signal(str, str, object)  # (tc_id, tool_name, args_dict)
        finished = Signal()
        error = Signal(str)

        def __init__(
            self,
            client: LLMClient,
            messages: list[dict],
            tools: list[dict],
            parent=None,
        ) -> None:
            super().__init__(parent)
            self._client = client
            self._messages = messages
            self._tools = tools
            self._tool_results: dict[str, dict] = {}

        def set_tool_result(self, tool_name: str, result: dict) -> None:
            """Called from main thread slot after tool dispatch completes."""
            self._tool_results[tool_name] = result

        def run(self) -> None:
            # Bypass any global asyncio event loop policy FreeCAD may have
            # installed (e.g. qasync). We need a plain SelectorEventLoop that
            # works correctly in a background QThread with no Qt event loop.
            loop = asyncio.SelectorEventLoop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._async_run())
            except Exception as exc:
                # Last-resort catch: _async_run should never raise because
                # run_chat swallows all exceptions via on_error, but guard
                # against unexpected failures so finished always fires.
                self.error.emit(f"Worker crashed: {type(exc).__name__}: {exc}")
            finally:
                try:
                    loop.close()
                except Exception:
                    pass
                # Always emit finished so the panel unblocks regardless of
                # how the async run ended.
                self.finished.emit()

        async def _async_run(self) -> None:
            async def on_token(text: str) -> None:
                self.token_received.emit(text)

            async def on_tool_call(tc_id: str, name: str, args: dict) -> dict:
                # Emit to main thread; main thread calls executor.dispatch()
                # and calls set_tool_result() before we continue.
                self.tool_call_ready.emit(tc_id, name, args)
                return {}

            async def on_error(msg: str) -> None:
                self.error.emit(msg)

            await run_chat(
                client=self._client,
                messages=self._messages,
                tools=self._tools,
                on_token=on_token,
                on_tool_call=on_tool_call,
                on_error=on_error,
            )

    return LLMWorker


LLMWorker = _make_llm_worker_class()
