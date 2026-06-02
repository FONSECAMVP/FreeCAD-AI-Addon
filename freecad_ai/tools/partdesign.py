"""PartDesign workbench tools — REQ-007. All FreeCAD imports lazy (REQ-019)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from freecad_ai.registry import ToolRegistry


def _schema(name: str, description: str, properties: dict, required: list) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required},
        },
    }


_N = {"type": "number"}
_S = {"type": "string"}
_A = {"type": "array", "items": {"type": "string"}}


def _handle_create_body(args: dict) -> dict:
    import FreeCAD  # lazy

    label = args.get("label", "Body")
    body = FreeCAD.ActiveDocument.addObject("PartDesign::Body", label)
    FreeCAD.ActiveDocument.recompute()
    return {"label": body.Label}


def _handle_pad_sketch(args: dict) -> dict:
    import FreeCAD  # lazy

    length = args["length"]
    if length <= 0:
        return {"error": "validation", "field": "length", "reason": "must be > 0"}

    sketch_label = args["sketch_label"]
    body_label = args["body_label"]
    doc = FreeCAD.ActiveDocument

    sketches = doc.getObjectsByLabel(sketch_label)
    if not sketches:
        return {"error": "execution", "message": f"Sketch '{sketch_label}' not found"}
    bodies = doc.getObjectsByLabel(body_label)
    if not bodies:
        return {"error": "execution", "message": f"Body '{body_label}' not found"}

    sketch, body = sketches[0], bodies[0]
    pad = body.newObject("PartDesign::Pad", "Pad")
    pad.Profile = sketch
    pad.Length = length
    doc.recompute()
    return {"label": pad.Label, "length": length}


def _handle_pocket_sketch(args: dict) -> dict:
    import FreeCAD  # lazy

    depth = args["depth"]
    if depth <= 0:
        return {"error": "validation", "field": "depth", "reason": "must be > 0"}

    sketch_label = args["sketch_label"]
    body_label = args["body_label"]
    doc = FreeCAD.ActiveDocument

    sketches = doc.getObjectsByLabel(sketch_label)
    if not sketches:
        return {"error": "execution", "message": f"Sketch '{sketch_label}' not found"}
    bodies = doc.getObjectsByLabel(body_label)
    if not bodies:
        return {"error": "execution", "message": f"Body '{body_label}' not found"}

    sketch, body = sketches[0], bodies[0]
    pocket = body.newObject("PartDesign::Pocket", "Pocket")
    pocket.Profile = sketch
    pocket.Length = depth
    doc.recompute()
    return {"label": pocket.Label, "depth": depth}


def _handle_add_fillet(args: dict) -> dict:
    import FreeCAD  # lazy

    radius = args["radius"]
    if radius <= 0:
        return {"error": "validation", "field": "radius", "reason": "must be > 0"}

    doc = FreeCAD.ActiveDocument
    bodies = doc.getObjectsByLabel(args["body_label"])
    features = doc.getObjectsByLabel(args["feature_label"])
    edges = args.get("edges", [])

    if not bodies:
        return {"error": "execution", "message": f"Body '{args['body_label']}' not found"}
    if not features:
        return {"error": "execution", "message": f"Feature '{args['feature_label']}' not found"}

    body, feature = bodies[0], features[0]
    fillet = body.newObject("PartDesign::Fillet", "Fillet")
    fillet.Base = (feature, edges)
    fillet.Radius = radius
    doc.recompute()
    return {"label": fillet.Label, "radius": radius}


def _handle_add_chamfer(args: dict) -> dict:
    import FreeCAD  # lazy

    size = args["size"]
    if size <= 0:
        return {"error": "validation", "field": "size", "reason": "must be > 0"}

    doc = FreeCAD.ActiveDocument
    bodies = doc.getObjectsByLabel(args["body_label"])
    features = doc.getObjectsByLabel(args["feature_label"])
    edges = args.get("edges", [])

    if not bodies:
        return {"error": "execution", "message": f"Body '{args['body_label']}' not found"}
    if not features:
        return {"error": "execution", "message": f"Feature '{args['feature_label']}' not found"}

    body, feature = bodies[0], features[0]
    chamfer = body.newObject("PartDesign::Chamfer", "Chamfer")
    chamfer.Base = (feature, edges)
    chamfer.Size = size
    doc.recompute()
    return {"label": chamfer.Label, "size": size}


def register_tools(registry: ToolRegistry) -> None:
    registry.register(
        "create_body",
        _schema(
            "create_body",
            "Create a new PartDesign Body.",
            {"label": {**_S, "description": "Body name (default: Body)"}},
            [],
        ),
        _handle_create_body,
        workbench="PartDesign",
    )
    registry.register(
        "pad_sketch",
        _schema(
            "pad_sketch",
            "Pad a sketch by a given length to create a solid.",
            {
                "sketch_label": {**_S, "description": "Label of the sketch to pad"},
                "body_label": {**_S, "description": "Label of the PartDesign Body"},
                "length": {**_N, "description": "Pad length in mm"},
                "label": {**_S, "description": "Feature name (default: Pad)"},
            },
            ["sketch_label", "body_label", "length"],
        ),
        _handle_pad_sketch,
        workbench="PartDesign",
    )
    registry.register(
        "pocket_sketch",
        _schema(
            "pocket_sketch",
            "Cut a pocket into a solid using a sketch.",
            {
                "sketch_label": {**_S, "description": "Label of the sketch"},
                "body_label": {**_S, "description": "Label of the PartDesign Body"},
                "depth": {**_N, "description": "Pocket depth in mm"},
                "label": {**_S, "description": "Feature name (default: Pocket)"},
            },
            ["sketch_label", "body_label", "depth"],
        ),
        _handle_pocket_sketch,
        workbench="PartDesign",
    )
    registry.register(
        "add_fillet",
        _schema(
            "add_fillet",
            "Round edges of a PartDesign feature.",
            {
                "feature_label": {**_S, "description": "Feature to fillet"},
                "body_label": {**_S, "description": "Parent Body label"},
                "radius": {**_N, "description": "Fillet radius in mm"},
                "edges": {**_A, "description": 'Edge names e.g. ["Edge1","Edge2"]'},
            },
            ["feature_label", "body_label", "radius"],
        ),
        _handle_add_fillet,
        workbench="PartDesign",
    )
    registry.register(
        "add_chamfer",
        _schema(
            "add_chamfer",
            "Chamfer edges of a PartDesign feature.",
            {
                "feature_label": {**_S, "description": "Feature to chamfer"},
                "body_label": {**_S, "description": "Parent Body label"},
                "size": {**_N, "description": "Chamfer size in mm"},
                "edges": {**_A, "description": 'Edge names e.g. ["Edge1"]'},
            },
            ["feature_label", "body_label", "size"],
        ),
        _handle_add_chamfer,
        workbench="PartDesign",
    )
