"""
Python 3.13 / SDK compatibility shim — DEC-012.

Python 3.13 made `isinstance()` against a runtime-checkable Protocol with
non-method members raise TypeError instead of returning False. Both the
openai and anthropic SDKs (which share the same httpx-based template) define:

    class _ConfigProtocol(Protocol):
        allow_population_by_field_name: bool

and call `isinstance(config, _ConfigProtocol)` inside their response parsers.
On Python 3.13 this raises:

    TypeError: Protocols with non-method members don't support issubclass().
    Non-method members: 'allow_population_by_field_name'.

Fix: replace each SDK's `_ConfigProtocol` with a plain class that exposes the
same attribute. `isinstance()` then performs a normal type check and returns
False, preserving the original semantics.
"""

from __future__ import annotations

import sys


class _Py313ConfigCompat:
    """Plain class substitute for Protocol classes with non-method members."""
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


_patch_openai_config_protocol()
_patch_anthropic_config_protocol()
