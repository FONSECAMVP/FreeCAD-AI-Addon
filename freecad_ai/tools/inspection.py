"""Model inspection tools — REQ-009. All FreeCAD imports lazy (REQ-019)."""

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
            "parameters": {"type": "object", "properties": properties, "required": required},
        },
    }


def _handle_list_objects(args: dict) -> dict:
    import FreeCAD  # lazy

    doc = FreeCAD.ActiveDocument
    return {"objects": [{"label": o.Label, "type": o.TypeId} for o in doc.Objects]}


def _handle_get_object_properties(args: dict) -> dict:
    import FreeCAD  # lazy

    doc = FreeCAD.ActiveDocument
    label = args["label"]
    objs = doc.getObjectsByLabel(label)
    if not objs:
        return {"error": "execution", "message": f"Object '{label}' not found"}
    obj = objs[0]
    props = {}
    for prop in obj.PropertiesList:
        try:
            props[prop] = str(getattr(obj, prop))
        except Exception:
            props[prop] = "<unreadable>"
    return {"label": obj.Label, "type": obj.TypeId, "properties": props}


def _handle_get_bounding_box(args: dict) -> dict:
    import FreeCAD  # lazy

    doc = FreeCAD.ActiveDocument
    label = args["label"]
    objs = doc.getObjectsByLabel(label)
    if not objs:
        return {"error": "execution", "message": f"Object '{label}' not found"}
    obj = objs[0]
    try:
        bb = obj.Shape.BoundBox
        return {
            "label": obj.Label,
            "dimensions_mm": {
                "length_x": round(bb.XLength, 3),
                "width_y": round(bb.YLength, 3),
                "height_z": round(bb.ZLength, 3),
            },
            "bounds_mm": {
                "x": [round(bb.XMin, 3), round(bb.XMax, 3)],
                "y": [round(bb.YMin, 3), round(bb.YMax, 3)],
                "z": [round(bb.ZMin, 3), round(bb.ZMax, 3)],
            },
        }
    except Exception as exc:
        return {"error": "execution", "message": f"Could not read bounding box: {exc}"}


def _handle_get_selection(args: dict) -> dict:
    import FreeCADGui  # lazy

    sel = FreeCADGui.Selection.getSelection()
    return {"selection": [{"label": o.Label, "type": o.TypeId} for o in sel]}


def register_tools(registry: ToolRegistry) -> None:
    registry.register(
        "list_objects",
        _make_schema("list_objects", "List all objects in the active document.", {}, []),
        _handle_list_objects,
        workbench="Part",
    )
    registry.register(
        "get_object_properties",
        _make_schema(
            "get_object_properties",
            "Get all properties of a named object.",
            {"label": {"type": "string", "description": "Object label"}},
            ["label"],
        ),
        _handle_get_object_properties,
        workbench="Part",
    )
    registry.register(
        "get_bounding_box",
        _make_schema(
            "get_bounding_box",
            "Get the bounding box dimensions (length, width, height in mm) of a named object.",
            {"label": {"type": "string", "description": "Object label"}},
            ["label"],
        ),
        _handle_get_bounding_box,
        workbench="Part",
    )
    registry.register(
        "get_selection",
        _make_schema("get_selection", "Get the currently selected objects.", {}, []),
        _handle_get_selection,
        workbench="Part",
    )
