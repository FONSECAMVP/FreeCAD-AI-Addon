"""
Tests for PartDesign workbench tools — REQ-007.
"""

from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.fast


@pytest.fixture()
def pd_tools(registry):
    from freecad_ai.tools.partdesign import register_tools

    register_tools(registry)
    return registry


@pytest.fixture()
def doc_with_body(mock_fc):
    body = MagicMock()
    body.Label = "Body"
    body.TypeId = "PartDesign::Body"
    body.Tip = None
    mock_fc.ActiveDocument.Objects = [body]
    mock_fc.ActiveDocument.getObjectsByLabel = lambda lbl: ([body] if lbl == "Body" else [])

    feature = MagicMock()
    feature.Label = "Pad"
    feature.TypeId = "PartDesign::Pad"
    body.newObject = MagicMock(return_value=feature)
    return mock_fc, body, feature


@pytest.fixture()
def doc_with_sketch(mock_fc):
    sketch = MagicMock()
    sketch.Label = "Sketch"
    sketch.TypeId = "Sketcher::SketchObject"

    body = MagicMock()
    body.Label = "Body"
    body.TypeId = "PartDesign::Body"
    body.Tip = None

    feature = MagicMock()
    feature.Label = "Pad"
    feature.TypeId = "PartDesign::Pad"
    body.newObject = MagicMock(return_value=feature)

    mock_fc.ActiveDocument.Objects = [sketch, body]

    def get_by_label(lbl):
        return {"Sketch": [sketch], "Body": [body]}.get(lbl, [])

    mock_fc.ActiveDocument.getObjectsByLabel = get_by_label
    return mock_fc, sketch, body, feature


# --- tool registration ---


def test_partdesign_tools_registered(pd_tools):
    names = {t["function"]["name"] for t in pd_tools.get_tools_for_llm()}
    assert "create_body" in names
    assert "pad_sketch" in names
    assert "pocket_sketch" in names
    assert "add_fillet" in names
    assert "add_chamfer" in names


# --- create_body ---


def test_create_body_adds_object(mock_fc, pd_tools):
    from freecad_ai.executor import ToolExecutor

    body = MagicMock()
    body.Label = "Body"
    mock_fc.ActiveDocument.addObject = MagicMock(return_value=body)

    ex = ToolExecutor(pd_tools)
    result = ex.dispatch("create_body", {})
    assert "error" not in result
    mock_fc.ActiveDocument.addObject.assert_called_with("PartDesign::Body", "Body")


def test_create_body_custom_label(mock_fc, pd_tools):
    from freecad_ai.executor import ToolExecutor

    body = MagicMock()
    body.Label = "MyPart"
    mock_fc.ActiveDocument.addObject = MagicMock(return_value=body)

    ex = ToolExecutor(pd_tools)
    result = ex.dispatch("create_body", {"label": "MyPart"})
    assert "error" not in result
    mock_fc.ActiveDocument.addObject.assert_called_with("PartDesign::Body", "MyPart")


# --- pad_sketch ---


def test_pad_sketch_creates_pad(doc_with_sketch, pd_tools):
    from freecad_ai.executor import ToolExecutor

    mock_fc, sketch, body, feature = doc_with_sketch

    ex = ToolExecutor(pd_tools)
    result = ex.dispatch(
        "pad_sketch",
        {
            "sketch_label": "Sketch",
            "body_label": "Body",
            "length": 15.0,
        },
    )
    assert "error" not in result
    body.newObject.assert_called_with("PartDesign::Pad", "Pad")
    assert feature.Profile == sketch
    assert feature.Length == 15.0


def test_pad_sketch_missing_sketch_returns_error(mock_fc, pd_tools):
    from freecad_ai.executor import ToolExecutor

    mock_fc.ActiveDocument.getObjectsByLabel = lambda lbl: []

    ex = ToolExecutor(pd_tools)
    result = ex.dispatch(
        "pad_sketch",
        {
            "sketch_label": "NoSuch",
            "body_label": "Body",
            "length": 10.0,
        },
    )
    assert result["error"] == "execution"


def test_pad_sketch_requires_positive_length(mock_fc, pd_tools):
    from freecad_ai.executor import ToolExecutor

    ex = ToolExecutor(pd_tools)
    result = ex.dispatch(
        "pad_sketch",
        {
            "sketch_label": "Sketch",
            "body_label": "Body",
            "length": 0.0,
        },
    )
    assert result["error"] == "validation"


# --- pocket_sketch ---


def test_pocket_sketch_creates_pocket(doc_with_sketch, pd_tools):
    from freecad_ai.executor import ToolExecutor

    mock_fc, sketch, body, feature = doc_with_sketch
    feature.TypeId = "PartDesign::Pocket"

    ex = ToolExecutor(pd_tools)
    result = ex.dispatch(
        "pocket_sketch",
        {
            "sketch_label": "Sketch",
            "body_label": "Body",
            "depth": 8.0,
        },
    )
    assert "error" not in result
    body.newObject.assert_called_with("PartDesign::Pocket", "Pocket")
    assert feature.Length == 8.0


def test_pocket_sketch_requires_positive_depth(mock_fc, pd_tools):
    from freecad_ai.executor import ToolExecutor

    ex = ToolExecutor(pd_tools)
    result = ex.dispatch(
        "pocket_sketch",
        {
            "sketch_label": "Sketch",
            "body_label": "Body",
            "depth": -1.0,
        },
    )
    assert result["error"] == "validation"


# --- add_fillet ---


def test_add_fillet_creates_fillet(doc_with_body, pd_tools):
    from freecad_ai.executor import ToolExecutor

    mock_fc, body, feature = doc_with_body
    fillet = MagicMock()
    fillet.Label = "Fillet"
    body.newObject = MagicMock(return_value=fillet)

    mock_fc.ActiveDocument.getObjectsByLabel = lambda lbl: (
        [body] if lbl in ("Body", "Pad") else []
    )

    ex = ToolExecutor(pd_tools)
    result = ex.dispatch(
        "add_fillet",
        {
            "feature_label": "Pad",
            "body_label": "Body",
            "radius": 2.0,
            "edges": ["Edge1", "Edge2"],
        },
    )
    assert "error" not in result
    body.newObject.assert_called_with("PartDesign::Fillet", "Fillet")
    assert fillet.Radius == 2.0


def test_add_fillet_requires_positive_radius(mock_fc, pd_tools):
    from freecad_ai.executor import ToolExecutor

    ex = ToolExecutor(pd_tools)
    result = ex.dispatch(
        "add_fillet",
        {
            "feature_label": "Pad",
            "body_label": "Body",
            "radius": 0.0,
            "edges": ["Edge1"],
        },
    )
    assert result["error"] == "validation"


# --- add_chamfer ---


def test_add_chamfer_creates_chamfer(doc_with_body, pd_tools):
    from freecad_ai.executor import ToolExecutor

    mock_fc, body, feature = doc_with_body
    chamfer = MagicMock()
    chamfer.Label = "Chamfer"
    body.newObject = MagicMock(return_value=chamfer)

    mock_fc.ActiveDocument.getObjectsByLabel = lambda lbl: (
        [body] if lbl in ("Body", "Pad") else []
    )

    ex = ToolExecutor(pd_tools)
    result = ex.dispatch(
        "add_chamfer",
        {
            "feature_label": "Pad",
            "body_label": "Body",
            "size": 1.5,
            "edges": ["Edge1"],
        },
    )
    assert "error" not in result
    body.newObject.assert_called_with("PartDesign::Chamfer", "Chamfer")
    assert chamfer.Size == 1.5
