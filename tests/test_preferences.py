"""
Tests for preferences module — REQ-001, DEC-006 (keyring storage).
"""

import os
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.fast


@pytest.fixture()
def prefs():
    from freecad_ai.preferences import AIPreferences

    return AIPreferences()


# --- base_url / model stored in FreeCAD preferences (non-sensitive) ---


def test_get_base_url_default(prefs):
    assert prefs.base_url == "http://localhost:11434/v1"


def test_set_and_get_base_url(prefs):
    prefs.base_url = "https://api.openai.com/v1"
    assert prefs.base_url == "https://api.openai.com/v1"


def test_get_model_default(prefs):
    assert prefs.model == "gpt-4o"


def test_set_and_get_model(prefs):
    prefs.model = "claude-sonnet-4-6"
    assert prefs.model == "claude-sonnet-4-6"


def test_get_max_tokens_default(prefs):
    assert prefs.max_tokens == 8000


def test_set_and_get_max_tokens(prefs):
    prefs.max_tokens = 4000
    assert prefs.max_tokens == 4000


# --- api_key stored via keyring (DEC-006) ---


def test_get_api_key_from_keyring(prefs):
    with patch("freecad_ai.preferences.keyring") as mock_kr:
        mock_kr.get_password.return_value = "sk-test-key"
        assert prefs.api_key == "sk-test-key"
        mock_kr.get_password.assert_called_once_with("freecad-ai", "api_key")


def test_set_api_key_stores_in_keyring(prefs):
    with patch("freecad_ai.preferences.keyring") as mock_kr:
        prefs.api_key = "sk-new-key"
        mock_kr.set_password.assert_called_once_with("freecad-ai", "api_key", "sk-new-key")


def test_get_api_key_falls_back_to_env_var(prefs):
    with patch("freecad_ai.preferences.keyring") as mock_kr:
        mock_kr.get_password.return_value = None
        with patch.dict(os.environ, {"FC_AI_API_KEY": "sk-env-key"}):
            assert prefs.api_key == "sk-env-key"


def test_get_api_key_returns_none_when_absent(prefs):
    with patch("freecad_ai.preferences.keyring") as mock_kr:
        mock_kr.get_password.return_value = None
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("FC_AI_API_KEY", None)
            assert prefs.api_key is None


def test_get_api_key_falls_back_when_keyring_unavailable(prefs):
    from freecad_ai.preferences import _NoKeyring

    with (
        patch("freecad_ai.preferences.keyring", _NoKeyring()),
        patch.dict(os.environ, {"FC_AI_API_KEY": "sk-fallback"}),
    ):
        assert prefs.api_key == "sk-fallback"


# --- is_configured ---


def test_is_configured_true_when_key_present(prefs):
    with patch("freecad_ai.preferences.keyring") as mock_kr:
        mock_kr.get_password.return_value = "sk-key"
        assert prefs.is_configured is True


def test_is_configured_false_when_no_key(prefs):
    with patch("freecad_ai.preferences.keyring") as mock_kr:
        mock_kr.get_password.return_value = None
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("FC_AI_API_KEY", None)
            assert prefs.is_configured is False


# --- AIPreferencePage Qt widget (REQ-001 — FreeCAD preferences dialog entry) ---


@pytest.fixture()
def qapp():
    """Module-wide QApplication for headless Qt widget tests (offscreen platform)."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide2.QtWidgets import QApplication
    except ImportError:
        pytest.skip("PySide2 not available")
    app = QApplication.instance() or QApplication([])
    yield app


def test_preference_page_constructs_and_loads_settings(qapp):
    from freecad_ai.preferences import AIPreferencePage

    with patch("freecad_ai.preferences.keyring") as mock_kr:
        mock_kr.get_password.return_value = "sk-loaded"
        page = AIPreferencePage()
        # _Page reads from a fresh AIPreferences in its __init__
        assert page._base_url.text() == "http://localhost:11434/v1"
        assert page._model.text() == "gpt-4o"
        assert page._api_key.text() == "sk-loaded"
        assert page._max_tokens.value() == 8000


def test_preference_page_save_writes_back_to_prefs(qapp):
    from freecad_ai.preferences import AIPreferencePage

    with patch("freecad_ai.preferences.keyring") as mock_kr:
        mock_kr.get_password.return_value = None
        page = AIPreferencePage()
        page._base_url.setText("https://api.openai.com/v1")
        page._model.setText("gpt-4o-mini")
        page._api_key.setText("sk-new")
        page._max_tokens.setValue(16000)

        page.saveSettings()

        assert page._prefs.base_url == "https://api.openai.com/v1"
        assert page._prefs.model == "gpt-4o-mini"
        assert page._prefs.max_tokens == 16000
        mock_kr.set_password.assert_called_with("freecad-ai", "api_key", "sk-new")


def test_preference_page_save_skips_empty_api_key(qapp):
    """Blank api_key field must not overwrite a stored key (prevents accidental wipe)."""
    from freecad_ai.preferences import AIPreferencePage

    with patch("freecad_ai.preferences.keyring") as mock_kr:
        mock_kr.get_password.return_value = "sk-existing"
        page = AIPreferencePage()
        page._api_key.setText("")  # user blanked the field
        page.saveSettings()
        mock_kr.set_password.assert_not_called()
