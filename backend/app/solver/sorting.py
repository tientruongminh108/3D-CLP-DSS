from typing import List
from app.solver.parsing import Box
from app.solver.block_generation import Block
from app.config import get_settings


def initial_sort(boxes: List[Box], shipment_type: str) -> List[Box]:
    """Sort boxes per Section 5.5: Customer_Sequence asc, Stacking_Group asc, Volume desc, Weight desc."""
    def sort_key(box: Box):
        keys = []

        if shipment_type == "LCL":
            keys.append(box.customer_sequence)

        keys.append(box.stacking_group)
        keys.append(-box.length_cm * box.width_cm * box.height_cm)
        keys.append(-box.weight_kg)

        return tuple(keys)

    return sorted(boxes, key=sort_key)


def resort_after_blocks(units: List[Block], shipment_type: str) -> List[Block]:
    """Re-sort blocks after block generation per Section 5.5.
    Blocks carry the most restrictive stacking_group, so we don't need Stacking_Group as a separate key.

    For FCL: Sort by Volume desc, Weight desc.
    For LCL: Sort by Customer_Sequence DESC first (last-to-unload goes deepest/rear),
             then Volume desc, Weight desc within the same customer.

    Descending customer_sequence for LCL means the algorithm places the
    last customer's cargo first (deepest in the container, nearest rear wall),
    which, combined with the LIFO constraint checker in constraints.py, prevents
    later-sequence cargo from blocking earlier-sequence cargo at the door.
    """
    def sort_key(unit):
        keys = []

        if shipment_type == "LCL":
            # Descending: last customer (highest sequence) placed first/deepest.
            keys.append(-unit.customer_sequence)

        keys.append(-unit.length_cm * unit.width_cm * unit.height_cm)
        keys.append(-unit.weight_kg)

        return tuple(keys)

    return sorted(units, key=sort_key)