"""
Python 3.13 / SDK compatibility shim — DEC-012.

Python 3.13 tightened isinstance() against runtime-checkable Protocols:
non-method members (data attributes and @property) now raise TypeError
instead of being silently ignored.  Three third-party packages trigger
this with the SDKs we use:

1. openai._models._ConfigProtocol  — data attribute 'allow_population_by_field_name'
2. anthropic._models._ConfigProtocol — same pattern
3. annotated_types.GroupedMetadata  — @property __is_annotated_types_grouped_metadata__

Fixes applied:
  1 & 2 — replace _ConfigProtocol with a plain class (isinstance always
           returns False, which is correct: SDK models don't set that flag).
  3      — inject __subclasshook__ that checks for the attribute directly,
           bypassing Protocol machinery.  We cannot replace GroupedMetadata
           because annotated_types.Interval and Len inherit from it.
"""

from __future__ import annotations

import sys


# ---- fix 1 & 2: _ConfigProtocol ----------------------------------------

class _Py313ConfigCompat:
    """Plain-class substitute for _ConfigProtocol in openai/anthropic."""
    allow_population_by_field_name: bool


def _patch_openai_config_protocol() -> None:
    if sys.version_info < (3, 13):
        return
    try:
        import openai._models as _m
        _m._ConfigProtocol = _Py313ConfigCompat  # type: ignore[misc,assignment]
    except (ImportError, AttributeError):
        pass


def _patch_anthropic_config_protocol() -> None:
    if sys.version_info < (3, 13):
        return
    try:
        import anthropic._models as _m
        _m._ConfigProtocol = _Py313ConfigCompat  # type: ignore[misc,assignment]
    except (ImportError, AttributeError):
        pass


# ---- fix 3: annotated_types.GroupedMetadata -----------------------------

def _patch_annotated_types_grouped_metadata() -> None:
    """
    GroupedMetadata uses @property for __is_annotated_types_grouped_metadata__.
    Python 3.13 treats @property as a non-callable Protocol member, raising:

        TypeError: Protocols with non-method members don't support issubclass().
        Non-method members: '__is_annotated_types_grouped_metadata__'.

    Inject __subclasshook__ that checks for the attribute directly so the
    Protocol machinery is bypassed before it reaches the failing code path.
    """
    if sys.version_info < (3, 13):
        return
    try:
        import annotated_types as _at
        proto = getattr(_at, 'GroupedMetadata', None)
        if proto is None:
            return

        _marker = '__is_annotated_types_grouped_metadata__'
        _proto = proto  # capture for closure

        def _subclasshook(cls, C):  # type: ignore[misc]
            if cls is _proto:
                return hasattr(C, _marker)
            return NotImplemented

        proto.__subclasshook__ = classmethod(_subclasshook)
    except Exception:
        pass


_patch_openai_config_protocol()
_patch_anthropic_config_protocol()
_patch_annotated_types_grouped_metadata()
