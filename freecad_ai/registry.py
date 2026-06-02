"""Tool registry — DES-001, REQ-003, REQ-019."""

from __future__ import annotations

from collections.abc import Callable


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, dict] = {}  # name -> {schema, handler, workbench}

    def register(
        self,
        name: str,
        schema: dict,
        handler: Callable[[dict], dict],
        workbench: str,
    ) -> None:
        if name in self._tools:
            raise ValueError(f"Tool '{name}' already registered")
        self._tools[name] = {"schema": schema, "handler": handler, "workbench": workbench}

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def get_tools_for_llm(self) -> list[dict]:
        return [entry["schema"] for entry in self._tools.values()]

    def get_entry(self, name: str) -> dict | None:
        return self._tools.get(name)

    def dispatch(self, name: str, args: dict) -> dict:
        """Thin delegation — real validation/transaction in ToolExecutor.
        Direct dispatch from registry returns unknown_tool if name missing."""
        if name not in self._tools:
            return {"error": "unknown_tool", "name": name}
        return self._tools[name]["handler"](args)
