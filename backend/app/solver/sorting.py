from typing import List
from collections import defaultdict
from app.solver.parsing import Box
from app.solver.block_generation import Block
from app.config import get_settings


def _get_unit_item_id(unit) -> str:
    """Helper to extract item_id whether unit is a Block or a Box."""
    if hasattr(unit, 'boxes') and unit.boxes:
        return unit.boxes[0].item_id or ""
    return getattr(unit, 'item_id', "") or ""


def initial_sort(boxes: List[Box], shipment_type: str) -> List[Box]:
    """Sort boxes per Section 5.5: Customer_Sequence asc, Stacking_Group asc, Item_ID, Volume desc, Weight desc."""
    def sort_key(box: Box):
        keys = []

        if shipment_type == "LCL":
            keys.append(box.customer_sequence)

        keys.append(box.stacking_group)
        keys.append(box.item_id or "")
        keys.append(-box.length_cm * box.width_cm * box.height_cm)
        keys.append(-box.weight_kg)

        return tuple(keys)

    return sorted(boxes, key=sort_key)


def resort_after_blocks(units: List[Block], shipment_type: str) -> List[Block]:
    """Re-sort blocks after block generation per Section 5.5 with Item Affinity Clustering.

    For LCL: Group by Customer_Sequence DESC first (last-to-unload goes deepest/rear).
    Within each customer (or FCL):
      - Group all units of the same item_id together so leftover singletons are placed
        adjacent to the blocks of the same item rather than scattered across the container.
      - Items with larger maximum unit volume are sequenced earlier to form solid foundations.
      - Within each item_id group, sort by unit volume desc, weight desc.
    """
    # Precompute max unit volume and total volume per (customer_sequence, item_id)
    group_max_vol = defaultdict(float)
    group_tot_vol = defaultdict(float)

    for unit in units:
        cust_seq = getattr(unit, 'customer_sequence', 0) if shipment_type == "LCL" else 0
        item_id = _get_unit_item_id(unit)
        vol = unit.length_cm * unit.width_cm * unit.height_cm
        key = (cust_seq, item_id)
        if vol > group_max_vol[key]:
            group_max_vol[key] = vol
        group_tot_vol[key] += vol

    def sort_key(unit):
        cust_seq = getattr(unit, 'customer_sequence', 0) if shipment_type == "LCL" else 0
        item_id = _get_unit_item_id(unit)
        vol = unit.length_cm * unit.width_cm * unit.height_cm
        grp_key = (cust_seq, item_id)

        keys = []
        if shipment_type == "LCL":
            # Descending: last customer placed first/deepest
            keys.append(-cust_seq)

        if item_id:
            # Cluster by item: items with larger blocks placed earlier
            keys.append(-group_max_vol[grp_key])
            keys.append(-group_tot_vol[grp_key])
            keys.append(item_id)

        # Within the item (or for items with no item_id): volume desc, weight desc
        keys.append(-vol)
        keys.append(-unit.weight_kg)

        return tuple(keys)

    return sorted(units, key=sort_key)