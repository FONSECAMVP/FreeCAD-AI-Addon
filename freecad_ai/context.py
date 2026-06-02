"""Document context injector — DES-009, REQ-005."""

from __future__ import annotations

_MAX_OBJECTS = 20
_MAX_LEN = 500


def build_context() -> str:
    try:
        import FreeCAD
        import FreeCADGui
    except ImportError:
        return "[Context]\nno active document\n"

    doc = FreeCAD.ActiveDocument
    if doc is None:
        return "[Context]\nno active document\n"

    objects = doc.Objects
    selected = FreeCADGui.Selection.getSelection()
    selected_labels = {o.Label for o in selected}

    # Selected first, then rest, capped at _MAX_OBJECTS
    ordered = [o for o in objects if o.Label in selected_labels]
    ordered += [o for o in objects if o.Label not in selected_labels]
    ordered = ordered[:_MAX_OBJECTS]

    obj_lines = ", ".join(f"{o.Label} ({o.TypeId})" for o in ordered)
    sel_line = ", ".join(selected_labels) if selected_labels else "none"

    ctx = (
        f"[Context]\n"
        f"Document: {doc.Name} ({len(objects)} objects)\n"
        f"Objects: {obj_lines}\n"
        f"Selection: {sel_line}\n"
    )

    if len(ctx) > _MAX_LEN:
        ctx = ctx[: _MAX_LEN - 3] + "..."

    return ctx
