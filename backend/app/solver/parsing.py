import pandas as pd
import uuid
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass
from app.config import get_settings
from app.core.models import (
    PackingListRow,
    PackingListPreviewRow,
    PackingListPreview,
    ShipmentType,
    ItemBase,
    ContainerBase,
    Posture,
)
from app.core.exceptions import ValidationError
from app.solver.geometry import get_permitted_postures, Dimensions


@dataclass
class Box:
    box_id: str
    item_id: str
    po_no: str
    customer_code: Optional[str]
    customer_sequence: int
    length_cm: float
    width_cm: float
    height_cm: float
    weight_kg: float
    this_way_up: bool
    stacking_group: int
    max_load_bearing_kg: Optional[float]
    permitted_postures: List[Posture]
    inflated_length: float
    inflated_width: float
    inflated_height: float
    # Relative position within a block (for explode_blocks)
    rel_x: float = 0.0
    rel_y: float = 0.0
    rel_z: float = 0.0


@dataclass
class ContainerSpec:
    container_type: str
    internal_length_cm: float
    internal_width_cm: float
    internal_height_cm: float
    max_weight_kg: float
    usable_length: float
    usable_width: float
    usable_height: float


def parse_container_spec(df: pd.DataFrame, tolerance_gap: Optional[float] = None) -> ContainerSpec:
    required = [
        "Container_Type",
        "Internal_Length_cm",
        "Internal_Width_cm",
        "Internal_Height_cm",
        "Max_Weight_kg",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValidationError(f"Missing columns in container spec: {missing}")

    row = df.iloc[0]
    for col in required:
        val = row[col]
        if pd.isna(val):
            raise ValidationError(f"Container {col} cannot be empty")
        if col == "Container_Type":
            continue
        try:
            num_val = float(val)
            if num_val <= 0:
                raise ValidationError(f"Container {col} must be > 0")
        except (ValueError, TypeError):
            raise ValidationError(f"Container {col} must be a number > 0")

    settings = get_settings()
    gap = tolerance_gap if tolerance_gap is not None else settings.TOLERANCE_GAP_CM

    return ContainerSpec(
        container_type=str(row["Container_Type"]),
        internal_length_cm=float(row["Internal_Length_cm"]),
        internal_width_cm=float(row["Internal_Width_cm"]),
        internal_height_cm=float(row["Internal_Height_cm"]),
        max_weight_kg=float(row["Max_Weight_kg"]),
        usable_length=float(row["Internal_Length_cm"]) - 2 * gap,
        usable_width=float(row["Internal_Width_cm"]) - 2 * gap,
        usable_height=float(row["Internal_Height_cm"]),
    )


def parse_item_master(df: pd.DataFrame) -> Dict[str, ItemBase]:
    required = [
        "Item_ID",
        "Description",
        "Length_cm",
        "Width_cm",
        "Height_cm",
        "Weight_kg",
        "This_Way_Up",
        "Stacking_Group",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValidationError(f"Missing columns in item master: {missing}")

    items = {}
    for idx, row in df.iterrows():
        item_id = str(row["Item_ID"]).strip()
        if not item_id:
            raise ValidationError(f"Row {idx + 1}: Item_ID cannot be empty")

        for dim in ["Length_cm", "Width_cm", "Height_cm", "Weight_kg"]:
            if pd.isna(row[dim]) or row[dim] <= 0:
                raise ValidationError(f"Row {idx + 1}: {dim} must be > 0")

        stacking_group = int(row["Stacking_Group"])
        if stacking_group not in [1, 2]:
            raise ValidationError(f"Row {idx + 1}: Stacking_Group must be 1 or 2")

        this_way_up = bool(row["This_Way_Up"])
        if pd.isna(row["This_Way_Up"]):
            raise ValidationError(f"Row {idx + 1}: This_Way_Up must be boolean")

        max_load = None
        if "Max_Load_Bearing_kg" in df.columns and not pd.isna(row["Max_Load_Bearing_kg"]):
            max_load = float(row["Max_Load_Bearing_kg"])
            if max_load <= 0:
                raise ValidationError(f"Row {idx + 1}: Max_Load_Bearing_kg must be > 0")

        items[item_id] = ItemBase(
            item_id=item_id,
            description=str(row["Description"]),
            length_cm=float(row["Length_cm"]),
            width_cm=float(row["Width_cm"]),
            height_cm=float(row["Height_cm"]),
            weight_kg=float(row["Weight_kg"]),
            this_way_up=this_way_up,
            stacking_group=stacking_group,
            max_load_bearing_kg=max_load,
        )

    return items


def detect_shipment_type(packing_rows: List[PackingListRow]) -> Tuple[ShipmentType, int, Dict[str, int]]:
    customer_codes = [r.customer_code for r in packing_rows if r.customer_code]
    unique_customers = []
    seen = set()
    for c in customer_codes:
        if c not in seen:
            seen.add(c)
            unique_customers.append(c)

    if len(unique_customers) <= 1:
        return ShipmentType.FCL, 0, {}

    customer_sequence = {cust: i + 1 for i, cust in enumerate(unique_customers)}
    return ShipmentType.LCL, len(unique_customers), customer_sequence


def _check_item_fits_container(
    item: "ItemBase",
    container: "ContainerSpec",
    permitted: List,
) -> bool:
    """Return True if the item fits inside the container's usable interior in at least one posture."""
    from app.solver.geometry import Dimensions as Dims
    base = Dims(item.length_cm, item.width_cm, item.height_cm)
    cl, cw, ch = container.usable_length, container.usable_width, container.usable_height
    for posture in permitted:
        d = base.apply_posture(posture)
        if d.length <= cl and d.width <= cw and d.height <= ch:
            return True
    return False


def expand_packing_list(
    packing_rows: List[PackingListRow],
    items: Dict[str, ItemBase],
    container: ContainerSpec,
    customer_sequence: Dict[str, int],
    tolerance_gap: float,
) -> Tuple[List[Box], List[PackingListPreviewRow]]:
    boxes = []
    preview_rows = []

    # --- Issue 3: Fast-fail oversized item validation ---
    # Check each distinct item that appears in the packing list before expanding.
    seen_item_ids: set = set()
    for row_idx, row in enumerate(packing_rows):
        item = items.get(row.item_id)
        if not item:
            raise ValidationError(
                f"Row {row_idx + 1}: Item_ID '{row.item_id}' not found in Item Master. "
                "Please register this item in Data Management > Items first."
            )
        if row.item_id not in seen_item_ids:
            seen_item_ids.add(row.item_id)
            permitted = get_permitted_postures(item.this_way_up, item.max_load_bearing_kg, item.weight_kg)
            if not _check_item_fits_container(item, container, permitted):
                raise ValidationError(
                    f"Item_ID '{item.item_id}' "
                    f"({item.length_cm:g}x{item.width_cm:g}x{item.height_cm:g} cm) "
                    f"does not fit inside the container's usable interior "
                    f"({container.usable_length:g}x{container.usable_width:g}x{container.usable_height:g} cm) "
                    f"in any orientation. Check the item's dimensions or the container selection."
                )

    box_counter = 0
    for row_idx, row in enumerate(packing_rows):
        item = items.get(row.item_id)
        if not item:
            raise ValidationError(f"Row {row_idx + 1}: Item_ID '{row.item_id}' not found in Item Master. Please register this item in Data Management > Items first.")

        cust_seq = customer_sequence.get(row.customer_code, 0) if row.customer_code else 0

        permitted = get_permitted_postures(item.this_way_up, item.max_load_bearing_kg, item.weight_kg)

        inflated_length = item.length_cm + tolerance_gap
        inflated_width = item.width_cm + tolerance_gap
        inflated_height = item.height_cm

        for i in range(row.qty_cartons):
            box_counter += 1
            box_id = f"{item.item_id}_{row.po_no}_{box_counter}"
            boxes.append(
                Box(
                    box_id=box_id,
                    item_id=item.item_id,
                    po_no=row.po_no,
                    customer_code=row.customer_code,
                    customer_sequence=cust_seq,
                    length_cm=item.length_cm,
                    width_cm=item.width_cm,
                    height_cm=item.height_cm,
                    weight_kg=item.weight_kg,
                    this_way_up=item.this_way_up,
                    stacking_group=item.stacking_group,
                    max_load_bearing_kg=item.max_load_bearing_kg,
                    permitted_postures=permitted,
                    inflated_length=inflated_length,
                    inflated_width=inflated_width,
                    inflated_height=inflated_height,
                )
            )

        preview_rows.append(
                PackingListPreviewRow(
                    item_id=item.item_id,
                    po_no=row.po_no,
                    customer_code=row.customer_code,
                    description=item.description,
                    qty_cartons=row.qty_cartons,
                    length_cm=item.length_cm,
                    width_cm=item.width_cm,
                    height_cm=item.height_cm,
                    weight_kg=item.weight_kg,
                    this_way_up=item.this_way_up,
                    stacking_group=item.stacking_group,
                    max_load_bearing_kg=item.max_load_bearing_kg,
                )
            )

    return boxes, preview_rows


def build_preview(
    preview_rows: List[PackingListPreviewRow],
    shipment_type: ShipmentType,
    customer_count: int,
) -> PackingListPreview:
    total_cartons = sum(r.qty_cartons for r in preview_rows)
    total_weight = sum(r.weight_kg * r.qty_cartons for r in preview_rows)
    total_volume = sum(
        r.length_cm * r.width_cm * r.height_cm * r.qty_cartons for r in preview_rows
    )

    return PackingListPreview(
        rows=preview_rows,
        shipment_type=shipment_type,
        customer_count=customer_count,
        total_cartons=total_cartons,
        total_weight_kg=total_weight,
        total_volume_cm3=total_volume,
    )


def parse_and_join(
    packing_list_df: pd.DataFrame,
    item_master_df: pd.DataFrame,
    container_df: pd.DataFrame,
    tolerance_gap: Optional[float] = None,
) -> Tuple[List[Box], ContainerSpec, PackingListPreview, ShipmentType]:
    settings = get_settings()
    gap = tolerance_gap if tolerance_gap is not None else settings.TOLERANCE_GAP_CM

    container = parse_container_spec(container_df, tolerance_gap=gap)
    items = parse_item_master(item_master_df)

    required_packing = ["Item_ID", "PO_No", "Qty_Pcs", "Qty_Cartons"]
    missing = [c for c in required_packing if c not in packing_list_df.columns]
    if missing:
        raise ValidationError(f"Missing columns in packing list: {missing}")

    packing_rows = []
    for idx, row in packing_list_df.iterrows():
        qty_pcs = int(row["Qty_Pcs"])
        qty_cartons = int(row["Qty_Cartons"])
        if qty_pcs <= 0 or qty_cartons <= 0:
            raise ValidationError(f"Row {idx + 1}: Qty_Pcs and Qty_Cartons must be > 0")

        customer_code = None
        if "Customer_Code" in packing_list_df.columns and not pd.isna(row["Customer_Code"]):
            customer_code = str(row["Customer_Code"]).strip()
            if not customer_code:
                customer_code = None

        description = None
        if "Description" in packing_list_df.columns and not pd.isna(row["Description"]):
            description = str(row["Description"])

        packing_rows.append(
            PackingListRow(
                item_id=str(row["Item_ID"]).strip(),
                po_no=str(row["PO_No"]).strip(),
                customer_code=customer_code,
                description=description,
                qty_pcs=qty_pcs,
                qty_cartons=qty_cartons,
            )
        )

    shipment_type, customer_count, customer_sequence = detect_shipment_type(packing_rows)

    boxes, preview_rows = expand_packing_list(
        packing_rows, items, container, customer_sequence, gap
    )

    preview = build_preview(preview_rows, shipment_type, customer_count)

    return boxes, container, preview, shipment_type