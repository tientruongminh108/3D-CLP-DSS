"""Shared utility helpers for the solver package.

Kept intentionally small: only helpers that are used by more than one
solver module belong here.  Business logic lives in its own module.
"""


def get_unit_item_id(unit) -> str:
    """Extract item_id whether *unit* is a :class:`Block` or a :class:`Box`.

    Both types can appear in the mixed ``all_units`` list that flows through
    the placement pipeline.  Blocks store the representative item_id on their
    first box; plain Boxes carry it directly.
    """
    if hasattr(unit, 'boxes') and unit.boxes:
        return unit.boxes[0].item_id or ""
    return getattr(unit, 'item_id', "") or ""
