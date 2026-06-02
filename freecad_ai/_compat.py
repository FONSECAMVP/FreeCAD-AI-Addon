"""
Python 3.13 / openai SDK compatibility shim — DEC-012.

Python 3.13 made `isinstance()` against a runtime-checkable Protocol with
non-method members raise TypeError instead of returning False. The openai SDK
(verified 1.10.0 through 2.36.0) defines:

    class _ConfigProtocol(Protocol):
        allow_population_by_field_name: bool

and calls `isinstance(config, _ConfigProtocol)` inside the streaming response
parser. On Python 3.13, that raises:

    TypeError: Protocols with non-method members don't support issubclass().
    Non-method members: 'allow_population_by_field_name'.

The crash is non-deterministic per test because the ABC cache may hit True
before falling through to __subclasscheck__. In production, streaming responses
trigger it consistently.

Fix: replace `_ConfigProtocol` with a plain class that exposes the same
attribute. `isinstance()` then performs a normal type check and returns False
for SDK config objects, preserving the original semantics (the SDK only uses
the protocol to detect a pydantic-v1-style config flag, which the SDK does
not actually set on its own models).

Tested by tests/test_llm_client.py::test_streaming_through_real_sdk_parser.
"""

from __future__ import annotations

import sys


def _patch_openai_config_protocol() -> None:
    if sys.version_info < (3, 13):
        return
    try:
        import openai._models as _omodels
    except ImportError:
        return

    class _Py313ConfigCompat:
        allow_population_by_field_name: bool

    _omodels._ConfigProtocol = _Py313ConfigCompat  # type: ignore[misc,assignment]


_patch_openai_config_protocol()
