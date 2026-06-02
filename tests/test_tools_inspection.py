"""
Tests for model inspection tools — REQ-009.
"""

from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.fast


@pytest.fixture()
def inspection_tools(registry):
    from freecad_ai.tools.inspection import register_tools

    register_tools(registry)
    return registry


def test_inspection_tools_registered(inspection_tools):
    names = {t["function"]["name"] for t in inspection_tools.get_tools_for_llm()}
    assert "list_objects" in names
    assert "get_object_properties" in names
    assert "get_selection" in names


def test_list_objects_returns_labels(mock_fc, inspection_tools):
    from freecad_ai.executor import ToolExecutor

    obj = MagicMock()
    obj.Label = "MyBox"
    obj.TypeId = "Part::Box"
    mock_fc.ActiveDocument.Objects = [obj]

    ex = ToolExecutor(inspection_tools)
    result = ex.dispatch("list_objects", {})
    assert "error" not in result
    assert any("MyBox" in str(o) for o in result.get("objects", []))


def test_list_objects_no_document(no_document, inspection_tools):
    from freecad_ai.executor import ToolExecutor

    ex = ToolExecutor(inspection_tools)
    result = ex.dispatch("list_objects", {})
    assert result["error"] == "no_document"


def test_get_selection_empty(mock_fc, inspection_tools):
    import FreeCADGui

    FreeCADGui.Selection.getSelection.return_value = []
    from freecad_ai.executor import ToolExecutor

    ex = ToolExecutor(inspection_tools)
    result = ex.dispatch("get_selection", {})
    assert result.get("selection") == []
