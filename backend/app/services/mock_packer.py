"""Deterministic Mock Packing Engine (Stub/Dummy Handler).

Provides a deterministic, high-speed, non-overlapping 3D placement algorithm
for end-to-end infrastructure stabilization before the mathematical solver runs.
"""

from typing import List, Dict, Optional, Tuple, Any
import uuid
from datetime import datetime, timezone

from app.core.models import (
    RunResult,
    RunStatus,
    Container,
    PlacedBox,
    UnplacedCarton,
    LoadMetrics,
    UnplacedReason,
    PackingListRow,
    Posture,
    Layer,
    LayerBox,
    ShipmentType,
    RunOptions,
)
from app.core.database import Item as DBItem, Container as DBContainer

COLOR_PALETTE = [
    "#3b82f6",  # Blue
    "#10b981",  # Emerald
    "#f59e0b",  # Amber
    "#8b5cf6",  # Purple
    "#ec4899",  # Pink
    "#06b6d4",  # Cyan
    "#ef4444",  # Red
    "#84cc16",  # Lime
    "#14b8a6",  # Teal
    "#f97316",  # Orange
]


def run_deterministic_mock_pack(
    container: DBContainer | Container,
    packing_rows: List[PackingListRow],
    item_lookup: Dict[str, Any],
    options: Optional[RunOptions] = None,
    run_id: Optional[str] = None,
) -> RunResult:
    """Deterministically places cartons inside the container using a 3D grid layout.
    
    Coordinates follow the Logistics Convention:
      - X in [0, L]: Container length axis (door to rear)
      - Y in [0, W]: Container width axis (left to right wall)
      - Z in [0, H]: Container height axis (floor to ceiling)
    """
    if run_id is None:
        run_id = str(uuid.uuid4())

    L = float(container.internal_length_cm)
    W = float(container.internal_width_cm)
    H = float(container.internal_height_cm)
    W_max = float(container.max_weight_kg)
    container_vol = L * W * H if (L * W * H) > 0 else 1.0

    gap = float(options.tolerance_gap_cm) if options and options.tolerance_gap_cm is not None else 0.5

    # Determine unique customers and customer sequences
    customer_codes: List[str] = []
    for r in packing_rows:
        if r.customer_code and r.customer_code not in customer_codes:
            customer_codes.append(r.customer_code)
    
    shipment_type = ShipmentType.LCL if len(customer_codes) > 1 else ShipmentType.FCL
    customer_seq_map = {code: idx + 1 for idx, code in enumerate(customer_codes)}

    # Expand rows into individual cartons
    carton_units: List[Dict[str, Any]] = []
    unit_id = 0

    for row in packing_rows:
        item = item_lookup.get(row.item_id)
        
        # Dimensions & physical properties fallback
        l_cm = float(item.length_cm) if item and getattr(item, 'length_cm', None) else 40.0
        w_cm = float(item.width_cm) if item and getattr(item, 'width_cm', None) else 30.0
        h_cm = float(item.height_cm) if item and getattr(item, 'height_cm', None) else 25.0
        wt_kg = float(item.weight_kg) if item and getattr(item, 'weight_kg', None) else 10.0
        this_way_up = bool(item.this_way_up) if item and hasattr(item, 'this_way_up') else True
        desc = row.description or (item.description if item and getattr(item, 'description', None) else row.item_id)

        c_seq = customer_seq_map.get(row.customer_code, 1) if row.customer_code else 1

        for _ in range(row.qty_cartons):
            unit_id += 1
            carton_units.append({
                "box_id": f"BOX-{row.item_id}-{unit_id:04d}",
                "item_id": row.item_id,
                "po_no": row.po_no,
                "customer_code": row.customer_code,
                "customer_sequence": c_seq,
                "description": desc,
                "length_cm": l_cm,
                "width_cm": w_cm,
                "height_cm": h_cm,
                "weight_kg": wt_kg,
                "this_way_up": this_way_up,
            })

    # Sort cartons deterministically:
    # 1. Customer sequence (for LCL separation)
    # 2. Heavier/larger cartons first for base stability
    carton_units.sort(key=lambda c: (
        c["customer_sequence"],
        -c["weight_kg"],
        -(c["length_cm"] * c["width_cm"] * c["height_cm"]),
        c["item_id"],
    ))

    placed_boxes: List[PlacedBox] = []
    unplaced_cartons: List[UnplacedCarton] = []

    cur_x = 0.0
    cur_y = 0.0
    cur_z = 0.0
    row_max_l = 0.0
    tier_max_h = 0.0
    used_weight = 0.0

    step_counter = 0

    for carton in carton_units:
        box_l = carton["length_cm"]
        box_w = carton["width_cm"]
        box_h = carton["height_cm"]
        box_wt = carton["weight_kg"]

        # Check single carton boundary compatibility
        if box_l > L or box_w > W or box_h > H:
            unplaced_cartons.append(UnplacedCarton(
                box_id=carton["box_id"],
                item_id=carton["item_id"],
                po_no=carton["po_no"],
                customer_code=carton["customer_code"],
                customer_sequence=carton["customer_sequence"],
                reason=UnplacedReason.NO_SPACE,
                length_cm=box_l,
                width_cm=box_w,
                height_cm=box_h,
                weight_kg=box_wt,
            ))
            continue

        # Check total payload weight limit
        if used_weight + box_wt > W_max:
            unplaced_cartons.append(UnplacedCarton(
                box_id=carton["box_id"],
                item_id=carton["item_id"],
                po_no=carton["po_no"],
                customer_code=carton["customer_code"],
                customer_sequence=carton["customer_sequence"],
                reason=UnplacedReason.NO_SPACE,
                length_cm=box_l,
                width_cm=box_w,
                height_cm=box_h,
                weight_kg=box_wt,
            ))
            continue

        # Placement fit check along Y (Width)
        if cur_y + box_w > W:
            # Wrap to next row along X (Length)
            cur_y = 0.0
            cur_x += row_max_l + gap
            row_max_l = 0.0

        # Placement fit check along X (Length)
        if cur_x + box_l > L:
            # Wrap to next tier along Z (Height)
            cur_x = 0.0
            cur_y = 0.0
            cur_z += tier_max_h + gap
            row_max_l = 0.0
            tier_max_h = 0.0

        # Placement fit check along Z (Height)
        if cur_z + box_h > H:
            # Container volume exhausted
            unplaced_cartons.append(UnplacedCarton(
                box_id=carton["box_id"],
                item_id=carton["item_id"],
                po_no=carton["po_no"],
                customer_code=carton["customer_code"],
                customer_sequence=carton["customer_sequence"],
                reason=UnplacedReason.NO_SPACE,
                length_cm=box_l,
                width_cm=box_w,
                height_cm=box_h,
                weight_kg=box_wt,
            ))
            continue

        # Placed successfully
        step_counter += 1
        color_idx = (carton["customer_sequence"] - 1) % len(COLOR_PALETTE)
        box_color = COLOR_PALETTE[color_idx]

        placed_box = PlacedBox(
            box_id=carton["box_id"],
            item_id=carton["item_id"],
            po_no=carton["po_no"],
            customer_code=carton["customer_code"],
            customer_sequence=carton["customer_sequence"],
            description=carton["description"],
            length_cm=box_l,
            width_cm=box_w,
            height_cm=box_h,
            weight_kg=box_wt,
            this_way_up=carton["this_way_up"],
            permitted_postures=[Posture.LWH],
            inflated_length=box_l,
            inflated_width=box_w,
            inflated_height=box_h,
            x=round(cur_x, 2),
            y=round(cur_y, 2),
            z=round(cur_z, 2),
            posture=Posture.LWH,
            actual_length=box_l,
            actual_width=box_w,
            actual_height=box_h,
            step_index=step_counter,
            color=box_color,
        )
        placed_boxes.append(placed_box)

        # Advance coordinates
        used_weight += box_wt
        cur_y += box_w + gap
        row_max_l = max(row_max_l, box_l)
        tier_max_h = max(tier_max_h, box_h)

    # Compute exact metrics
    placed_vol = sum(b.actual_length * b.actual_width * b.actual_height for b in placed_boxes)
    fill_rate = round(placed_vol / container_vol, 4)
    weight_util = round(used_weight / W_max, 4) if W_max > 0 else 0.0

    if used_weight > 0:
        cog_x = round(sum((b.x + b.actual_length / 2.0) * b.weight_kg for b in placed_boxes) / used_weight, 2)
        cog_y = round(sum((b.y + b.actual_width / 2.0) * b.weight_kg for b in placed_boxes) / used_weight, 2)
        cog_z = round(sum((b.z + b.actual_height / 2.0) * b.weight_kg for b in placed_boxes) / used_weight, 2)
    else:
        cog_x, cog_y, cog_z = round(L / 2.0, 2), round(W / 2.0, 2), round(H / 2.0, 2)

    metrics = LoadMetrics(
        placed_count=len(placed_boxes),
        unplaced_count=len(unplaced_cartons),
        total_cartons=len(placed_boxes) + len(unplaced_cartons),
        fill_rate=fill_rate,
        used_weight_kg=round(used_weight, 2),
        max_weight_kg=W_max,
        weight_utilization=weight_util,
        cog_x=cog_x,
        cog_y=cog_y,
        cog_z=cog_z,
        cog_deviation_xy=0.0,
        cog_deviation_z=0.0,
    )

    # Construct Layer breakdowns
    layers: List[Layer] = []
    if placed_boxes:
        # Group by Z slices
        max_z = max(b.z + b.actual_height for b in placed_boxes)
        slice_height = 50.0
        num_slices = max(1, int(max_z / slice_height) + 1)

        for s in range(num_slices):
            z_min = s * slice_height
            z_max = (s + 1) * slice_height
            slice_boxes = [
                LayerBox(
                    box_id=b.box_id,
                    item_id=b.item_id,
                    x=b.x,
                    y=b.y,
                    z=b.z,
                    length=b.actual_length,
                    width=b.actual_width,
                    height=b.actual_height,
                    posture=b.posture,
                    customer_sequence=b.customer_sequence,
                    step_index=b.step_index,
                    color=b.color,
                )
                for b in placed_boxes
                if b.z < z_max and (b.z + b.actual_height) > z_min
            ]
            if slice_boxes:
                layers.append(Layer(z_min=round(z_min, 1), z_max=round(z_max, 1), boxes=slice_boxes))

    # Construct Container Model
    container_model = Container(
        id=container.id,
        container_type=container.container_type,
        internal_length_cm=L,
        internal_width_cm=W,
        internal_height_cm=H,
        max_weight_kg=W_max,
        created_at=getattr(container, 'created_at', datetime.now(timezone.utc)),
        updated_at=getattr(container, 'updated_at', datetime.now(timezone.utc)),
    )

    return RunResult(
        run_id=run_id,
        status=RunStatus.COMPLETED,
        container=container_model,
        metrics=metrics,
        placed_boxes=placed_boxes,
        unplaced_cartons=unplaced_cartons,
        layers=layers,
        created_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        error_message=None,
        options=options,
    )
