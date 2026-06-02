"""
Tests for Draft workbench tools — REQ-013.
"""

import sys
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.fast


@pytest.fixture(autouse=True)
def draft_mock():
    import types

    draft = types.ModuleType("Draft")
    result_obj = MagicMock()
    result_obj.Label = "DraftObj"
    draft.makeLine = MagicMock(return_value=result_obj)
    draft.makeRectangle = MagicMock(return_value=result_obj)
    draft.makeCircle = MagicMock(return_value=result_obj)
    draft.makeBSpline = MagicMock(return_value=result_obj)
    draft.makeArray = MagicMock(return_value=result_obj)
    draft.move = MagicMock(return_value=None)
    draft.rotate = MagicMock(return_value=None)
    sys.modules["Draft"] = draft
    yield draft


@pytest.fixture()
def dr_tools(registry):
    from freecad_ai.tools.draft import register_tools

    register_tools(registry)
    return registry


@pytest.fixture()
def doc_with_obj(mock_fc):
    obj = MagicMock()
    obj.Label = "MyLine"
    obj.TypeId = "Draft::Wire"
    mock_fc.ActiveDocument.Objects = [obj]
    mock_fc.ActiveDocument.getObjectsByLabel = lambda lbl: [obj] if lbl == "MyLine" else []
    return mock_fc, obj


# --- registration ---


def test_draft_tools_registered(dr_tools):
    names = {t["function"]["name"] for t in dr_tools.get_tools_for_llm()}
    assert "draft_line" in names
    assert "draft_rectangle" in names
    assert "draft_circle" in names
    assert "draft_bspline" in names
    assert "draft_array" in names
    assert "draft_move" in names
    assert "draft_rotate" in names


# --- draft_line ---


def test_draft_line_calls_makeline(mock_fc, dr_tools, draft_mock):
    from freecad_ai.executor import ToolExecutor

    ex = ToolExecutor(dr_tools)
    result = ex.dispatch(
        "draft_line",
        {
            "x1": 0.0,
            "y1": 0.0,
            "z1": 0.0,
            "x2": 50.0,
            "y2": 0.0,
            "z2": 0.0,
        },
    )
    assert "error" not in result
    draft_mock.makeLine.assert_called_once()


# --- draft_rectangle ---


def test_draft_rectangle_calls_makerectangle(mock_fc, dr_tools, draft_mock):
    from freecad_ai.executor import ToolExecutor

    ex = ToolExecutor(dr_tools)
    result = ex.dispatch("draft_rectangle", {"length": 100.0, "height": 50.0})
    assert "error" not in result
    draft_mock.makeRectangle.assert_called_once()


def test_draft_rectangle_requires_positive_dims(mock_fc, dr_tools):
    from freecad_ai.executor import ToolExecutor

    ex = ToolExecutor(dr_tools)
    result = ex.dispatch("draft_rectangle", {"length": 0.0, "height": 50.0})
    assert result["error"] == "validation"


# --- draft_circle ---


def test_draft_circle_calls_makecircle(mock_fc, dr_tools, draft_mock):
    from freecad_ai.executor import ToolExecutor

    ex = ToolExecutor(dr_tools)
    result = ex.dispatch("draft_circle", {"radius": 25.0})
    assert "error" not in result
    draft_mock.makeCircle.assert_called_once()


def test_draft_circle_requires_positive_radius(mock_fc, dr_tools):
    from freecad_ai.executor import ToolExecutor

    ex = ToolExecutor(dr_tools)
    result = ex.dispatch("draft_circle", {"radius": -5.0})
    assert result["error"] == "validation"


# --- draft_bspline ---


def test_draft_bspline_calls_makebspline(mock_fc, dr_tools, draft_mock):
    from freecad_ai.executor import ToolExecutor

    ex = ToolExecutor(dr_tools)
    result = ex.dispatch(
        "draft_bspline",
        {
            "points": [
                {"x": 0.0, "y": 0.0, "z": 0.0},
                {"x": 10.0, "y": 5.0, "z": 0.0},
                {"x": 20.0, "y": 0.0, "z": 0.0},
            ]
        },
    )
    assert "error" not in result
    draft_mock.makeBSpline.assert_called_once()


def test_draft_bspline_requires_at_least_two_points(mock_fc, dr_tools):
    from freecad_ai.executor import ToolExecutor

    ex = ToolExecutor(dr_tools)
    result = ex.dispatch("draft_bspline", {"points": [{"x": 0.0, "y": 0.0, "z": 0.0}]})
    assert result["error"] == "validation"


# --- draft_array ---


def test_draft_array_calls_makearray(mock_fc, doc_with_obj, dr_tools, draft_mock):
    from freecad_ai.executor import ToolExecutor

    mock_fc, obj = doc_with_obj
    ex = ToolExecutor(dr_tools)
    result = ex.dispatch(
        "draft_array",
        {
            "object_label": "MyLine",
            "interval_x": 20.0,
            "interval_y": 0.0,
            "count_x": 3,
            "count_y": 1,
        },
    )
    assert "error" not in result
    draft_mock.makeArray.assert_called_once()


def test_draft_array_missing_object_returns_error(mock_fc, dr_tools):
    from freecad_ai.executor import ToolExecutor

    mock_fc.ActiveDocument.getObjectsByLabel = lambda lbl: []
    ex = ToolExecutor(dr_tools)
    result = ex.dispatch(
        "draft_array",
        {
            "object_label": "NoSuch",
            "interval_x": 10.0,
            "interval_y": 0.0,
            "count_x": 2,
            "count_y": 1,
        },
    )
    assert result["error"] == "execution"


def test_draft_array_requires_positive_counts(mock_fc, doc_with_obj, dr_tools):
    from freecad_ai.executor import ToolExecutor

    mock_fc, obj = doc_with_obj
    ex = ToolExecutor(dr_tools)
    result = ex.dispatch(
        "draft_array",
        {
            "object_label": "MyLine",
            "interval_x": 10.0,
            "interval_y": 0.0,
            "count_x": 0,
            "count_y": 1,
        },
    )
    assert result["error"] == "validation"


# --- draft_move ---


def test_draft_move_calls_move(mock_fc, doc_with_obj, dr_tools, draft_mock):
    from freecad_ai.executor import ToolExecutor

    mock_fc, obj = doc_with_obj
    ex = ToolExecutor(dr_tools)
    result = ex.dispatch(
        "draft_move",
        {
            "object_label": "MyLine",
            "dx": 10.0,
            "dy": 0.0,
            "dz": 0.0,
        },
    )
    assert "error" not in result
    draft_mock.move.assert_called_once()


def test_draft_move_missing_object_returns_error(mock_fc, dr_tools):
    from freecad_ai.executor import ToolExecutor

    mock_fc.ActiveDocument.getObjectsByLabel = lambda lbl: []
    ex = ToolExecutor(dr_tools)
    result = ex.dispatch(
        "draft_move",
        {
            "object_label": "Ghost",
            "dx": 5.0,
            "dy": 0.0,
            "dz": 0.0,
        },
    )
    assert result["error"] == "execution"


# --- draft_rotate ---


def test_draft_rotate_calls_rotate(mock_fc, doc_with_obj, dr_tools, draft_mock):
    from freecad_ai.executor import ToolExecutor

    mock_fc, obj = doc_with_obj
    ex = ToolExecutor(dr_tools)
    result = ex.dispatch(
        "draft_rotate",
        {
            "object_label": "MyLine",
            "angle": 90.0,
            "cx": 0.0,
            "cy": 0.0,
            "cz": 0.0,
        },
    )
    assert "error" not in result
    draft_mock.rotate.assert_called_once()
