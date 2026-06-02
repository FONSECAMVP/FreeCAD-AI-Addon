"""Tool executor — DES-001, REQ-004, REQ-020, REQ-023, REQ-024, REQ-025, REQ-027."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from freecad_ai.registry import ToolRegistry

_WORKBENCH_MAP = {
    "Part": "PartWorkbench",
    "PartDesign": "PartDesignWorkbench",
    "Sketcher": "SketcherWorkbench",
    "Draft": "DraftWorkbench",
    "BIM": "BIMWorkbench",
    "Arch": "BIMWorkbench",
}

_STRING_ARG_RE = re.compile(r"^[\w\s\-]{1,128}$")  # alphanumeric+space+underscore+hyphen


def _validate_string_arg(field: str, value: str) -> dict | None:
    """Returns error dict if invalid, else None."""
    if not isinstance(value, str):
        return None  # type mismatch caught by schema validation
    if not value.strip():
        return {"error": "validation", "field": field, "reason": "must not be empty or whitespace"}
    if len(value) > 128:
        return {"error": "validation", "field": field, "reason": "max 128 characters"}
    if not _STRING_ARG_RE.match(value):
        return {
            "error": "validation",
            "field": field,
            "reason": "only alphanumeric, space, underscore, hyphen allowed",
        }
    return None


def _validate_args(schema: dict, args: dict) -> dict | None:
    """Basic schema validation. Returns error dict or None."""
    func_schema = schema.get("function", schema)
    params = func_schema.get("parameters", {})
    properties = params.get("properties", {})
    required = params.get("required", [])

    for field in required:
        if field not in args:
            return {"error": "validation", "field": field, "reason": "required field missing"}

    for field, value in args.items():
        prop = properties.get(field, {})
        expected_type = prop.get("type")

        if expected_type == "number" and not isinstance(value, int | float):
            return {"error": "validation", "field": field, "reason": "must be a number"}

        if expected_type == "string":
            err = _validate_string_arg(field, value)
            if err:
                return err

    return None


class ToolExecutor:
    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry
        self._busy = False

    def set_busy(self, busy: bool) -> None:
        self._busy = busy

    def dispatch(self, name: str, args: dict) -> dict:
        import FreeCAD
        import FreeCADGui

        if self._busy:
            return {"error": "busy", "message": "FreeCAD is busy — try again shortly"}

        entry = self._registry.get_entry(name)
        if entry is None:
            return {"error": "unknown_tool", "name": name}

        if FreeCAD.ActiveDocument is None:
            return {
                "error": "no_document",
                "message": "No active document. Create or open a document first.",
            }

        err = _validate_args(entry["schema"], args)
        if err:
            return err

        workbench = entry["workbench"]
        wb_name = _WORKBENCH_MAP.get(workbench, f"{workbench}Workbench")
        FreeCADGui.activateWorkbench(wb_name)

        FreeCAD.ActiveDocument.openTransaction(f"AI: {name}")
        try:
            result = entry["handler"](args)
            FreeCAD.ActiveDocument.commitTransaction()
            return result
        except Exception as exc:
            try:
                if FreeCAD.ActiveDocument:
                    FreeCAD.ActiveDocument.abortTransaction()
            except Exception:
                pass  # document was closed during handler — transaction already gone
            return {"error": "execution", "message": str(exc)}
