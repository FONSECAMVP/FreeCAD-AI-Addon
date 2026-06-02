"""
Tests for BIM/Arch workbench tools — REQ-014.
"""

import sys
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.fast


@pytest.fixture(autouse=True)
def arch_mock():
    import types

    arch = types.ModuleType("Arch")
    obj = MagicMock()
    obj.Label = "ArchObj"
    arch.makeWall = MagicMock(return_value=obj)
    arch.makeFloor = MagicMock(return_value=obj)  # slab via Floor
    arch.makeColumn = MagicMock(return_value=obj)
    arch.makeStairs = MagicMock(return_value=obj)
    arch.makeRoof = MagicMock(return_value=obj)
    sys.modules["Arch"] = arch
    yield arch


@pytest.fixture()
def bim_tools(registry):
    from freecad_ai.tools.bim import register_tools

    register_tools(registry)
    return registry


# --- registration ---


def test_bim_tools_registered(bim_tools):
    names = {t["function"]["name"] for t in bim_tools.get_tools_for_llm()}
    assert "bim_wall" in names
    assert "bim_slab" in names
    assert "bim_column" in names
    assert "bim_stair" in names
    assert "bim_roof" in names


# --- bim_wall ---


def test_bim_wall_creates_wall(mock_fc, bim_tools, arch_mock):
    from freecad_ai.executor import ToolExecutor

    ex = ToolExecutor(bim_tools)
    result = ex.dispatch("bim_wall", {"length": 3000.0, "height": 2800.0, "width": 200.0})
    assert "error" not in result
    arch_mock.makeWall.assert_called_once()


def test_bim_wall_requires_positive_dims(mock_fc, bim_tools):
    from freecad_ai.executor import ToolExecutor

    ex = ToolExecutor(bim_tools)
    result = ex.dispatch("bim_wall", {"length": 0.0, "height": 2800.0, "width": 200.0})
    assert result["error"] == "validation"


def test_bim_wall_height_required(mock_fc, bim_tools):
    from freecad_ai.executor import ToolExecutor

    ex = ToolExecutor(bim_tools)
    result = ex.dispatch("bim_wall", {"length": 3000.0, "width": 200.0})
    assert result["error"] == "validation"


# --- bim_slab ---


def test_bim_slab_creates_slab(mock_fc, bim_tools, arch_mock):
    from freecad_ai.executor import ToolExecutor

    ex = ToolExecutor(bim_tools)
    result = ex.dispatch("bim_slab", {"length": 5000.0, "width": 4000.0, "thickness": 200.0})
    assert "error" not in result
    arch_mock.makeFloor.assert_called_once()


def test_bim_slab_requires_positive_thickness(mock_fc, bim_tools):
    from freecad_ai.executor import ToolExecutor

    ex = ToolExecutor(bim_tools)
    result = ex.dispatch("bim_slab", {"length": 5000.0, "width": 4000.0, "thickness": 0.0})
    assert result["error"] == "validation"


# --- bim_column ---


def test_bim_column_creates_column(mock_fc, bim_tools, arch_mock):
    from freecad_ai.executor import ToolExecutor

    ex = ToolExecutor(bim_tools)
    result = ex.dispatch("bim_column", {"height": 3000.0, "width": 300.0, "depth": 300.0})
    assert "error" not in result
    arch_mock.makeColumn.assert_called_once()


def test_bim_column_requires_positive_height(mock_fc, bim_tools):
    from freecad_ai.executor import ToolExecutor

    ex = ToolExecutor(bim_tools)
    result = ex.dispatch("bim_column", {"height": -100.0, "width": 300.0, "depth": 300.0})
    assert result["error"] == "validation"


# --- bim_stair ---


def test_bim_stair_creates_stair(mock_fc, bim_tools, arch_mock):
    from freecad_ai.executor import ToolExecutor

    ex = ToolExecutor(bim_tools)
    result = ex.dispatch("bim_stair", {"steps": 12, "step_height": 175.0, "step_width": 250.0})
    assert "error" not in result
    arch_mock.makeStairs.assert_called_once()


def test_bim_stair_requires_at_least_one_step(mock_fc, bim_tools):
    from freecad_ai.executor import ToolExecutor

    ex = ToolExecutor(bim_tools)
    result = ex.dispatch("bim_stair", {"steps": 0, "step_height": 175.0, "step_width": 250.0})
    assert result["error"] == "validation"


# --- bim_roof ---


def test_bim_roof_creates_roof(mock_fc, bim_tools, arch_mock):
    from freecad_ai.executor import ToolExecutor

    ex = ToolExecutor(bim_tools)
    result = ex.dispatch("bim_roof", {"angle": 30.0})
    assert "error" not in result
    arch_mock.makeRoof.assert_called_once()


def test_bim_roof_angle_must_be_0_to_90(mock_fc, bim_tools):
    from freecad_ai.executor import ToolExecutor

    ex = ToolExecutor(bim_tools)
    result = ex.dispatch("bim_roof", {"angle": 95.0})
    assert result["error"] == "validation"
