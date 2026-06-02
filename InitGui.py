"""FreeCAD AI Addon — GUI init. Registers chat panel and tool registry."""

import FreeCAD
import FreeCADGui

from freecad_ai import DEPS_OK

if not DEPS_OK:
    # Already warned in Init.py — skip GUI setup silently
    pass
else:
    from freecad_ai.conversation import ConversationHistory
    from freecad_ai.executor import ToolExecutor
    from freecad_ai.llm_client import SYSTEM_PROMPT, LLMClient
    from freecad_ai.preferences import AIPreferencePage, AIPreferences
    from freecad_ai.registry import ToolRegistry

    # Build registry with all workbench plugins (REQ-003, REQ-019)
    _registry = ToolRegistry()

    from freecad_ai.tools import bim, draft, inspection, part, partdesign, sketcher

    part.register_tools(_registry)
    partdesign.register_tools(_registry)
    sketcher.register_tools(_registry)
    inspection.register_tools(_registry)
    draft.register_tools(_registry)
    bim.register_tools(_registry)

    tool_count = len(_registry.get_tools_for_llm())
    FreeCAD.Console.PrintMessage(f"[AI Addon] {tool_count} tools registered.\n")

    _executor = ToolExecutor(_registry)
    _prefs = AIPreferences()
    _history = ConversationHistory(system_prompt=SYSTEM_PROMPT, max_tokens=_prefs.max_tokens)

    # Default args bind values at def time. FreeCAD's mod loader execs InitGui.py
    # in a non-module scope, so `def` functions cannot resolve module-level names
    # at call time (the function's __globals__ is FreeCADGuiInit, not this scope).
    def _make_llm_client(_LLMClient=LLMClient, _prefs=_prefs):
        return _LLMClient(
            base_url=_prefs.base_url,
            api_key=_prefs.api_key or "",
            model=_prefs.model,
        )

    # Register chat panel (REQ-002) — deferred import to keep Qt out of headless path.
    # Use PySide2 directly: FreeCADGui.Qt does not expose Qt.RightDockWidgetArea on 1.0.
    try:
        from PySide2.QtCore import Qt
    except ImportError:
        from PySide6.QtCore import Qt  # type: ignore[no-redef]

    try:
        from freecad_ai.panel import AIChatPanel

        _panel = AIChatPanel(
            registry=_registry,
            executor=_executor,
            history=_history,
            make_client=_make_llm_client,
            prefs=_prefs,
        )
        FreeCADGui.getMainWindow().addDockWidget(Qt.RightDockWidgetArea, _panel)
        FreeCAD.Console.PrintMessage("[AI Addon] Chat panel ready.\n")
    except Exception as exc:
        FreeCAD.Console.PrintWarning(f"[AI Addon] Panel failed to load: {exc}\n")

    # Register preferences page (REQ-001)
    try:
        FreeCADGui.addPreferencePage(AIPreferencePage, "AI Addon")
        FreeCAD.Console.PrintMessage("[AI Addon] Preferences page registered.\n")
    except Exception as exc:
        FreeCAD.Console.PrintWarning(f"[AI Addon] Preferences page registration failed: {exc!r}\n")

    # Warn if not configured (A2-C1)
    if not _prefs.is_configured:
        FreeCAD.Console.PrintWarning(
            "[AI Addon] API key not set. Open Edit > Preferences > AI Addon.\n"
        )

    # Minimal Workbench so package.xml <workbench><classname> lookup succeeds.
    # FreeCAD 1.0+ scans user mods via the GUI loader only when package.xml
    # declares <content><workbench>; without this stub class and the workbench
    # content type, InitGui.py is skipped entirely. The addon's UX lives in
    # the chat panel + preferences page, not in workbench tools, so this
    # class is intentionally empty.
    class AIAddonWorkbench(FreeCADGui.Workbench):
        MenuText = "AI Addon"
        ToolTip = "AI chat panel with workbench tool registry"

        def Initialize(self):
            pass

        def Activated(self):
            pass

        def Deactivated(self):
            pass

        def GetClassName(self):
            return "Gui::PythonWorkbench"

    FreeCADGui.addWorkbench(AIAddonWorkbench())
