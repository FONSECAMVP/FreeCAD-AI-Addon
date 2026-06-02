"""Draft workbench tools — REQ-013. All FreeCAD/Draft imports lazy (REQ-019)."""

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
_A_PTS = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {"x": _N, "y": _N, "z": _N},
        "required": ["x", "y", "z"],
    },
}


def _vec(x: float, y: float, z: float):
    import FreeCAD  # lazy

    return FreeCAD.Vector(x, y, z)


def _get_obj(label: str):
    import FreeCAD  # lazy

    objs = FreeCAD.ActiveDocument.getObjectsByLabel(label)
    if not objs:
        return None, {"error": "execution", "message": f"Object '{label}' not found"}
    return objs[0], None


def _handle_draft_line(args: dict) -> dict:
    import Draft  # lazy

    obj = Draft.makeLine(
        _vec(args["x1"], args["y1"], args["z1"]),
        _vec(args["x2"], args["y2"], args["z2"]),
    )
    return {"label": obj.Label}


def _handle_draft_rectangle(args: dict) -> dict:
    import Draft  # lazy

    length, height = args["length"], args["height"]
    if length <= 0 or height <= 0:
        return {"error": "validation", "field": "length/height", "reason": "must be > 0"}
    obj = Draft.makeRectangle(length, height)
    return {"label": obj.Label}


def _handle_draft_circle(args: dict) -> dict:
    import Draft  # lazy

    radius = args["radius"]
    if radius <= 0:
        return {"error": "validation", "field": "radius", "reason": "must be > 0"}
    obj = Draft.makeCircle(radius)
    return {"label": obj.Label}


def _handle_draft_bspline(args: dict) -> dict:
    import Draft  # lazy

    points = args["points"]
    if len(points) < 2:
        return {"error": "validation", "field": "points", "reason": "need at least 2 points"}
    vecs = [_vec(p["x"], p["y"], p["z"]) for p in points]
    obj = Draft.makeBSpline(vecs)
    return {"label": obj.Label}


def _handle_draft_array(args: dict) -> dict:
    import Draft  # lazy

    count_x, count_y = args["count_x"], args["count_y"]
    if count_x < 1 or count_y < 1:
        return {"error": "validation", "field": "count_x/count_y", "reason": "must be >= 1"}
    obj, err = _get_obj(args["object_label"])
    if err:
        return err
    result = Draft.makeArray(
        obj,
        _vec(args["interval_x"], 0, 0),
        _vec(0, args["interval_y"], 0),
        count_x,
        count_y,
    )
    return {"label": result.Label}


def _handle_draft_move(args: dict) -> dict:
    import Draft  # lazy

    obj, err = _get_obj(args["object_label"])
    if err:
        return err
    Draft.move([obj], _vec(args["dx"], args["dy"], args["dz"]))
    return {"label": obj.Label, "moved": True}


def _handle_draft_rotate(args: dict) -> dict:
    import Draft  # lazy

    obj, err = _get_obj(args["object_label"])
    if err:
        return err
    Draft.rotate(
        [obj],
        args["angle"],
        _vec(args["cx"], args["cy"], args["cz"]),
        axis=_vec(0, 0, 1),
    )
    return {"label": obj.Label, "rotated": True}


def register_tools(registry: ToolRegistry) -> None:
    registry.register(
        "draft_line",
        _schema(
            "draft_line",
            "Draw a Draft line between two 3D points.",
            {"x1": _N, "y1": _N, "z1": _N, "x2": _N, "y2": _N, "z2": _N},
            ["x1", "y1", "z1", "x2", "y2", "z2"],
        ),
        _handle_draft_line,
        workbench="Draft",
    )
    registry.register(
        "draft_rectangle",
        _schema(
            "draft_rectangle",
            "Draw a Draft rectangle.",
            {
                "length": {**_N, "description": "Length mm"},
                "height": {**_N, "description": "Height mm"},
            },
            ["length", "height"],
        ),
        _handle_draft_rectangle,
        workbench="Draft",
    )
    registry.register(
        "draft_circle",
        _schema(
            "draft_circle",
            "Draw a Draft circle.",
            {"radius": {**_N, "description": "Radius mm"}},
            ["radius"],
        ),
        _handle_draft_circle,
        workbench="Draft",
    )
    registry.register(
        "draft_bspline",
        _schema(
            "draft_bspline",
            "Draw a BSpline through a list of 3D points.",
            {"points": {**_A_PTS, "description": "List of {x,y,z} point objects"}},
            ["points"],
        ),
        _handle_draft_bspline,
        workbench="Draft",
    )
    registry.register(
        "draft_array",
        _schema(
            "draft_array",
            "Create a rectangular array of an object.",
            {
                "object_label": {**_S, "description": "Object to array"},
                "interval_x": {**_N, "description": "Spacing in X mm"},
                "interval_y": {**_N, "description": "Spacing in Y mm"},
                "count_x": {**_I, "description": "Number of columns"},
                "count_y": {**_I, "description": "Number of rows"},
            },
            ["object_label", "interval_x", "interval_y", "count_x", "count_y"],
        ),
        _handle_draft_array,
        workbench="Draft",
    )
    registry.register(
        "draft_move",
        _schema(
            "draft_move",
            "Move an object by a displacement vector.",
            {
                "object_label": {**_S, "description": "Object to move"},
                "dx": {**_N, "description": "X displacement mm"},
                "dy": {**_N, "description": "Y displacement mm"},
                "dz": {**_N, "description": "Z displacement mm"},
            },
            ["object_label", "dx", "dy", "dz"],
        ),
        _handle_draft_move,
        workbench="Draft",
    )
    registry.register(
        "draft_rotate",
        _schema(
            "draft_rotate",
            "Rotate an object around a centre point (Z axis).",
            {
                "object_label": {**_S, "description": "Object to rotate"},
                "angle": {**_N, "description": "Rotation angle degrees"},
                "cx": {**_N, "description": "Centre X mm"},
                "cy": {**_N, "description": "Centre Y mm"},
                "cz": {**_N, "description": "Centre Z mm"},
            },
            ["object_label", "angle", "cx", "cy", "cz"],
        ),
        _handle_draft_rotate,
        workbench="Draft",
    )
