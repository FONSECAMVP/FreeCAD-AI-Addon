"""
Mocks for FreeCAD modules so tests run without FreeCAD installed.
All FreeCAD API mocks live here — tests import from conftest via fixtures.
"""

import sys
import types
from unittest.mock import MagicMock

import pytest


def _make_freecad_mock() -> types.ModuleType:
    fc = types.ModuleType("FreeCAD")
    fc.Console = MagicMock()
    fc.Console.PrintLog = MagicMock()
    fc.Console.PrintMessage = MagicMock()
    fc.Console.PrintWarning = MagicMock()
    fc.Console.PrintError = MagicMock()
    fc.Vector = MagicMock(side_effect=lambda x, y, z: MagicMock())

    doc = MagicMock()
    doc.Name = "TestDoc"
    doc.Objects = []
    fc.ActiveDocument = doc
    fc.newDocument = MagicMock(return_value=doc)
    fc.open = MagicMock(return_value=doc)
    return fc


def _make_freecadgui_mock() -> types.ModuleType:
    fcg = types.ModuleType("FreeCADGui")
    fcg.activateWorkbench = MagicMock()
    fcg.ActiveDocument = MagicMock()
    fcg.Selection = MagicMock()
    fcg.Selection.getSelection = MagicMock(return_value=[])
    return fcg


def _make_part_mock() -> types.ModuleType:
    part = types.ModuleType("Part")
    part.makeBox = MagicMock()
    part.makeCylinder = MagicMock()
    part.makeSphere = MagicMock()
    part.makeCone = MagicMock()
    # Geometry classes used by Sketcher tools
    part.Vector = MagicMock(side_effect=lambda x, y, z: MagicMock())
    part.LineSegment = MagicMock(return_value=MagicMock())
    part.Circle = MagicMock(return_value=MagicMock())
    part.ArcOfCircle = MagicMock(return_value=MagicMock())
    return part


def _make_sketcher_mock() -> types.ModuleType:
    sk = types.ModuleType("Sketcher")
    sk.Constraint = MagicMock(return_value=MagicMock())
    return sk


# Install mocks into sys.modules before any freecad_ai import
_FC = _make_freecad_mock()
_FCG = _make_freecadgui_mock()
_PART = _make_part_mock()
_SK = _make_sketcher_mock()

sys.modules.setdefault("FreeCAD", _FC)
sys.modules.setdefault("FreeCADGui", _FCG)
sys.modules.setdefault("Part", _PART)
sys.modules.setdefault("PartDesign", types.ModuleType("PartDesign"))
sys.modules.setdefault("Sketcher", _SK)
sys.modules.setdefault("Draft", types.ModuleType("Draft"))
sys.modules.setdefault("Arch", types.ModuleType("Arch"))


@pytest.fixture()
def mock_fc():
    """Fresh FreeCAD mock with active document per test."""
    fc = sys.modules["FreeCAD"]
    doc = MagicMock()
    doc.Name = "TestDoc"
    doc.Objects = []
    fc.ActiveDocument = doc
    yield fc
    fc.ActiveDocument = MagicMock()  # reset


@pytest.fixture()
def no_document():
    """FreeCAD mock with no active document."""
    fc = sys.modules["FreeCAD"]
    original = fc.ActiveDocument
    fc.ActiveDocument = None
    yield fc
    fc.ActiveDocument = original


@pytest.fixture()
def registry():
    from freecad_ai.registry import ToolRegistry

    return ToolRegistry()
