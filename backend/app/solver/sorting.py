from typing import List
from collections import defaultdict
from app.solver.parsing import Box
from app.solver.block_generation import Block
from app.config import get_settings
from app.solver.utils import get_unit_item_id


def initial_sort(boxes: List[Box], shipment_type: str) -> List[Box]:
    """Sort boxes per Section 5.5: Customer_Sequence asc, Stacking_Group asc, Item_ID,
    Weight desc (primary), Volume desc (secondary).

    Weight is the primary criterion so heaviest boxes are always attempted first;
    volume acts as a tiebreaker to preserve block compactness for same-weight units.
    """
    def sort_key(box: Box):
        keys = []

        if shipment_type == "LCL":
            keys.append(box.customer_sequence)

        keys.append(box.stacking_group)
        keys.append(box.item_id or "")
        # Weight FIRST — heaviest boxes placed first.
        keys.append(-box.weight_kg)
        # Volume second — tiebreak: larger volume (bulk) before flat/light.
        keys.append(-box.length_cm * box.width_cm * box.height_cm)

        return tuple(keys)

    return sorted(boxes, key=sort_key)


def resort_after_blocks(units: List[Block], shipment_type: str) -> List[Block]:
    """Re-sort blocks after block generation per Section 5.5 with Item Affinity Clustering.

    For LCL: Group by Customer_Sequence DESC first (last-to-unload goes deepest/rear).
    Within each customer (or FCL):
      - Group all units of the same item_id together so leftover singletons are placed
        adjacent to the blocks of the same item rather than scattered across the container.
      - Items with larger maximum unit weight are sequenced earlier to place heavy cargo
        first and reserve gap space for flat/light boxes.
      - Within each item_id group, sort by weight desc (primary), volume desc (secondary).
    """
    # Precompute max unit weight and total weight per (customer_sequence, item_id)
    # (volume retained as secondary grouping tiebreaker)
    group_max_wt = defaultdict(float)
    group_tot_wt = defaultdict(float)
    group_max_vol = defaultdict(float)
    group_tot_vol = defaultdict(float)

    for unit in units:
        cust_seq = getattr(unit, 'customer_sequence', 0) if shipment_type == "LCL" else 0
        item_id = get_unit_item_id(unit)
        wt = unit.weight_kg
        vol = unit.length_cm * unit.width_cm * unit.height_cm
        key = (cust_seq, item_id)
        if wt > group_max_wt[key]:
            group_max_wt[key] = wt
        group_tot_wt[key] += wt
        if vol > group_max_vol[key]:
            group_max_vol[key] = vol
        group_tot_vol[key] += vol

    def sort_key(unit):
        cust_seq = getattr(unit, 'customer_sequence', 0) if shipment_type == "LCL" else 0
        item_id = get_unit_item_id(unit)
        wt = unit.weight_kg
        vol = unit.length_cm * unit.width_cm * unit.height_cm
        grp_key = (cust_seq, item_id)

        keys = []
        if shipment_type == "LCL":
            # Descending: last customer placed first/deepest
            keys.append(-cust_seq)

        if item_id:
            # Cluster by item: items with heavier blocks placed first.
            # Weight is the primary grouping criterion; volume is the tiebreaker
            # so compact heavy items still form solid foundations.
            keys.append(-group_max_wt[grp_key])
            keys.append(-group_tot_wt[grp_key])
            keys.append(-group_max_vol[grp_key])
            keys.append(-group_tot_vol[grp_key])
            keys.append(item_id)

        # Within the item (or for items with no item_id):
        # weight desc (primary) → volume desc (secondary)
        keys.append(-wt)
        keys.append(-vol)

        return tuple(keys)

    return sorted(units, key=sort_key)