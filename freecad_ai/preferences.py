"""
Preferences module — DES-006, REQ-001, DEC-006.
Non-sensitive fields: FreeCAD Preferences XML.
api_key: OS keychain via keyring; fallback to FC_AI_API_KEY env var.
"""

from __future__ import annotations

import os

try:
    import keyring
    import keyring.errors

    _KEYRING_OK = True
except ImportError:
    keyring = None  # type: ignore[assignment]
    _KEYRING_OK = False

_SERVICE = "freecad-ai"
_KEY_NAME = "api_key"

_DEFAULTS = {
    "base_url": "http://localhost:11434/v1",
    "model": "gpt-4o",
    "max_tokens": 8000,
}


class _NoKeyring:
    """Sentinel returned when keyring is unavailable."""

    def get_password(self, service: str, key: str) -> None:
        return None

    def set_password(self, service: str, key: str, value: str) -> None:
        pass


class AIPreferences:
    """
    Thin wrapper over FreeCAD Preferences + keyring.
    In headless/test mode, falls back to an in-memory dict.
    """

    def __init__(self) -> None:
        self._mem: dict = {}  # in-memory fallback (tests / headless)
        try:
            import FreeCAD  # lazy

            self._fc_prefs = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/AIAddon")
        except (ImportError, AttributeError):
            self._fc_prefs = None

    # --- helpers ---

    def _get_str(self, key: str) -> str:
        if self._fc_prefs:
            return self._fc_prefs.GetString(key, _DEFAULTS.get(key, ""))
        return self._mem.get(key, _DEFAULTS.get(key, ""))

    def _set_str(self, key: str, value: str) -> None:
        if self._fc_prefs:
            self._fc_prefs.SetString(key, value)
        else:
            self._mem[key] = value

    def _get_int(self, key: str) -> int:
        if self._fc_prefs:
            return self._fc_prefs.GetInt(key, _DEFAULTS.get(key, 0))
        return self._mem.get(key, _DEFAULTS.get(key, 0))

    def _set_int(self, key: str, value: int) -> None:
        if self._fc_prefs:
            self._fc_prefs.SetInt(key, value)
        else:
            self._mem[key] = value

    def _keyring(self):
        if not _KEYRING_OK or keyring is None:
            return _NoKeyring()
        return keyring

    # --- public properties ---

    @property
    def base_url(self) -> str:
        return self._get_str("base_url")

    @base_url.setter
    def base_url(self, value: str) -> None:
        self._set_str("base_url", value)

    @property
    def model(self) -> str:
        return self._get_str("model")

    @model.setter
    def model(self, value: str) -> None:
        self._set_str("model", value)

    @property
    def max_tokens(self) -> int:
        return self._get_int("max_tokens")

    @max_tokens.setter
    def max_tokens(self, value: int) -> None:
        self._set_int("max_tokens", value)

    @property
    def api_key(self) -> str | None:
        kr = self._keyring()
        try:
            val = kr.get_password(_SERVICE, _KEY_NAME)
        except Exception:
            val = None
        if val:
            return val
        return os.environ.get("FC_AI_API_KEY") or None

    @api_key.setter
    def api_key(self, value: str) -> None:
        self._keyring().set_password(_SERVICE, _KEY_NAME, value)

    @property
    def is_configured(self) -> bool:
        return self.api_key is not None


class AIPreferencePage:
    """
    REQ-001, DEC-006, DES-006 — FreeCAD preferences page.

    Standard FreeCAD prefs idiom (see AddonManager/AddonManagerOptions.py):
    plain class with `self.form` = QWidget built in `__init__`, plus
    saveSettings()/loadSettings() methods. FreeCAD instantiates the class
    each time the prefs dialog opens, reads `self.form` (Gui/WidgetFactory
    .cpp:285), then uses `form->windowTitle()` as the tab label
    (WidgetFactory.cpp:296). `__init__` accepts an optional positional
    arg because some FreeCAD code paths pass the parent.
    """

    def __init__(self, _parent=None):
        try:
            from PySide2.QtWidgets import (
                QFormLayout,
                QLabel,
                QLineEdit,
                QSpinBox,
                QWidget,
            )
        except ImportError:
            from PySide6.QtWidgets import (  # type: ignore[no-redef]
                QFormLayout,
                QLabel,
                QLineEdit,
                QSpinBox,
                QWidget,
            )

        self._prefs = AIPreferences()
        self.form = QWidget()
        # Empty windowTitle makes the page invisible in DlgPreferencesImp
        # (WidgetFactory.cpp:296 reads form->windowTitle()).
        self.form.setWindowTitle("Settings")
        layout = QFormLayout(self.form)

        self._base_url = QLineEdit()
        self._base_url.setPlaceholderText("http://localhost:11434/v1")
        layout.addRow(QLabel("API base URL:"), self._base_url)

        self._model = QLineEdit()
        self._model.setPlaceholderText("gpt-4o")
        layout.addRow(QLabel("Model name:"), self._model)

        self._api_key = QLineEdit()
        self._api_key.setPlaceholderText("sk-… (stored in OS keychain)")
        self._api_key.setEchoMode(QLineEdit.Password)
        layout.addRow(QLabel("API key:"), self._api_key)

        self._max_tokens = QSpinBox()
        self._max_tokens.setRange(1000, 128000)
        self._max_tokens.setSingleStep(1000)
        layout.addRow(QLabel("Max context tokens:"), self._max_tokens)

        self.loadSettings()

    def loadSettings(self):
        self._base_url.setText(self._prefs.base_url)
        self._model.setText(self._prefs.model)
        self._api_key.setText(self._prefs.api_key or "")
        self._max_tokens.setValue(self._prefs.max_tokens)

    def saveSettings(self):
        self._prefs.base_url = self._base_url.text().strip()
        self._prefs.model = self._model.text().strip()
        key = self._api_key.text().strip()
        if key:
            self._prefs.api_key = key
        self._prefs.max_tokens = self._max_tokens.value()
