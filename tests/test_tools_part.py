"""
Tests for Part workbench tools — REQ-006.
"""

import pytest

pytestmark = pytest.mark.fast


@pytest.fixture()
def part_tools(registry):
    from freecad_ai.tools.part import register_tools

    register_tools(registry)
    return registry


def test_part_tools_registered(part_tools):
    tools = part_tools.get_tools_for_llm()
    names = {t["function"]["name"] for t in tools}
    assert "create_box" in names
    assert "create_cylinder" in names
    assert "create_sphere" in names
    assert "boolean_union" in names
    assert "boolean_cut" in names
    assert "boolean_common" in names


def test_create_box_calls_freecad(mock_fc, part_tools):
    from freecad_ai.executor import ToolExecutor

    ex = ToolExecutor(part_tools)
    result = ex.dispatch("create_box", {"length": 50.0, "width": 30.0, "height": 10.0})
    assert "error" not in result
    mock_fc.ActiveDocument.addObject.assert_called()


def test_create_box_requires_positive_dimensions(mock_fc, part_tools):
    from freecad_ai.executor import ToolExecutor

    ex = ToolExecutor(part_tools)
    result = ex.dispatch("create_box", {"length": -1.0, "width": 30.0, "height": 10.0})
    assert result["error"] == "validation"


def test_create_cylinder_handler(mock_fc, part_tools):
    from freecad_ai.executor import ToolExecutor

    ex = ToolExecutor(part_tools)
    result = ex.dispatch("create_cylinder", {"radius": 10.0, "height": 20.0})
    assert "error" not in result


def test_create_sphere_handler(mock_fc, part_tools):
    from freecad_ai.executor import ToolExecutor

    ex = ToolExecutor(part_tools)
    result = ex.dispatch("create_sphere", {"radius": 15.0})
    assert "error" not in result
