"""Sketcher workbench tools — REQ-008. All FreeCAD imports lazy (REQ-019)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from freecad_ai.registry import ToolRegistry

_VALID_PLANES = {"XY", "XZ", "YZ"}

_PLANE_NORMAL = {
    "XY": (0, 0, 1),
    "XZ": (0, 1, 0),
    "YZ": (1, 0, 0),
}


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


def _get_sketch(label: str):
    import FreeCAD  # lazy

    objs = FreeCAD.ActiveDocument.getObjectsByLabel(label)
    if not objs:
        return None, {"error": "execution", "message": f"Sketch '{label}' not found"}
    return objs[0], None


def _handle_create_sketch(args: dict) -> dict:
    import FreeCAD  # lazy

    plane = args.get("plane", "XY").upper()
    if plane not in _VALID_PLANES:
        return {
            "error": "validation",
            "field": "plane",
            "reason": f"must be one of {sorted(_VALID_PLANES)}",
        }

    body_label = args["body_label"]
    doc = FreeCAD.ActiveDocument
    bodies = doc.getObjectsByLabel(body_label)
    if not bodies:
        return {"error": "execution", "message": f"Body '{body_label}' not found"}

    body = bodies[0]
    label = args.get("label", "Sketch")
    sketch = body.newObject("Sketcher::SketchObject", label)

    nx, ny, nz = _PLANE_NORMAL[plane]
    sketch.AttachmentOffset = None  # placeholder — real placement set by FreeCAD
    sketch.MapReversed = False
    sketch.MapPathParameter = 0.0
    doc.recompute()
    return {"label": sketch.Label, "plane": plane}


def _handle_add_line(args: dict) -> dict:
    import Part  # lazy

    sketch, err = _get_sketch(args["sketch_label"])
    if err:
        return err
    line = Part.LineSegment(
        Part.Vector(args["x1"], args["y1"], 0),
        Part.Vector(args["x2"], args["y2"], 0),
    )
    idx = sketch.addGeometry(line, False)
    return {"geometry_index": idx}


def _handle_add_circle(args: dict) -> dict:
    import Part  # lazy

    radius = args["radius"]
    if radius <= 0:
        return {"error": "validation", "field": "radius", "reason": "must be > 0"}
    sketch, err = _get_sketch(args["sketch_label"])
    if err:
        return err
    circle = Part.Circle(Part.Vector(args["cx"], args["cy"], 0), Part.Vector(0, 0, 1), radius)
    idx = sketch.addGeometry(circle, False)
    return {"geometry_index": idx}


def _handle_add_arc(args: dict) -> dict:
    import Part  # lazy

    sketch, err = _get_sketch(args["sketch_label"])
    if err:
        return err
    import math

    arc = Part.ArcOfCircle(
        Part.Circle(Part.Vector(args["cx"], args["cy"], 0), Part.Vector(0, 0, 1), args["radius"]),
        math.radians(args["start_angle"]),
        math.radians(args["end_angle"]),
    )
    idx = sketch.addGeometry(arc, False)
    return {"geometry_index": idx}


def _handle_add_rectangle(args: dict) -> dict:
    import Part  # lazy

    sketch, err = _get_sketch(args["sketch_label"])
    if err:
        return err
    x, y, w, h = args["x"], args["y"], args["width"], args["height"]
    lines = [
        Part.LineSegment(Part.Vector(x, y, 0), Part.Vector(x + w, y, 0)),
        Part.LineSegment(Part.Vector(x + w, y, 0), Part.Vector(x + w, y + h, 0)),
        Part.LineSegment(Part.Vector(x + w, y + h, 0), Part.Vector(x, y + h, 0)),
        Part.LineSegment(Part.Vector(x, y + h, 0), Part.Vector(x, y, 0)),
    ]
    indices = [sketch.addGeometry(ln, False) for ln in lines]
    return {"geometry_indices": indices}


def _handle_constrain_distance(args: dict) -> dict:
    import Sketcher  # lazy

    sketch, err = _get_sketch(args["sketch_label"])
    if err:
        return err
    c = Sketcher.Constraint("Distance", args["geometry_index"], args["distance"])
    idx = sketch.addConstraint(c)
    return {"constraint_index": idx}


def _handle_constrain_radius(args: dict) -> dict:
    import Sketcher  # lazy

    sketch, err = _get_sketch(args["sketch_label"])
    if err:
        return err
    c = Sketcher.Constraint("Radius", args["geometry_index"], args["radius"])
    idx = sketch.addConstraint(c)
    return {"constraint_index": idx}


def _handle_constrain_coincident(args: dict) -> dict:
    import Sketcher  # lazy

    sketch, err = _get_sketch(args["sketch_label"])
    if err:
        return err
    c = Sketcher.Constraint(
        "Coincident",
        args["geo_index1"],
        args["point_index1"],
        args["geo_index2"],
        args["point_index2"],
    )
    idx = sketch.addConstraint(c)
    return {"constraint_index": idx}


def register_tools(registry: ToolRegistry) -> None:
    registry.register(
        "create_sketch",
        _schema(
            "create_sketch",
            "Create a new constrained sketch in a PartDesign Body.",
            {
                "body_label": {**_S, "description": "Parent Body label"},
                "plane": {**_S, "description": "Attachment plane: XY, XZ, or YZ"},
                "label": {**_S, "description": "Sketch name (default: Sketch)"},
            },
            ["body_label"],
        ),
        _handle_create_sketch,
        workbench="Sketcher",
    )
    registry.register(
        "sketch_add_line",
        _schema(
            "sketch_add_line",
            "Add a line segment to a sketch.",
            {
                "sketch_label": {**_S, "description": "Target sketch label"},
                "x1": {**_N, "description": "Start X mm"},
                "y1": {**_N, "description": "Start Y mm"},
                "x2": {**_N, "description": "End X mm"},
                "y2": {**_N, "description": "End Y mm"},
            },
            ["sketch_label", "x1", "y1", "x2", "y2"],
        ),
        _handle_add_line,
        workbench="Sketcher",
    )
    registry.register(
        "sketch_add_circle",
        _schema(
            "sketch_add_circle",
            "Add a circle to a sketch.",
            {
                "sketch_label": {**_S, "description": "Target sketch label"},
                "cx": {**_N, "description": "Centre X mm"},
                "cy": {**_N, "description": "Centre Y mm"},
                "radius": {**_N, "description": "Radius mm"},
            },
            ["sketch_label", "cx", "cy", "radius"],
        ),
        _handle_add_circle,
        workbench="Sketcher",
    )
    registry.register(
        "sketch_add_arc",
        _schema(
            "sketch_add_arc",
            "Add an arc to a sketch.",
            {
                "sketch_label": {**_S, "description": "Target sketch label"},
                "cx": {**_N, "description": "Centre X mm"},
                "cy": {**_N, "description": "Centre Y mm"},
                "radius": {**_N, "description": "Radius mm"},
                "start_angle": {**_N, "description": "Start angle degrees"},
                "end_angle": {**_N, "description": "End angle degrees"},
            },
            ["sketch_label", "cx", "cy", "radius", "start_angle", "end_angle"],
        ),
        _handle_add_arc,
        workbench="Sketcher",
    )
    registry.register(
        "sketch_add_rectangle",
        _schema(
            "sketch_add_rectangle",
            "Add a rectangle (4 lines) to a sketch.",
            {
                "sketch_label": {**_S, "description": "Target sketch label"},
                "x": {**_N, "description": "Bottom-left X mm"},
                "y": {**_N, "description": "Bottom-left Y mm"},
                "width": {**_N, "description": "Width mm"},
                "height": {**_N, "description": "Height mm"},
            },
            ["sketch_label", "x", "y", "width", "height"],
        ),
        _handle_add_rectangle,
        workbench="Sketcher",
    )
    registry.register(
        "sketch_constrain_distance",
        _schema(
            "sketch_constrain_distance",
            "Apply a distance constraint to a geometry.",
            {
                "sketch_label": {**_S, "description": "Target sketch label"},
                "geometry_index": {**_I, "description": "Geometry index from add call"},
                "distance": {**_N, "description": "Distance mm"},
            },
            ["sketch_label", "geometry_index", "distance"],
        ),
        _handle_constrain_distance,
        workbench="Sketcher",
    )
    registry.register(
        "sketch_constrain_radius",
        _schema(
            "sketch_constrain_radius",
            "Apply a radius constraint to a circle or arc.",
            {
                "sketch_label": {**_S, "description": "Target sketch label"},
                "geometry_index": {**_I, "description": "Circle/arc geometry index"},
                "radius": {**_N, "description": "Radius mm"},
            },
            ["sketch_label", "geometry_index", "radius"],
        ),
        _handle_constrain_radius,
        workbench="Sketcher",
    )
    registry.register(
        "sketch_constrain_coincident",
        _schema(
            "sketch_constrain_coincident",
            "Constrain two points to be coincident.",
            {
                "sketch_label": {**_S, "description": "Target sketch label"},
                "geo_index1": {**_I, "description": "First geometry index"},
                "point_index1": {**_I, "description": "Point on first geometry (1=start, 2=end)"},
                "geo_index2": {**_I, "description": "Second geometry index"},
                "point_index2": {**_I, "description": "Point on second geometry"},
            },
            ["sketch_label", "geo_index1", "point_index1", "geo_index2", "point_index2"],
        ),
        _handle_constrain_coincident,
        workbench="Sketcher",
    )
