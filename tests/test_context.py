"""
Tests for document context injector — REQ-005, REQ-009 (inspection).
"""

from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.fast


@pytest.fixture()
def doc_with_objects(mock_fc):
    obj1 = MagicMock()
    obj1.Label = "Box"
    obj1.TypeId = "Part::Box"
    obj2 = MagicMock()
    obj2.Label = "Sketch"
    obj2.TypeId = "Sketcher::SketchObject"
    mock_fc.ActiveDocument.Objects = [obj1, obj2]
    mock_fc.ActiveDocument.Name = "MyPart"
    return mock_fc


def test_build_context_includes_doc_name(doc_with_objects):
    from freecad_ai.context import build_context

    ctx = build_context()
    assert "MyPart" in ctx


def test_build_context_includes_object_labels(doc_with_objects):
    from freecad_ai.context import build_context

    ctx = build_context()
    assert "Box" in ctx
    assert "Sketch" in ctx


def test_build_context_no_document(no_document):
    from freecad_ai.context import build_context

    ctx = build_context()
    assert "no active document" in ctx.lower()


def test_build_context_caps_at_20_objects(mock_fc):
    from freecad_ai.context import build_context

    objs = []
    for i in range(25):
        o = MagicMock()
        o.Label = f"Obj{i:02d}"
        o.TypeId = "Part::Box"
        objs.append(o)
    mock_fc.ActiveDocument.Objects = objs
    mock_fc.ActiveDocument.Name = "BigDoc"
    ctx = build_context()
    # Only first 20 should appear; Obj20..24 should not
    assert "Obj19" in ctx
    assert "Obj20" not in ctx


def test_build_context_total_length_bounded(doc_with_objects):
    from freecad_ai.context import build_context

    ctx = build_context()
    assert len(ctx) <= 500
