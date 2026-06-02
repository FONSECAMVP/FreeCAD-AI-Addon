"""
Tests for tool executor — REQ-004, REQ-020, REQ-023, REQ-024, REQ-025, REQ-027.
A4-BLOCK-1: document closed during handler must not crash (abortTransaction guard).
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
                "label": {"type": "string"},
            },
            "required": ["length", "width", "height"],
        },
    },
}


@pytest.fixture()
def executor(registry):
    from freecad_ai.executor import ToolExecutor

    return ToolExecutor(registry)


@pytest.fixture()
def registered_registry(registry):
    def handler(args):
        return {"ok": True}

    registry.register("create_box", BOX_SCHEMA, handler, workbench="Part")
    return registry


# REQ-004: successful dispatch returns handler result
def test_dispatch_success(mock_fc, registered_registry):
    from freecad_ai.executor import ToolExecutor

    ex = ToolExecutor(registered_registry)
    result = ex.dispatch("create_box", {"length": 10, "width": 10, "height": 5})
    assert result == {"ok": True}


# REQ-020: openTransaction called before handler, commitTransaction after
def test_dispatch_wraps_in_transaction(mock_fc, registered_registry):
    from freecad_ai.executor import ToolExecutor

    ex = ToolExecutor(registered_registry)
    ex.dispatch("create_box", {"length": 10, "width": 10, "height": 5})
    mock_fc.ActiveDocument.openTransaction.assert_called_once()
    mock_fc.ActiveDocument.commitTransaction.assert_called_once()


# REQ-020: abortTransaction called on handler exception, not commitTransaction
def test_dispatch_aborts_transaction_on_exception(mock_fc, registry):
    from freecad_ai.executor import ToolExecutor

    def bad_handler(args):
        raise RuntimeError("FreeCAD API failure")

    registry.register("bad_tool", BOX_SCHEMA, bad_handler, workbench="Part")
    ex = ToolExecutor(registry)
    result = ex.dispatch("bad_tool", {"length": 10, "width": 10, "height": 5})
    assert result["error"] == "execution"
    mock_fc.ActiveDocument.abortTransaction.assert_called_once()
    mock_fc.ActiveDocument.commitTransaction.assert_not_called()


# REQ-025: no active document returns error
def test_dispatch_no_active_document(no_document, registered_registry):
    from freecad_ai.executor import ToolExecutor

    ex = ToolExecutor(registered_registry)
    result = ex.dispatch("create_box", {"length": 10, "width": 10, "height": 5})
    assert result["error"] == "no_document"


# REQ-024: string arg with path traversal rejected
def test_dispatch_rejects_invalid_string_arg(mock_fc, registry):
    from freecad_ai.executor import ToolExecutor

    schema = {
        "type": "function",
        "function": {
            "name": "labeled_box",
            "description": "Box with label.",
            "parameters": {
                "type": "object",
                "properties": {"label": {"type": "string"}},
                "required": ["label"],
            },
        },
    }
    registry.register("labeled_box", schema, lambda a: {"ok": True}, workbench="Part")
    ex = ToolExecutor(registry)
    result = ex.dispatch("labeled_box", {"label": "../../etc/passwd"})
    assert result["error"] == "validation"
    assert result["field"] == "label"


# REQ-024: valid string arg passes
def test_dispatch_accepts_valid_string_arg(mock_fc, registry):
    from freecad_ai.executor import ToolExecutor

    schema = {
        "type": "function",
        "function": {
            "name": "labeled_box",
            "description": "Box with label.",
            "parameters": {
                "type": "object",
                "properties": {"label": {"type": "string"}},
                "required": ["label"],
            },
        },
    }
    registry.register("labeled_box", schema, lambda a: {"ok": True}, workbench="Part")
    ex = ToolExecutor(registry)
    result = ex.dispatch("labeled_box", {"label": "My Box_01"})
    assert "error" not in result


# REQ-024: string arg over 128 chars rejected
def test_dispatch_rejects_too_long_string_arg(mock_fc, registry):
    from freecad_ai.executor import ToolExecutor

    schema = {
        "type": "function",
        "function": {
            "name": "labeled_box",
            "description": "",
            "parameters": {
                "type": "object",
                "properties": {"label": {"type": "string"}},
                "required": ["label"],
            },
        },
    }
    registry.register("labeled_box", schema, lambda a: {"ok": True}, workbench="Part")
    ex = ToolExecutor(registry)
    result = ex.dispatch("labeled_box", {"label": "x" * 129})
    assert result["error"] == "validation"


# REQ-027: executor activates workbench before handler call
def test_dispatch_activates_workbench(mock_fc, registry):
    import FreeCADGui

    from freecad_ai.executor import ToolExecutor

    registry.register("create_box", BOX_SCHEMA, lambda a: {"ok": True}, workbench="Part")
    ex = ToolExecutor(registry)
    ex.dispatch("create_box", {"length": 10, "width": 10, "height": 5})
    FreeCADGui.activateWorkbench.assert_called_with("PartWorkbench")


# A4-BLOCK-1: document closed mid-handler — abortTransaction must not raise
def test_dispatch_document_closed_during_handler(mock_fc, registry):
    """A4-BLOCK-1: if ActiveDocument becomes None during handler execution,
    abortTransaction guard must prevent AttributeError (no crash in Qt slot)."""
    import FreeCAD

    from freecad_ai.executor import ToolExecutor

    def handler_that_closes_doc(args):
        FreeCAD.ActiveDocument = None  # simulate doc closed mid-handler
        raise RuntimeError("doc closed")

    registry.register("doc_close_tool", BOX_SCHEMA, handler_that_closes_doc, workbench="Part")
    ex = ToolExecutor(registry)
    result = ex.dispatch("doc_close_tool", {"length": 10, "width": 10, "height": 5})
    assert result["error"] == "execution"
    assert "doc closed" in result["message"]
