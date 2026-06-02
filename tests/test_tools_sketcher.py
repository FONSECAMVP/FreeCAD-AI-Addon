"""
Tests for Sketcher workbench tools — REQ-008.
"""

from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.fast


@pytest.fixture()
def sk_tools(registry):
    from freecad_ai.tools.sketcher import register_tools

    register_tools(registry)
    return registry


@pytest.fixture()
def doc_with_body_and_sketch(mock_fc):
    sketch = MagicMock()
    sketch.Label = "Sketch"
    sketch.TypeId = "Sketcher::SketchObject"
    sketch.addGeometry = MagicMock(return_value=0)
    sketch.addConstraint = MagicMock(return_value=0)

    body = MagicMock()
    body.Label = "Body"
    body.TypeId = "PartDesign::Body"
    body.newObject = MagicMock(return_value=sketch)

    mock_fc.ActiveDocument.Objects = [body, sketch]

    def get_by_label(lbl):
        return {"Sketch": [sketch], "Body": [body]}.get(lbl, [])

    mock_fc.ActiveDocument.getObjectsByLabel = get_by_label
    return mock_fc, sketch, body


# --- registration ---


def test_sketcher_tools_registered(sk_tools):
    names = {t["function"]["name"] for t in sk_tools.get_tools_for_llm()}
    assert "create_sketch" in names
    assert "sketch_add_line" in names
    assert "sketch_add_circle" in names
    assert "sketch_add_arc" in names
    assert "sketch_add_rectangle" in names
    assert "sketch_constrain_distance" in names
    assert "sketch_constrain_radius" in names
    assert "sketch_constrain_coincident" in names


# --- create_sketch ---


def test_create_sketch_on_xy_plane(mock_fc, sk_tools):
    from freecad_ai.executor import ToolExecutor

    body = MagicMock()
    body.Label = "Body"
    sketch = MagicMock()
    sketch.Label = "Sketch"
    body.newObject = MagicMock(return_value=sketch)
    mock_fc.ActiveDocument.getObjectsByLabel = lambda lbl: [body] if lbl == "Body" else []
    mock_fc.ActiveDocument.addObject = MagicMock(return_value=sketch)

    ex = ToolExecutor(sk_tools)
    result = ex.dispatch("create_sketch", {"body_label": "Body", "plane": "XY"})
    assert "error" not in result


def test_create_sketch_invalid_plane(mock_fc, sk_tools):
    from freecad_ai.executor import ToolExecutor

    ex = ToolExecutor(sk_tools)
    result = ex.dispatch("create_sketch", {"body_label": "Body", "plane": "DIAGONAL"})
    assert result["error"] == "validation"


# --- sketch_add_line ---


def test_sketch_add_line(doc_with_body_and_sketch, sk_tools):
    from freecad_ai.executor import ToolExecutor

    mock_fc, sketch, body = doc_with_body_and_sketch

    ex = ToolExecutor(sk_tools)
    result = ex.dispatch(
        "sketch_add_line",
        {
            "sketch_label": "Sketch",
            "x1": 0.0,
            "y1": 0.0,
            "x2": 10.0,
            "y2": 0.0,
        },
    )
    assert "error" not in result
    sketch.addGeometry.assert_called_once()


# --- sketch_add_circle ---


def test_sketch_add_circle(doc_with_body_and_sketch, sk_tools):
    from freecad_ai.executor import ToolExecutor

    mock_fc, sketch, body = doc_with_body_and_sketch

    ex = ToolExecutor(sk_tools)
    result = ex.dispatch(
        "sketch_add_circle",
        {
            "sketch_label": "Sketch",
            "cx": 0.0,
            "cy": 0.0,
            "radius": 10.0,
        },
    )
    assert "error" not in result
    sketch.addGeometry.assert_called_once()


def test_sketch_add_circle_requires_positive_radius(doc_with_body_and_sketch, sk_tools):
    from freecad_ai.executor import ToolExecutor

    mock_fc, sketch, body = doc_with_body_and_sketch

    ex = ToolExecutor(sk_tools)
    result = ex.dispatch(
        "sketch_add_circle",
        {
            "sketch_label": "Sketch",
            "cx": 0.0,
            "cy": 0.0,
            "radius": 0.0,
        },
    )
    assert result["error"] == "validation"


# --- sketch_add_rectangle ---


def test_sketch_add_rectangle(doc_with_body_and_sketch, sk_tools):
    from freecad_ai.executor import ToolExecutor

    mock_fc, sketch, body = doc_with_body_and_sketch

    ex = ToolExecutor(sk_tools)
    result = ex.dispatch(
        "sketch_add_rectangle",
        {
            "sketch_label": "Sketch",
            "x": 0.0,
            "y": 0.0,
            "width": 20.0,
            "height": 10.0,
        },
    )
    assert "error" not in result
    # Rectangle = 4 lines
    assert sketch.addGeometry.call_count == 4


# --- constraints ---


def test_sketch_constrain_distance(doc_with_body_and_sketch, sk_tools):
    from freecad_ai.executor import ToolExecutor

    mock_fc, sketch, body = doc_with_body_and_sketch

    ex = ToolExecutor(sk_tools)
    result = ex.dispatch(
        "sketch_constrain_distance",
        {
            "sketch_label": "Sketch",
            "geometry_index": 0,
            "distance": 50.0,
        },
    )
    assert "error" not in result
    sketch.addConstraint.assert_called_once()


def test_sketch_constrain_radius(doc_with_body_and_sketch, sk_tools):
    from freecad_ai.executor import ToolExecutor

    mock_fc, sketch, body = doc_with_body_and_sketch

    ex = ToolExecutor(sk_tools)
    result = ex.dispatch(
        "sketch_constrain_radius",
        {
            "sketch_label": "Sketch",
            "geometry_index": 0,
            "radius": 20.0,
        },
    )
    assert "error" not in result
    sketch.addConstraint.assert_called_once()


def test_sketch_constrain_coincident(doc_with_body_and_sketch, sk_tools):
    from freecad_ai.executor import ToolExecutor

    mock_fc, sketch, body = doc_with_body_and_sketch

    ex = ToolExecutor(sk_tools)
    result = ex.dispatch(
        "sketch_constrain_coincident",
        {
            "sketch_label": "Sketch",
            "geo_index1": 0,
            "point_index1": 1,
            "geo_index2": 1,
            "point_index2": 2,
        },
    )
    assert "error" not in result
    sketch.addConstraint.assert_called_once()


def test_sketch_tool_missing_sketch_returns_error(mock_fc, sk_tools):
    from freecad_ai.executor import ToolExecutor

    mock_fc.ActiveDocument.getObjectsByLabel = lambda lbl: []

    ex = ToolExecutor(sk_tools)
    result = ex.dispatch(
        "sketch_add_line",
        {
            "sketch_label": "NoSuch",
            "x1": 0.0,
            "y1": 0.0,
            "x2": 10.0,
            "y2": 0.0,
        },
    )
    assert result["error"] == "execution"
