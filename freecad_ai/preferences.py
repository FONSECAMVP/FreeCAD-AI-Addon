"""
Preferences module — DES-006, REQ-001, DEC-006.
Non-sensitive fields: FreeCAD Preferences XML.
API keys: OS keychain via keyring; fallback to env vars.

OpenAI and Anthropic settings are stored independently so switching
providers never sends the wrong model name to the wrong API.
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
_KEY_OPENAI = "api_key"
_KEY_ANTHROPIC = "anthropic_api_key"

_PROVIDERS = ("openai", "anthropic")

_DEFAULTS: dict = {
    "provider": "openai",
    # OpenAI-compatible section
    "base_url": "http://localhost:11434/v1",
    "openai_model": "gpt-4o",
    # Anthropic section
    "anthropic_model": "claude-sonnet-4-6",
    # General
    "max_tokens": 8000,
}


class _NoKeyring:
    def get_password(self, service: str, key: str) -> None:
        return None

    def set_password(self, service: str, key: str, value: str) -> None:
        pass


class AIPreferences:
    """
    Thin wrapper over FreeCAD Preferences + keyring.
    Falls back to an in-memory dict in headless/test mode.
    """

    def __init__(self) -> None:
        self._mem: dict = {}
        try:
            import FreeCAD  # lazy

            self._fc_prefs = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/AIAddon")
        except (ImportError, AttributeError):
            self._fc_prefs = None

    # --- internal helpers ---

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

    def _kr_get(self, key_name: str, env_var: str) -> str | None:
        try:
            val = self._keyring().get_password(_SERVICE, key_name)
        except Exception:
            val = None
        return val or os.environ.get(env_var) or None

    # --- provider ---

    @property
    def provider(self) -> str:
        val = self._get_str("provider")
        return val if val in _PROVIDERS else "openai"

    @provider.setter
    def provider(self, value: str) -> None:
        if value in _PROVIDERS:
            self._set_str("provider", value)

    # --- OpenAI-compatible settings ---

    @property
    def base_url(self) -> str:
        return self._get_str("base_url")

    @base_url.setter
    def base_url(self, value: str) -> None:
        self._set_str("base_url", value)

    @property
    def openai_model(self) -> str:
        return self._get_str("openai_model")

    @openai_model.setter
    def openai_model(self, value: str) -> None:
        self._set_str("openai_model", value)

    @property
    def api_key(self) -> str | None:
        return self._kr_get(_KEY_OPENAI, "FC_AI_API_KEY")

    @api_key.setter
    def api_key(self, value: str) -> None:
        self._keyring().set_password(_SERVICE, _KEY_OPENAI, value)

    # --- Anthropic settings ---

    @property
    def anthropic_model(self) -> str:
        return self._get_str("anthropic_model")

    @anthropic_model.setter
    def anthropic_model(self, value: str) -> None:
        self._set_str("anthropic_model", value)

    @property
    def anthropic_api_key(self) -> str | None:
        return self._kr_get(_KEY_ANTHROPIC, "FC_AI_ANTHROPIC_KEY")

    @anthropic_api_key.setter
    def anthropic_api_key(self, value: str) -> None:
        self._keyring().set_password(_SERVICE, _KEY_ANTHROPIC, value)

    # --- derived / general ---

    @property
    def model(self) -> str:
        """Active model for the selected provider."""
        if self.provider == "anthropic":
            return self.anthropic_model
        return self.openai_model

    @property
    def max_tokens(self) -> int:
        return self._get_int("max_tokens")

    @max_tokens.setter
    def max_tokens(self, value: int) -> None:
        self._set_int("max_tokens", value)

    @property
    def is_configured(self) -> bool:
        if self.provider == "anthropic":
            return self.anthropic_api_key is not None
        return self.api_key is not None


class AIPreferencePage:
    """
    REQ-001, DEC-006, DES-006 — FreeCAD preferences page.
    OpenAI and Anthropic are configured in separate named sections.
    """

    def __init__(self, _parent=None):
        try:
            from PySide2.QtWidgets import (
                QComboBox,
                QFormLayout,
                QGroupBox,
                QLabel,
                QLineEdit,
                QSpinBox,
                QVBoxLayout,
                QWidget,
            )
        except ImportError:
            from PySide6.QtWidgets import (  # type: ignore[no-redef]
                QComboBox,
                QFormLayout,
                QGroupBox,
                QLabel,
                QLineEdit,
                QSpinBox,
                QVBoxLayout,
                QWidget,
            )

        self._prefs = AIPreferences()
        self.form = QWidget()
        self.form.setWindowTitle("Settings")
        root = QVBoxLayout(self.form)
        root.setSpacing(8)

        # --- Provider selector ---
        top_form = QFormLayout()
        self._provider = QComboBox()
        self._provider.addItem("OpenAI / Compatible", "openai")
        self._provider.addItem("Anthropic (Claude)", "anthropic")
        top_form.addRow(QLabel("Active provider:"), self._provider)
        root.addLayout(top_form)

        # --- OpenAI section ---
        self._openai_box = QGroupBox("OpenAI / Compatible")
        oai_form = QFormLayout(self._openai_box)

        self._base_url = QLineEdit()
        self._base_url.setPlaceholderText("http://localhost:11434/v1")
        oai_form.addRow(QLabel("API base URL:"), self._base_url)

        self._openai_model = QLineEdit()
        self._openai_model.setPlaceholderText("gpt-4o")
        oai_form.addRow(QLabel("Model:"), self._openai_model)

        self._api_key = QLineEdit()
        self._api_key.setPlaceholderText("sk-… (stored in OS keychain)")
        self._api_key.setEchoMode(QLineEdit.Password)
        oai_form.addRow(QLabel("API key:"), self._api_key)

        root.addWidget(self._openai_box)

        # --- Anthropic section ---
        self._anthropic_box = QGroupBox("Anthropic (Claude)")
        ant_form = QFormLayout(self._anthropic_box)

        self._anthropic_model = QLineEdit()
        self._anthropic_model.setPlaceholderText("claude-sonnet-4-6")
        ant_form.addRow(QLabel("Model:"), self._anthropic_model)

        self._anthropic_key = QLineEdit()
        self._anthropic_key.setPlaceholderText("sk-ant-… (stored in OS keychain)")
        self._anthropic_key.setEchoMode(QLineEdit.Password)
        ant_form.addRow(QLabel("API key:"), self._anthropic_key)

        root.addWidget(self._anthropic_box)

        # --- General section ---
        general_box = QGroupBox("General")
        gen_form = QFormLayout(general_box)

        self._max_tokens = QSpinBox()
        self._max_tokens.setRange(1000, 128000)
        self._max_tokens.setSingleStep(1000)
        gen_form.addRow(QLabel("Max context tokens:"), self._max_tokens)

        root.addWidget(general_box)
        root.addStretch()

        self._provider.currentIndexChanged.connect(self._on_provider_changed)
        self.loadSettings()

    def _on_provider_changed(self, _index: int = 0) -> None:
        provider = self._provider.currentData()
        # Bold the active section, dim the inactive one
        self._openai_box.setEnabled(True)
        self._anthropic_box.setEnabled(True)
        if provider == "openai":
            self._openai_box.setStyleSheet("QGroupBox { font-weight: bold; }")
            self._anthropic_box.setStyleSheet("QGroupBox { color: gray; }")
        else:
            self._openai_box.setStyleSheet("QGroupBox { color: gray; }")
            self._anthropic_box.setStyleSheet("QGroupBox { font-weight: bold; }")

    def loadSettings(self):
        idx = self._provider.findData(self._prefs.provider)
        if idx >= 0:
            self._provider.setCurrentIndex(idx)

        self._base_url.setText(self._prefs.base_url)
        self._openai_model.setText(self._prefs.openai_model)
        self._api_key.setText(self._prefs.api_key or "")

        self._anthropic_model.setText(self._prefs.anthropic_model)
        self._anthropic_key.setText(self._prefs.anthropic_api_key or "")

        self._max_tokens.setValue(self._prefs.max_tokens)
        self._on_provider_changed()

    def saveSettings(self):
        self._prefs.provider = self._provider.currentData()

        self._prefs.base_url = self._base_url.text().strip()
        openai_model = self._openai_model.text().strip()
        if openai_model:
            self._prefs.openai_model = openai_model

        openai_key = self._api_key.text().strip()
        if openai_key:
            self._prefs.api_key = openai_key

        anthropic_model = self._anthropic_model.text().strip()
        if anthropic_model:
            self._prefs.anthropic_model = anthropic_model

        anthropic_key = self._anthropic_key.text().strip()
        if anthropic_key:
            self._prefs.anthropic_api_key = anthropic_key

        self._prefs.max_tokens = self._max_tokens.value()
