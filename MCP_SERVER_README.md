# FreeCAD-AI MCP Server

Turns [FONSECAMVP/FreeCAD-AI-Addon](https://github.com/FONSECAMVP/FreeCAD-AI-Addon)
into a **Model Context Protocol (MCP) server**, so any MCP client (Claude
Desktop, Claude Code, etc.) can drive FreeCAD directly.

It does **not** reimplement the addon. It *wraps* it: on startup it imports the
addon's own `ToolRegistry`, loads all six tool modules, and re-exposes every
registered tool over MCP — reusing the addon's exact JSON schemas, argument
validation, and FreeCAD handlers. When the addon gains a tool, this server gains
it automatically.

The addon's built-in chat panel asks an LLM to call FreeCAD tools. This server
flips that around: **your MCP client is the LLM**, and FreeCAD is the toolset.
That means `openai` / `anthropic` / `keyring` are **not** needed here.

## Exposed tools (42)

**Document lifecycle (added by this server):** `new_document`, `open_document`,
`save_document`, `save_document_as`, `list_documents`, `recompute`

**From the addon (36), by workbench:**

| Workbench | Tools |
|---|---|
| Part | `create_box`, `create_cylinder`, `create_sphere`, `create_cone`, `boolean_union`, `boolean_cut`, `boolean_common` |
| PartDesign | `create_body`, `pad_sketch`, `pocket_sketch`, `add_fillet`, `add_chamfer` |
| Sketcher | `create_sketch`, `sketch_add_line`, `sketch_add_circle`, `sketch_add_arc`, `sketch_add_rectangle`, `sketch_constrain_distance`, `sketch_constrain_radius`, `sketch_constrain_coincident` |
| Draft | `draft_line`, `draft_rectangle`, `draft_circle`, `draft_bspline`, `draft_array`, `draft_move`, `draft_rotate` |
| BIM/Arch | `bim_wall`, `bim_slab`, `bim_column`, `bim_stair`, `bim_roof` |
| Inspection | `list_objects`, `get_object_properties`, `get_bounding_box`, `get_selection` |

## Requirements

- FreeCAD installed with `freecadcmd` available (it provides the Python that
  can `import FreeCAD`).
- The `mcp` package installed into that same Python (see install steps below).
- This addon repo on disk (this file lives at its root).

Headless is supported: GUI-only steps (workbench activation) are skipped when
`FreeCADGui` can't be imported. `get_selection` requires the GUI and will return
an error when headless.

## Install `mcp` into FreeCAD's Python

`freecadcmd` uses the system Python. Install `mcp` into it once:

**Linux (Debian / Ubuntu — Python is "externally managed" under PEP 668):**
```bash
python3 -m pip install --user --break-system-packages "mcp>=1.2"
```
`--break-system-packages` only bypasses Debian's guard; `--user` keeps
everything inside `~/.local/` and does not touch system packages.

**macOS / other Linux / Windows:**
```bash
python3 -m pip install --user "mcp>=1.2"
```

If `python3` is not FreeCAD's interpreter, use the full path:
```bash
/Applications/FreeCAD.app/Contents/Resources/bin/python3 \
    -m pip install "mcp>=1.2"     # macOS app bundle
```

## Verify without FreeCAD

```bash
python3 freecad_mcp_server.py --selfcheck   # injects mocks, checks wiring
python3 freecad_mcp_server.py --list        # print all tools + descriptions
```

## Run

```bash
freecadcmd freecad_mcp_server.py            # stdio MCP server
```

## Claude Code setup (`.mcp.json`)

The repo ships a `.mcp.json` in its root. Open the project directory in
Claude Code and it will detect this file and offer to enable the `freecad-ai`
server automatically — no manual config needed.

Pre-requisites:
- `freecadcmd` must be in `PATH` (`which freecadcmd` should return a path).
- `mcp>=1.2` must be installed (see above).

## Claude Desktop config

Add to `claude_desktop_config.json` (use absolute paths). Examples:

```json
{
  "mcpServers": {
    "freecad-ai": {
      "command": "/path/to/freecadcmd",
      "args": ["/path/to/FreeCAD-AI-Addon/freecad_mcp_server.py"]
    }
  }
}
```

If you instead use a regular Python that can import FreeCAD:

```json
{
  "mcpServers": {
    "freecad-ai": {
      "command": "python3",
      "args": ["/path/to/FreeCAD-AI-Addon/freecad_mcp_server.py"],
      "env": {
        "PYTHONPATH": "/path/to/FreeCAD/lib",
        "FREECAD_AI_ADDON_PATH": "/path/to/FreeCAD-AI-Addon"
      }
    }
  }
}
```

macOS bundled interpreter is typically
`/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd`. On Windows it's
`FreeCADCmd.exe` in the FreeCAD `bin` folder.

## Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `FREECAD_AI_ADDON_PATH` | auto-detect | Path to the addon repo root |
| `FREECAD_AI_AUTOCREATE_DOC` | `1` | Auto-create a document on first edit if none is open |

## How it maps to the addon

- `freecad_ai.registry.ToolRegistry` — schemas + handlers (reused as-is)
- `freecad_ai.executor._validate_args` — argument validation (reused as-is)
- `freecad_ai.executor` transaction + workbench logic — mirrored in `dispatch()`,
  with GUI calls made optional for headless use
- `freecad_ai.tools.*` — the six plugin modules, loaded via their
  `register_tools(registry)` entry points

## Notes & limits

- FreeCAD's API is synchronous and single-threaded; calls run on a worker thread
  off the asyncio loop and are serialized by FreeCAD itself.
- `get_selection` needs the GUI (returns an error headless).
- This wrapper does not start FreeCAD's GUI; for GUI-driven workflows, run it
  from within a FreeCAD instance's Python environment.
