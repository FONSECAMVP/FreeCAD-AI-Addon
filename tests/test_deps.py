"""REQ-028: dep-check at load — DEPS_OK flag, graceful degradation, no crash."""

import sys
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _restore_freecad_ai():
    """Save and restore freecad_ai module state around each test."""
    saved = {
        k: v for k, v in sys.modules.items() if k == "freecad_ai" or k.startswith("freecad_ai.")
    }
    yield
    for k in list(sys.modules):
        if k == "freecad_ai" or k.startswith("freecad_ai."):
            del sys.modules[k]
    sys.modules.update(saved)


def _fresh_import():
    """Remove freecad_ai from sys.modules and re-import so __init__.py re-runs."""
    for k in list(sys.modules):
        if k == "freecad_ai" or k.startswith("freecad_ai."):
            del sys.modules[k]
    import freecad_ai

    return freecad_ai


@pytest.mark.fast
def test_deps_ok_when_all_present():
    """openai + anthropic + keyring importable → DEPS_OK True, _MISSING empty."""
    mod = _fresh_import()
    assert mod.DEPS_OK is True
    assert [] == mod._MISSING


@pytest.mark.fast
def test_deps_fail_openai_missing():
    """openai absent → DEPS_OK False, 'openai' in _MISSING, no exception raised."""
    with patch.dict(sys.modules, {"openai": None}):
        mod = _fresh_import()
    assert mod.DEPS_OK is False
    assert "openai" in mod._MISSING
    assert "keyring" not in mod._MISSING


@pytest.mark.fast
def test_deps_fail_keyring_missing():
    """keyring absent → DEPS_OK False, 'keyring' in _MISSING, no exception raised."""
    with patch.dict(sys.modules, {"keyring": None}):
        mod = _fresh_import()
    assert mod.DEPS_OK is False
    assert "keyring" in mod._MISSING
    assert "openai" not in mod._MISSING


@pytest.mark.fast
def test_deps_fail_both_missing():
    """All three absent → DEPS_OK False, all in _MISSING, no exception raised."""
    with patch.dict(sys.modules, {"openai": None, "anthropic": None, "keyring": None}):
        mod = _fresh_import()
    assert mod.DEPS_OK is False
    assert set(mod._MISSING) == {"openai", "anthropic", "keyring"}
