from typing import List
from collections import defaultdict
from app.solver.parsing import Box
from app.solver.block_generation import Block
from app.config import get_settings
from app.solver.utils import get_unit_item_id


def initial_sort(boxes: List[Box], shipment_type: str) -> List[Box]:
    """Sort boxes: Customer_Sequence asc (for LCL), Item_ID asc,
    Volume desc (primary), Weight desc (secondary).

    Volume is the primary criterion to maximize container fill rate (the primary
    optimization objective of 3D-CLP); weight serves as a tiebreaker.
    """
    def sort_key(box: Box):
        keys = []

        if shipment_type == "LCL":
            keys.append(box.customer_sequence)

        # Volume FIRST — larger volume cartons placed earlier for solid fill rate.
        keys.append(-box.length_cm * box.width_cm * box.height_cm)
        # Weight second — tiebreak: heavier before lighter among same-volume boxes.
        keys.append(-box.weight_kg)
        keys.append(box.item_id or "")

        return tuple(keys)

    return sorted(boxes, key=sort_key)


def resort_after_blocks(units: List[Block], shipment_type: str) -> List[Block]:
    """Re-sort blocks after block generation per Section 5.5 with Item Affinity Clustering.

    For LCL: Group by Customer_Sequence DESC first (last-to-unload goes deepest/rear).
    Within each customer (or FCL):
      - Group all units of the same item_id together so leftover singletons are placed
        adjacent to the blocks of the same item rather than scattered across the container.
      - Items with larger maximum unit volume are sequenced earlier to form solid foundations.
      - Within each item_id group, sort by volume desc (primary), weight desc (secondary).

    TRADE-OFF NOTE & INVESTIGATION FINDINGS:
    Sorting by weight-primary vs. volume-primary presents an inherent trade-off on certain
    item mixes:
      - Weight-primary sorting prioritizes small-but-heavy boxes early, which can allow more
        individual cartons to be packed (+4 cartons in sample furniture mixes) by packing smaller
        units before space is filled, but at the expense of volume fill rate (larger, lighter boxes
        are pushed later into the queue and crowded out, leaving significant container volume unutilized).
      - Volume-primary sorting directly optimizes for container fill rate / volume utilization,
        which is the stated primary objective of this project (Section 5.3.2, 5.5 and README).
      - In addition, item-affinity clustering groups leftover singletons immediately behind their parent
        blocks, which keeps same-item cartons physically adjacent but can fragment remaining space
        ahead of subsequent items' large blocks.

    TODO:
    Expose optimization goal via RunOptions (e.g., `optimize_for: Literal["volume", "carton_count"]`)
    rather than a fixed default, allowing operators to choose between maximum volume fill rate
    and maximum carton count / service level depending on the shipment profile.
    Default: volume-primary sorting to maximize fill rate.
    """
    group_max_vol = defaultdict(float)
    group_tot_vol = defaultdict(float)
    group_max_wt = defaultdict(float)
    group_tot_wt = defaultdict(float)

    for unit in units:
        cust_seq = getattr(unit, 'customer_sequence', 0) if shipment_type == "LCL" else 0
        item_id = get_unit_item_id(unit)
        wt = unit.weight_kg
        vol = unit.length_cm * unit.width_cm * unit.height_cm
        key = (cust_seq, item_id)
        if vol > group_max_vol[key]:
            group_max_vol[key] = vol
        group_tot_vol[key] += vol
        if wt > group_max_wt[key]:
            group_max_wt[key] = wt
        group_tot_wt[key] += wt

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
            # Cluster by item: items with larger blocks placed earlier for stable foundation
            keys.append(-group_max_vol[grp_key])
            keys.append(-group_tot_vol[grp_key])
            keys.append(-group_max_wt[grp_key])
            keys.append(-group_tot_wt[grp_key])
            keys.append(item_id)

        # Within the item (or for items with no item_id):
        # volume desc (primary) → weight desc (secondary)
        keys.append(-vol)
        keys.append(-wt)

        return tuple(keys)

    return sorted(units, key=sort_key)