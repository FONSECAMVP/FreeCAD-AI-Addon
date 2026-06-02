"""BIM/Arch workbench tools — REQ-014. All imports lazy (REQ-019)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from freecad_ai.registry import ToolRegistry


def _schema(name: str, desc: str, props: dict, req: list) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": desc,
            "parameters": {"type": "object", "properties": props, "required": req},
        },
    }


_N = {"type": "number"}
_I = {"type": "integer"}
_S = {"type": "string"}


def _handle_bim_wall(args: dict) -> dict:
    import Arch  # lazy

    length = args.get("length")
    height = args.get("height")
    width = args.get("width", 200.0)

    if height is None:
        return {"error": "validation", "field": "height", "reason": "required field missing"}
    if length is not None and length <= 0:
        return {"error": "validation", "field": "length", "reason": "must be > 0"}
    if height <= 0:
        return {"error": "validation", "field": "height", "reason": "must be > 0"}

    obj = Arch.makeWall(None, length=length, width=width, height=height)
    if args.get("label"):
        obj.Label = args["label"]
    return {"label": obj.Label, "length": length, "height": height, "width": width}


def _handle_bim_slab(args: dict) -> dict:
    import Arch  # lazy

    length = args["length"]
    width = args["width"]
    thickness = args["thickness"]
    if thickness <= 0:
        return {"error": "validation", "field": "thickness", "reason": "must be > 0"}
    obj = Arch.makeFloor()
    obj.Length = length
    obj.Width = width
    obj.Height = thickness
    if args.get("label"):
        obj.Label = args["label"]
    return {"label": obj.Label, "length": length, "width": width, "thickness": thickness}


def _handle_bim_column(args: dict) -> dict:
    import Arch  # lazy

    height = args["height"]
    width = args.get("width", 300.0)
    depth = args.get("depth", 300.0)
    if height <= 0:
        return {"error": "validation", "field": "height", "reason": "must be > 0"}
    obj = Arch.makeColumn(None, height=height)
    obj.Width = width
    obj.Depth = depth
    if args.get("label"):
        obj.Label = args["label"]
    return {"label": obj.Label, "height": height, "width": width, "depth": depth}


def _handle_bim_stair(args: dict) -> dict:
    import Arch  # lazy

    steps = args["steps"]
    step_height = args.get("step_height", 175.0)
    step_width = args.get("step_width", 250.0)
    if steps < 1:
        return {"error": "validation", "field": "steps", "reason": "must be >= 1"}
    obj = Arch.makeStairs(None, steps=steps)
    obj.RiserHeight = step_height
    obj.TreadDepth = step_width
    if args.get("label"):
        obj.Label = args["label"]
    return {"label": obj.Label, "steps": steps}


def _handle_bim_roof(args: dict) -> dict:
    import Arch  # lazy

    angle = args["angle"]
    if not (0 <= angle <= 90):
        return {"error": "validation", "field": "angle", "reason": "must be between 0 and 90"}
    obj = Arch.makeRoof(None, angles=[angle])
    if args.get("label"):
        obj.Label = args["label"]
    return {"label": obj.Label, "angle": angle}


def register_tools(registry: ToolRegistry) -> None:
    registry.register(
        "bim_wall",
        _schema(
            "bim_wall",
            "Create an Arch wall.",
            {
                "length": {**_N, "description": "Wall length mm"},
                "height": {**_N, "description": "Wall height mm"},
                "width": {**_N, "description": "Wall thickness mm (default 200)"},
                "label": {**_S, "description": "Object name"},
            },
            ["height"],
        ),
        _handle_bim_wall,
        workbench="BIM",
    )
    registry.register(
        "bim_slab",
        _schema(
            "bim_slab",
            "Create a floor slab.",
            {
                "length": {**_N, "description": "Slab length mm"},
                "width": {**_N, "description": "Slab width mm"},
                "thickness": {**_N, "description": "Slab thickness mm"},
                "label": {**_S, "description": "Object name"},
            },
            ["length", "width", "thickness"],
        ),
        _handle_bim_slab,
        workbench="BIM",
    )
    registry.register(
        "bim_column",
        _schema(
            "bim_column",
            "Create a structural column.",
            {
                "height": {**_N, "description": "Column height mm"},
                "width": {**_N, "description": "Column width mm (default 300)"},
                "depth": {**_N, "description": "Column depth mm (default 300)"},
                "label": {**_S, "description": "Object name"},
            },
            ["height"],
        ),
        _handle_bim_column,
        workbench="BIM",
    )
    registry.register(
        "bim_stair",
        _schema(
            "bim_stair",
            "Create a staircase.",
            {
                "steps": {**_I, "description": "Number of steps"},
                "step_height": {**_N, "description": "Riser height mm (default 175)"},
                "step_width": {**_N, "description": "Tread depth mm (default 250)"},
                "label": {**_S, "description": "Object name"},
            },
            ["steps"],
        ),
        _handle_bim_stair,
        workbench="BIM",
    )
    registry.register(
        "bim_roof",
        _schema(
            "bim_roof",
            "Create a roof with a given pitch angle.",
            {
                "angle": {**_N, "description": "Roof pitch angle degrees (0–90)"},
                "label": {**_S, "description": "Object name"},
            },
            ["angle"],
        ),
        _handle_bim_roof,
        workbench="BIM",
    )
