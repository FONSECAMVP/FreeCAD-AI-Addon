"""FreeCAD AI Addon — REQ-028: check deps at load, degrade gracefully."""

import sys as _sys
from pathlib import Path as _Path

_ADDON_ROOT = _Path(__file__).parent.parent

# Inject bundled .venv site-packages so openai/keyring are visible to FreeCAD's
# embedded Python without a system-wide install (PEP 668 managed environments).
_venv_site = (
    _ADDON_ROOT
    / ".venv"
    / "lib"
    / f"python{_sys.version_info.major}.{_sys.version_info.minor}"
    / "site-packages"
)
if _venv_site.is_dir() and str(_venv_site) not in _sys.path:
    _sys.path.insert(0, str(_venv_site))


def _bootstrap_deps() -> bool:
    """
    Create .venv inside the addon directory and pip-install dependencies
    if they are not already importable. Runs once on first use.
    Returns True if bootstrap succeeded or was not needed.
    """
    import subprocess

    try:
        import FreeCAD  # noqa: F401 — only for console messages
        _log = FreeCAD.Console.PrintMessage
        _warn = FreeCAD.Console.PrintWarning
    except ImportError:
        _log = print
        _warn = print

    venv_dir = _ADDON_ROOT / ".venv"
    _log("[AI Addon] First-time setup: installing dependencies (openai, keyring)…\n")

    try:
        # Create the venv using FreeCAD's own Python interpreter.
        subprocess.run(
            [_sys.executable, "-m", "venv", str(venv_dir)],
            check=True,
            timeout=60,
        )
    except Exception as exc:
        _warn(f"[AI Addon] Could not create venv: {exc}\n")
        return False

    # Locate pip inside the new venv (cross-platform).
    pip = venv_dir / "bin" / "pip"
    if not pip.exists():
        pip = venv_dir / "Scripts" / "pip.exe"  # Windows
    if not pip.exists():
        _warn("[AI Addon] pip not found in new venv.\n")
        return False

    try:
        subprocess.run(
            [str(pip), "install", "--quiet", "openai>=1.30", "anthropic>=0.25", "keyring>=24"],
            check=True,
            timeout=120,
        )
    except Exception as exc:
        _warn(f"[AI Addon] Dependency install failed: {exc}\n")
        return False

    # Re-inject the newly populated site-packages.
    site = (
        venv_dir
        / "lib"
        / f"python{_sys.version_info.major}.{_sys.version_info.minor}"
        / "site-packages"
    )
    if site.is_dir() and str(site) not in _sys.path:
        _sys.path.insert(0, str(site))

    _log("[AI Addon] Dependencies installed. Restart FreeCAD to activate the chat panel.\n")
    return True


_MISSING: list[str] = []

try:
    import openai  # noqa: F401

    # DEC-012: must run after openai import, before any openai response is parsed
    from . import _compat  # noqa: F401
except ImportError:
    _MISSING.append("openai")

try:
    import anthropic  # noqa: F401
except ImportError:
    _MISSING.append("anthropic")

try:
    import keyring  # noqa: F401
except ImportError:
    _MISSING.append("keyring")

DEPS_OK = len(_MISSING) == 0

if not DEPS_OK:
    # Attempt one-time automatic bootstrap before giving up.
    _bootstrapped = _bootstrap_deps()
    if not _bootstrapped:
        try:
            import FreeCAD

            FreeCAD.Console.PrintWarning(
                f"[AI Addon] Missing dependencies: {', '.join(_MISSING)}.\n"
                "Automatic install failed. Run manually:\n"
                f"  pip install {' '.join(_MISSING)}\n"
                "Then restart FreeCAD.\n"
            )
        except ImportError:
            pass
