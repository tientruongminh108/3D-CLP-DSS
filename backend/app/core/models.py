from enum import Enum
from typing import Optional, List, Union, Dict, Any
from pydantic import BaseModel, Field, field_validator, model_validator
from datetime import datetime
import uuid


class StackingGroup(int, Enum):
    STURDY = 1
    FRAGILE = 2


class Posture(int, Enum):
    LWH = 1
    WLH = 2
    HLW = 3
    HWL = 4
    LHW = 5
    WHL = 6


class ShipmentType(str, Enum):
    FCL = "FCL"
    LCL = "LCL"


class UnplacedReason(str, Enum):
    NO_SPACE = "no_space"
    LIFO_BLOCKED = "lifo_blocked"


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ItemBase(BaseModel):
    item_id: str = Field(..., min_length=1, max_length=50)
    description: str = Field(..., min_length=1, max_length=200)
    length_cm: float = Field(..., gt=0)
    width_cm: float = Field(..., gt=0)
    height_cm: float = Field(..., gt=0)
    weight_kg: float = Field(..., gt=0)
    this_way_up: bool = True
    stacking_group: StackingGroup = StackingGroup.STURDY
    max_load_bearing_kg: Optional[float] = Field(None, gt=0)

    @field_validator("this_way_up", mode="before")
    @classmethod
    def validate_this_way_up(cls, v):
        if not isinstance(v, bool):
            raise ValueError("This_Way_Up must be a boolean (true/false)")
        return v

    @field_validator("stacking_group", mode="before")
    @classmethod
    def validate_stacking_group(cls, v):
        if isinstance(v, int):
            if v not in (1, 2):
                raise ValueError("Stacking group must be 1 (STURDY) or 2 (FRAGILE)")
            return StackingGroup(v)
        if isinstance(v, str):
            try:
                iv = int(v)
                if iv not in (1, 2):
                    raise ValueError("Stacking group must be 1 (STURDY) or 2 (FRAGILE)")
                return StackingGroup(iv)
            except ValueError:
                raise ValueError("Stacking group must be 1 (STURDY) or 2 (FRAGILE)")
        return v


class ItemCreate(ItemBase):
    pass


class ItemUpdate(BaseModel):
    description: Optional[str] = Field(None, min_length=1, max_length=200)
    length_cm: Optional[float] = Field(None, gt=0)
    width_cm: Optional[float] = Field(None, gt=0)
    height_cm: Optional[float] = Field(None, gt=0)
    weight_kg: Optional[float] = Field(None, gt=0)
    this_way_up: Optional[bool] = None
    stacking_group: Optional[StackingGroup] = None
    max_load_bearing_kg: Optional[float] = Field(None, gt=0)


