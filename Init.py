"""FreeCAD AI Addon — headless init (called at FreeCAD startup, with or without GUI)."""

import FreeCAD

from freecad_ai import _MISSING, DEPS_OK

if not DEPS_OK:
    FreeCAD.Console.PrintWarning(
        f"[AI Addon] Disabled — missing: {', '.join(_MISSING)}. "
        f"Run: pip install {' '.join(_MISSING)}\n"
    )
else:
    FreeCAD.Console.PrintMessage("[AI Addon] Loaded.\n")
