"""Part workbench tools — REQ-006. All FreeCAD imports are lazy (REQ-019)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from freecad_ai.registry import ToolRegistry


def _make_schema(name: str, description: str, properties: dict, required: list) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


def _handle_create_box(args: dict) -> dict:
    import FreeCAD  # lazy

    length, width, height = args["length"], args["width"], args["height"]
    if length <= 0 or width <= 0 or height <= 0:
        return {
            "error": "validation",
            "field": "length/width/height",
            "reason": "all dimensions must be > 0",
        }
    label = args.get("label", "Box")
    obj = FreeCAD.ActiveDocument.addObject("Part::Box", label)
    obj.Length, obj.Width, obj.Height = length, width, height
    FreeCAD.ActiveDocument.recompute()
    return {"label": obj.Label, "length": length, "width": width, "height": height}


def _handle_create_cylinder(args: dict) -> dict:
    import FreeCAD  # lazy

    radius, height = args["radius"], args["height"]
    if radius <= 0 or height <= 0:
        return {"error": "validation", "field": "radius/height", "reason": "must be > 0"}
    label = args.get("label", "Cylinder")
    obj = FreeCAD.ActiveDocument.addObject("Part::Cylinder", label)
    obj.Radius, obj.Height = radius, height
    FreeCAD.ActiveDocument.recompute()
    return {"label": obj.Label, "radius": radius, "height": height}


def _handle_create_sphere(args: dict) -> dict:
    import FreeCAD  # lazy

    radius = args["radius"]
    if radius <= 0:
        return {"error": "validation", "field": "radius", "reason": "must be > 0"}
    label = args.get("label", "Sphere")
    obj = FreeCAD.ActiveDocument.addObject("Part::Sphere", label)
    obj.Radius = radius
    FreeCAD.ActiveDocument.recompute()
    return {"label": obj.Label, "radius": radius}


def _handle_create_cone(args: dict) -> dict:
    import FreeCAD  # lazy

    r1, r2, height = args["radius1"], args["radius2"], args["height"]
    label = args.get("label", "Cone")
    obj = FreeCAD.ActiveDocument.addObject("Part::Cone", label)
    obj.Radius1, obj.Radius2, obj.Height = r1, r2, height
    FreeCAD.ActiveDocument.recompute()
    return {"label": obj.Label}


def _handle_boolean(args: dict, operation: str) -> dict:
    import FreeCAD  # lazy

    doc = FreeCAD.ActiveDocument
    base_label, tool_label = args["base"], args["tool"]
    base = doc.getObjectsByLabel(base_label)
    tool = doc.getObjectsByLabel(tool_label)
    if not base:
        return {"error": "execution", "message": f"Object '{base_label}' not found"}
    if not tool:
        return {"error": "execution", "message": f"Object '{tool_label}' not found"}
    type_map = {"union": "Part::Fuse", "cut": "Part::Cut", "common": "Part::Common"}
    obj = doc.addObject(type_map[operation], operation.capitalize())
    obj.Base, obj.Tool = base[0], tool[0]
    doc.recompute()
    return {"label": obj.Label, "operation": operation}


def register_tools(registry: ToolRegistry) -> None:
    _num = {"type": "number"}
    _str = {"type": "string"}

    registry.register(
        "create_box",
        _make_schema(
            "create_box",
            "Create a rectangular solid (Part::Box).",
            {
                "length": {**_num, "description": "Length mm"},
                "width": {**_num, "description": "Width mm"},
                "height": {**_num, "description": "Height mm"},
                "label": {**_str, "description": "Object name"},
            },
            ["length", "width", "height"],
        ),
        _handle_create_box,
        workbench="Part",
    )
    registry.register(
        "create_cylinder",
        _make_schema(
            "create_cylinder",
            "Create a cylinder (Part::Cylinder).",
            {
                "radius": {**_num, "description": "Radius mm"},
                "height": {**_num, "description": "Height mm"},
                "label": {**_str, "description": "Object name"},
            },
            ["radius", "height"],
        ),
        _handle_create_cylinder,
        workbench="Part",
    )
    registry.register(
        "create_sphere",
        _make_schema(
            "create_sphere",
            "Create a sphere (Part::Sphere).",
            {
                "radius": {**_num, "description": "Radius mm"},
                "label": {**_str, "description": "Object name"},
            },
            ["radius"],
        ),
        _handle_create_sphere,
        workbench="Part",
    )
    registry.register(
        "create_cone",
        _make_schema(
            "create_cone",
            "Create a cone (Part::Cone).",
            {
                "radius1": {**_num, "description": "Base radius mm"},
                "radius2": {**_num, "description": "Top radius mm (0 = pointed)"},
                "height": {**_num, "description": "Height mm"},
                "label": {**_str, "description": "Object name"},
            },
            ["radius1", "radius2", "height"],
        ),
        _handle_create_cone,
        workbench="Part",
    )
    registry.register(
        "boolean_union",
        _make_schema(
            "boolean_union",
            "Fuse two shapes (Part::Fuse).",
            {
                "base": {**_str, "description": "Base object label"},
                "tool": {**_str, "description": "Tool object label"},
            },
            ["base", "tool"],
        ),
        lambda a: _handle_boolean(a, "union"),
        workbench="Part",
    )
    registry.register(
        "boolean_cut",
        _make_schema(
            "boolean_cut",
            "Subtract tool from base (Part::Cut).",
            {
                "base": {**_str, "description": "Base object label"},
                "tool": {**_str, "description": "Tool object label"},
            },
            ["base", "tool"],
        ),
        lambda a: _handle_boolean(a, "cut"),
        workbench="Part",
    )
    registry.register(
        "boolean_common",
        _make_schema(
            "boolean_common",
            "Intersection of two shapes (Part::Common).",
            {
                "base": {**_str, "description": "Base object label"},
                "tool": {**_str, "description": "Tool object label"},
            },
            ["base", "tool"],
        ),
        lambda a: _handle_boolean(a, "common"),
        workbench="Part",
    )