class Item(ItemBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    @field_validator("stacking_group", mode="before")
    @classmethod
    def coerce_db_stacking_group(cls, v):
        if isinstance(v, int):
            if v in (1, 2):
                return StackingGroup(v)
            return StackingGroup.STURDY
        if isinstance(v, str):
            try:
                iv = int(v)
                if iv in (1, 2):
                    return StackingGroup(iv)
            except ValueError:
                pass
            return StackingGroup.STURDY
        return v


class ContainerBase(BaseModel):
    container_type: str = Field(..., min_length=1, max_length=50)
    internal_length_cm: float = Field(..., gt=0)
    internal_width_cm: float = Field(..., gt=0)
    internal_height_cm: float = Field(..., gt=0)
    max_weight_kg: float = Field(..., gt=0)


class ContainerCreate(ContainerBase):
    pass


class ContainerUpdate(BaseModel):
    container_type: Optional[str] = Field(None, min_length=1, max_length=50)
    internal_length_cm: Optional[float] = Field(None, gt=0)
    internal_width_cm: Optional[float] = Field(None, gt=0)
    internal_height_cm: Optional[float] = Field(None, gt=0)
    max_weight_kg: Optional[float] = Field(None, gt=0)


class Container(ContainerBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PackingListRow(BaseModel):
    item_id: str = Field(..., min_length=1)
    po_no: str = Field(..., min_length=1)
    customer_code: Optional[str] = None
    description: Optional[str] = None
    qty_pcs: int = Field(..., gt=0)
    qty_cartons: int = Field(..., gt=0)

    @model_validator(mode="after")
    def validate_qty(self):
        if self.qty_pcs < self.qty_cartons:
            raise ValueError("Qty_Pcs cannot be less than Qty_Cartons")
        return self


class PackingListUpload(BaseModel):
    rows: List[PackingListRow]
    filename: Optional[str] = None


class PackingListPreviewRow(BaseModel):
    item_id: str
    po_no: str
    customer_code: Optional[str]
    description: str
    qty_cartons: int
    length_cm: float
    width_cm: float
    height_cm: float
    weight_kg: float
    this_way_up: bool
    stacking_group: int
    max_load_bearing_kg: Optional[float]


class PackingListPreview(BaseModel):
    rows: List[PackingListPreviewRow]
    shipment_type: ShipmentType
    customer_count: int
    total_cartons: int
    total_weight_kg: float
    total_volume_cm3: float


class RunOptions(BaseModel):
    population_size: int = Field(default=30, ge=10, le=200)
    generations: int = Field(default=40, ge=10, le=500)
    tolerance_gap_cm: float = Field(default=2.0, ge=0.0, le=10.0)


class RunCreate(BaseModel):
    packing_list: PackingListUpload
    container_id: int
    options: Optional[RunOptions] = None


class RunCreateQuick(BaseModel):
    packing_list: PackingListUpload
    container_type: str
    options: Optional[RunOptions] = None


class Box(BaseModel):
    box_id: str
    item_id: str
    po_no: str
    customer_code: Optional[str] = None
    customer_sequence: int = 1
    description: Optional[str] = None
    length_cm: float
    width_cm: float
    height_cm: float
    weight_kg: float
    this_way_up: bool = True
    stacking_group: int = 1
    max_load_bearing_kg: Optional[float] = None
    permitted_postures: List[Posture] = [Posture.LWH]
    inflated_length: float = 0
    inflated_width: float = 0
    inflated_height: float = 0


class PlacedBox(Box):
    x: float
    y: float
    z: float
    posture: Posture = Posture.LWH
    actual_length: float
    actual_width: float
    actual_height: float
    step_index: int = 1
    color: Optional[str] = None


class LayerBox(BaseModel):
    box_id: str
    item_id: str
    x: float
    y: float
    z: float
    length: float
    width: float
    height: float
    posture: Posture = Posture.LWH
    customer_sequence: int = 1
    step_index: int = 1
    color: Optional[str] = None


class Layer(BaseModel):
    z_min: float
    z_max: float
    boxes: List[LayerBox]


class Block(BaseModel):
    block_id: str
    boxes: List[Box]
    length_cm: float
    width_cm: float
    height_cm: float
    weight_kg: float
    customer_sequence: int
    inflated_length: float
    inflated_width: float
    inflated_height: float


class PlacedBlock(Block):
    x: float
    y: float
    z: float
    posture: Posture
    actual_length: float
    actual_width: float
    actual_height: float


class LoadMetrics(BaseModel):
    placed_count: int
    unplaced_count: int
    total_cartons: int
    fill_rate: float
    used_weight_kg: float
    max_weight_kg: float
    weight_utilization: float
    cog_x: float
    cog_y: float
    cog_z: float
    cog_deviation_xy: float
    cog_deviation_z: float


class UnplacedCarton(BaseModel):
    box_id: str
    item_id: str
    po_no: str
    customer_code: Optional[str] = None
    customer_sequence: int = 1
    reason: UnplacedReason = UnplacedReason.NO_SPACE
    length_cm: float = 0
    width_cm: float = 0
    height_cm: float = 0
    weight_kg: float = 0


class RunResult(BaseModel):
    run_id: str
    status: RunStatus
    container: Container
    metrics: LoadMetrics
    placed_boxes: List[PlacedBox]
    unplaced_cartons: List[UnplacedCarton]
    layers: Union[List[Layer], List[dict]] = []
    created_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


class RunSummary(BaseModel):
    run_id: str
    container_type: str
    shipment_type: ShipmentType
    customer_count: int
    total_cartons: int
    placed_count: int
    unplaced_count: int
    fill_rate: float
    status: RunStatus
    created_at: datetime
    completed_at: Optional[datetime] = None


class ValidationError(BaseModel):
    field: str
    message: str
    row: Optional[int] = None


class ValidationResponse(BaseModel):
    valid: bool
    errors: List[ValidationError] = []
    preview: Optional[PackingListPreview] = None


class PackingListBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    filename: Optional[str] = None
    rows: List[PackingListRow]
    total_cartons: int = 0
    total_weight_kg: float = 0
    total_volume_cm3: float = 0
    shipment_type: ShipmentType = ShipmentType.FCL
    customer_count: int = 0


class PackingListCreate(PackingListBase):
    preview: Optional[PackingListPreview] = None


class PackingListUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    rows: Optional[List[PackingListRow]] = None
    total_cartons: Optional[int] = None
    total_weight_kg: Optional[float] = None
    total_volume_cm3: Optional[float] = None
    shipment_type: Optional[ShipmentType] = None
    customer_count: Optional[int] = None


class PackingList(PackingListBase):
    id: int
    preview: Optional[PackingListPreview] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PackingListSummary(BaseModel):
    id: int
    name: str
    filename: Optional[str]
    total_cartons: int
    total_weight_kg: float
    total_volume_cm3: float
    shipment_type: ShipmentType
    customer_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True