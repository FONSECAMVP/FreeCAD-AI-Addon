#!/usr/bin/env python3
"""
FreeCAD-AI MCP server
=====================

Turns the FONSECAMVP/FreeCAD-AI-Addon into a Model Context Protocol (MCP)
server. Instead of reimplementing anything, this *wraps the addon's own code*:
it imports the addon's ``ToolRegistry``, loads all six tool modules
(part, partdesign, sketcher, draft, bim, inspection) and re-exposes every
registered tool over MCP — reusing the addon's exact JSON schemas, argument
validation, and handlers.

It must run with a Python interpreter that can ``import FreeCAD`` — i.e.
FreeCAD's bundled interpreter (``freecadcmd``) or a system Python with FreeCAD
on ``PYTHONPATH``. Works headless: GUI calls (workbench activation) are made
only when ``FreeCADGui`` is importable and are skipped otherwise.

Usage
-----
    freecadcmd freecad_mcp_server.py            # run the MCP server (stdio)
    python3   freecad_mcp_server.py --selfcheck # verify wiring w/o FreeCAD

Environment
-----------
    FREECAD_AI_ADDON_PATH      Path to the addon repo (auto-detected if unset)
    FREECAD_AI_AUTOCREATE_DOC  "1"/"0" — auto-create a document on first edit
                               when none is open (default: 1)
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

# --------------------------------------------------------------------------- #
#  Locate and import the addon package (the repo we are "becoming").
# --------------------------------------------------------------------------- #


def _find_addon_root() -> Path:
    """Find the directory that contains the ``freecad_ai`` package."""
    candidates: list[Path] = []
    env = os.environ.get("FREECAD_AI_ADDON_PATH")
    if env:
        candidates.append(Path(env).expanduser())
    here = Path(__file__).resolve().parent
    candidates += [
        here,
        here / "FreeCAD-AI-Addon",
        here.parent,
        here.parent / "FreeCAD-AI-Addon",
    ]
    for c in candidates:
        if (c / "freecad_ai" / "registry.py").is_file():
            return c
    raise RuntimeError(
        "Could not locate the FreeCAD-AI-Addon package (freecad_ai/registry.py). "
        "Set FREECAD_AI_ADDON_PATH to the repo root."
    )


ADDON_ROOT = _find_addon_root()
if str(ADDON_ROOT) not in sys.path:
    sys.path.insert(0, str(ADDON_ROOT))

import contextlib  # noqa: E402

with contextlib.redirect_stdout(sys.stderr):
    from freecad_ai.executor import _WORKBENCH_MAP, _validate_args  # noqa: E402
    from freecad_ai.registry import ToolRegistry  # noqa: E402

# Tool plugin modules — each exposes register_tools(registry).
_TOOL_MODULES = (
    "freecad_ai.tools.part",
    "freecad_ai.tools.partdesign",
    "freecad_ai.tools.sketcher",
    "freecad_ai.tools.draft",
    "freecad_ai.tools.bim",
    "freecad_ai.tools.inspection",
)


def build_registry() -> ToolRegistry:
    """Build the addon's registry by loading every tool plugin module.

    The addon's package __init__ may print to stdout (dependency bootstrap
    messages). On an MCP stdio server, stdout carries JSON-RPC, so we redirect
    any such output to stderr while importing.
    """
    import contextlib
    import importlib

    registry = ToolRegistry()
    with contextlib.redirect_stdout(sys.stderr):
        for modname in _TOOL_MODULES:
            mod = importlib.import_module(modname)
            mod.register_tools(registry)
    return registry


REGISTRY = build_registry()

AUTO_CREATE_DOC = os.environ.get("FREECAD_AI_AUTOCREATE_DOC", "1") not in ("0", "false", "False")

# --------------------------------------------------------------------------- #
#  Document-management tools (not in the addon registry).
#
#  The addon's tools all operate on FreeCAD.ActiveDocument and error out when
#  none exists. In the GUI that's fine — a user has a document open. A headless
#  MCP server has no GUI, so we add a small set of document/lifecycle tools so
#  an agent can actually get work done end-to-end.
# --------------------------------------------------------------------------- #

_DOC_TOOLS: dict[str, dict] = {
    "new_document": {
        "description": "Create a new, empty FreeCAD document and make it active.",
        "inputSchema": {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "Document name"}},
            "required": [],
        },
    },
    "open_document": {
        "description": "Open an existing .FCStd document from disk and make it active.",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Path to .FCStd file"}},
            "required": ["path"],
        },
    },
    "save_document": {
        "description": "Save the active document (must have been saved to a path before).",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    "save_document_as": {
        "description": "Save the active document to a specific .FCStd path.",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Destination .FCStd path"}},
            "required": ["path"],
        },
    },
    "list_documents": {
        "description": "List all open FreeCAD documents and indicate the active one.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    "recompute": {
        "description": "Force a recompute of the active document.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
}


def _dispatch_doc_tool(name: str, args: dict) -> dict:
    import FreeCAD  # lazy

    if name == "new_document":
        doc = FreeCAD.newDocument(args.get("name", "Unnamed"))
        return {"document": doc.Name, "status": "created"}

    if name == "open_document":
        path = args["path"]
        if not os.path.isfile(path):
            return {"error": "execution", "message": f"File not found: {path}"}
        doc = FreeCAD.open(path)
        return {"document": doc.Name, "status": "opened"}

    doc = FreeCAD.ActiveDocument
    if doc is None:
        return {"error": "no_document", "message": "No active document."}

    if name == "save_document":
        try:
            doc.save()
            return {"document": doc.Name, "status": "saved", "path": doc.FileName}
        except Exception as exc:  # no path set yet
            return {"error": "execution", "message": f"Save failed ({exc}); use save_document_as."}

    if name == "save_document_as":
        doc.saveAs(args["path"])
        return {"document": doc.Name, "status": "saved", "path": doc.FileName}

    if name == "list_documents":
        active = FreeCAD.ActiveDocument.Name if FreeCAD.ActiveDocument else None
        return {
            "documents": list(FreeCAD.listDocuments().keys()),
            "active": active,
        }

    if name == "recompute":
        doc.recompute()
        return {"document": doc.Name, "status": "recomputed"}

    return {"error": "unknown_tool", "name": name}


# --------------------------------------------------------------------------- #
#  Dispatch into the addon's registered handlers.
#
#  Mirrors freecad_ai.executor.ToolExecutor.dispatch: active-document guard,
#  schema validation (reused verbatim), workbench activation (GUI-optional),
#  and openTransaction / commit / abort hardening.
# --------------------------------------------------------------------------- #


def _dispatch_addon_tool(name: str, args: dict) -> dict:
    import FreeCAD  # lazy

    entry = REGISTRY.get_entry(name)
    if entry is None:
        return {"error": "unknown_tool", "name": name}

    if FreeCAD.ActiveDocument is None:
        if AUTO_CREATE_DOC:
            FreeCAD.newDocument("Unnamed")
        else:
            return {
                "error": "no_document",
                "message": "No active document. Call new_document or open_document first.",
            }

    err = _validate_args(entry["schema"], args)
    if err:
        return err

    # Workbench activation is GUI-only; skip cleanly when running headless.
    try:
        import FreeCADGui

        workbench = entry["workbench"]
        wb_name = _WORKBENCH_MAP.get(workbench, f"{workbench}Workbench")
        try:
            FreeCADGui.activateWorkbench(wb_name)
        except Exception:
            pass
    except ImportError:
        pass

    doc = FreeCAD.ActiveDocument
    doc.openTransaction(f"AI: {name}")
    try:
        result = entry["handler"](args)
        doc.commitTransaction()
        return result
    except Exception as exc:
        try:
            if FreeCAD.ActiveDocument:
                FreeCAD.ActiveDocument.abortTransaction()
        except Exception:
            pass
        return {"error": "execution", "message": str(exc)}


def dispatch(name: str, args: dict) -> dict:
    """Route a tool call to the doc-management layer or the addon registry."""
    args = args or {}
    if name in _DOC_TOOLS:
        return _dispatch_doc_tool(name, args)
    return _dispatch_addon_tool(name, args)


# --------------------------------------------------------------------------- #
#  MCP server (low-level Server API — tools are built dynamically from schemas).
# --------------------------------------------------------------------------- #


def _list_tool_specs() -> list[tuple[str, str, dict]]:
    """(name, description, inputSchema) for every exposed tool."""
    specs: list[tuple[str, str, dict]] = []
    for name, meta in _DOC_TOOLS.items():
        specs.append((name, meta["description"], meta["inputSchema"]))
    for schema in REGISTRY.get_tools_for_llm():
        fn = schema["function"]
        specs.append((fn["name"], fn.get("description", ""), fn["parameters"]))
    return specs


def build_mcp_server():
    import mcp.types as types
    from mcp.server import Server

    server = Server(
        "freecad-ai",
        version="0.1.0",
        instructions=(
            "Drives FreeCAD via the FreeCAD-AI-Addon toolset. Open or create a "
            "document (new_document / open_document) before editing. Objects are "
            "referenced by their Label. Use list_objects / get_bounding_box to "
            "inspect the model, and save_document_as to persist work."
        ),
    )

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [
            types.Tool(name=n, description=d, inputSchema=s) for n, d, s in _list_tool_specs()
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
        # FreeCAD's API is synchronous and not thread-safe; run off the event loop.
        result = await asyncio.to_thread(dispatch, name, arguments or {})
        text = json.dumps(result, ensure_ascii=False, indent=2)
        return [types.TextContent(type="text", text=text)]

    return server


def _require_mcp() -> None:
    """Fail fast with a clear message when the MCP SDK is not installed.

    Without this check the process exits silently, producing an opaque
    "MCP error -32000: Connection closed" in the client with no hint of what
    went wrong or how to fix it.
    """
    try:
        import mcp.server  # noqa: F401
        import mcp.types  # noqa: F401
    except ImportError:
        import platform

        _flag = " --break-system-packages" if platform.system() == "Linux" else ""
        sys.stderr.write(
            "[freecad-ai] ERROR: 'mcp' package not found in FreeCAD's Python.\n"
            "Install it into the same Python that freecadcmd uses:\n\n"
            f"    python3 -m pip install --user{_flag} \"mcp>=1.2\"\n\n"
            "Then restart Claude Code (or whichever MCP client you are using).\n"
            "See MCP_SERVER_README.md for full setup instructions.\n"
        )
        sys.exit(1)


async def _run_stdio() -> None:
    _require_mcp()
    from mcp.server.stdio import stdio_server

    server = build_mcp_server()
    init_opts = server.create_initialization_options()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, init_opts)


# --------------------------------------------------------------------------- #
#  Self-check: verify wiring without a real FreeCAD install (injects mocks).
# --------------------------------------------------------------------------- #


def _selfcheck() -> int:
    import types as _t
    from unittest.mock import MagicMock

    fc = _t.ModuleType("FreeCAD")
    fc.Console = MagicMock()
    fc.Vector = MagicMock(side_effect=lambda *a: MagicMock())
    _doc = MagicMock()
    _doc.Name = "SelfCheck"
    _doc.Objects = []

    def _add(type_id, label):
        o = MagicMock()
        o.Label = label
        o.TypeId = type_id
        _doc.Objects.append(o)
        return o

    _doc.addObject = MagicMock(side_effect=_add)
    fc.ActiveDocument = _doc
    fc.newDocument = MagicMock(return_value=_doc)
    fc.listDocuments = MagicMock(return_value={"SelfCheck": _doc})
    sys.modules["FreeCAD"] = fc
    for extra in ("Part", "Sketcher", "Draft", "Arch", "PartDesign", "FreeCADGui"):
        sys.modules.setdefault(extra, _t.ModuleType(extra))

    specs = _list_tool_specs()
    print(f"Addon root : {ADDON_ROOT}")
    print(f"Tools      : {len(specs)} exposed "
          f"({len(_DOC_TOOLS)} document + {len(REGISTRY.get_tools_for_llm())} addon)")
    for n, _d, _s in specs:
        print(f"  - {n}")

    print("\nDispatch smoke tests:")
    r1 = dispatch("new_document", {"name": "T"})
    print("  new_document     ->", r1)
    r2 = dispatch("create_box", {"length": 10, "width": 20, "height": 5})
    print("  create_box       ->", r2)
    r3 = dispatch("create_box", {"length": -1, "width": 20, "height": 5})
    print("  create_box(bad)  ->", r3)
    r4 = dispatch("does_not_exist", {})
    print("  unknown_tool     ->", r4)

    ok = (
        len(specs) == len(_DOC_TOOLS) + len(REGISTRY.get_tools_for_llm())
        and r2.get("label") == "Box"
        and r3.get("error") == "validation"
        and r4.get("error") == "unknown_tool"
    )
    print("\nSELF-CHECK:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> None:
    if "--selfcheck" in sys.argv:
        raise SystemExit(_selfcheck())
    if "--list" in sys.argv:
        for n, d, _s in _list_tool_specs():
            print(f"{n}: {d}")
        return
    asyncio.run(_run_stdio())


if __name__ == "__main__":
    main()
