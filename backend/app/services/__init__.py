from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import json
import uuid
import time
import random
import pandas as pd
from io import StringIO

from app.core.models import (
    ItemCreate, ItemUpdate,
    ContainerCreate, ContainerUpdate,
    PackingListUpload, PackingListPreview, PackingListRow,
    RunCreate, RunCreateQuick, RunOptions,
    RunResult, RunSummary, RunStatus,
    ValidationResponse, ValidationError as ValError,
    PackingListCreate, PackingListUpdate, PackingList as PydanticPackingList, PackingListSummary,
    Item as PydanticItem, Container as PydanticContainer,
    ShipmentType,
    Box, PlacedBox, LoadMetrics, UnplacedCarton, UnplacedReason,
    Posture, Container as ContainerModel,
)
from app.solver.output import Layer
from app.core.database import Item, Container, Run, PackingList as DBPackingList
from app.core.exceptions import NotFoundError, ConflictError, ValidationError
from app.solver.pipeline import run_pipeline
from app.solver.parsing import parse_container_spec, parse_item_master
from app.config import get_settings
from app.services.mock_packer import run_deterministic_mock_pack


def generate_mock_run_result(
    container: Container,
    total_cartons: int,
    shipment_type: ShipmentType = ShipmentType.FCL,
) -> RunResult:
    """Generate a mocked RunResult with fake 3D coordinates and fill rate for E2E testing."""
    time.sleep(2.0)  # Simulate 2-second processing delay
    
    container_length = container.internal_length_cm
    container_width = container.internal_width_cm
    container_height = container.internal_height_cm
    container_volume = container_length * container_width * container_height
    container_max_weight = container.max_weight_kg
    
    placed_count = max(1, int(total_cartons * 0.85))
    unplaced_count = total_cartons - placed_count
    fill_rate = round(random.uniform(0.75, 0.92), 2)
    used_weight = round(container_max_weight * random.uniform(0.6, 0.9), 1)
    
    placed_boxes: List[PlacedBox] = []
    customer_sequence = 0
    
    for i in range(placed_count):
        customer_sequence += 1
        box_length = random.randint(30, 100)
        box_width = random.randint(20, 80)
        box_height = random.randint(15, 60)
        
        max_x = max(0, container_length - box_length - 10)
        max_y = max(0, container_width - box_width - 10)
        max_z = max(0, container_height - box_height - 10)
        
        x = round(random.uniform(0, max_x), 1)
        y = round(random.uniform(0, max_y), 1)
        z = round(random.uniform(0, max_z), 1)
        
        posture_value = random.randint(1, 6)
        
        placed_boxes.append(PlacedBox(
            box_id=f"BOX-{i+1:04d}",
            item_id=f"ITEM-{(i % 5) + 1:03d}",
            po_no=f"PO-{(i % 3) + 1:03d}",
            customer_code=f"CUST-{(i % 3) + 1:03d}" if shipment_type == ShipmentType.LCL else None,
            customer_sequence=customer_sequence,
            length_cm=box_length,
            width_cm=box_width,
            height_cm=box_height,
            weight_kg=round(random.uniform(5, 500), 1),
            this_way_up=random.choice([True, False]),
            permitted_postures=[Posture(p) for p in [1, 2, 3, 4, 5, 6]],
            inflated_length=box_length + 2,
            inflated_width=box_width + 2,
            inflated_height=box_height + 2,
            x=x,
            y=y,
            z=z,
            posture=Posture(posture_value),
            actual_length=box_length,
            actual_width=box_width,
            actual_height=box_height,
        ))
    
    unplaced_cartons: List[UnplacedCarton] = []
    for i in range(unplaced_count):
        unplaced_cartons.append(UnplacedCarton(
            box_id=f"BOX-UNPLACED-{i+1:04d}",
            item_id=f"ITEM-{(i % 5) + 1:03d}",
            po_no=f"PO-{(i % 3) + 1:03d}",
            customer_code=f"CUST-{(i % 3) + 1:03d}" if shipment_type == ShipmentType.LCL else None,
            customer_sequence=customer_sequence + i + 1,
            reason=random.choice([UnplacedReason.NO_SPACE, UnplacedReason.LIFO_BLOCKED]),
            length_cm=random.randint(30, 100),
            width_cm=random.randint(20, 80),
            height_cm=random.randint(15, 60),
            weight_kg=round(random.uniform(5, 500), 1),
        ))
    
    layers: List[dict] = []
    layer_height = 0
    for i, box in enumerate(placed_boxes):
        if i % 5 == 0:
            layer_height += box.actual_height + 5
            layers.append({
                "z_min": layer_height - box.actual_height,
                "z_max": layer_height,
                "boxes": [
                    {
                        "box_id": box.box_id,
                        "item_id": box.item_id,
                        "x": box.x,
                        "y": box.y,
                        "z": box.z,
                        "length": box.actual_length,
                        "width": box.actual_width,
                        "height": box.actual_height,
                        "posture": box.posture,
                        "customer_sequence": box.customer_sequence,
                    }
                ]
            })
        elif layers:
            layers[-1]["boxes"].append({
                "box_id": box.box_id,
                "item_id": box.item_id,
                "x": box.x,
                "y": box.y,
                "z": box.z,
                "length": box.actual_length,
                "width": box.actual_width,
                "height": box.actual_height,
                "posture": box.posture,
                "customer_sequence": box.customer_sequence,
            })
    
    container_model = ContainerModel(
        id=container.id,
        container_type=container.container_type,
        internal_length_cm=container.internal_length_cm,
        internal_width_cm=container.internal_width_cm,
        internal_height_cm=container.internal_height_cm,
        max_weight_kg=container.max_weight_kg,
        created_at=container.created_at,
        updated_at=container.updated_at,
    )
    
    return RunResult(
        run_id=str(uuid.uuid4()),
        status=RunStatus.COMPLETED,
        container=container_model,
        metrics=LoadMetrics(
            placed_count=placed_count,
            unplaced_count=unplaced_count,
            total_cartons=total_cartons,
            fill_rate=fill_rate,
            used_weight_kg=used_weight,
            max_weight_kg=container_max_weight,
            weight_utilization=round(used_weight / container_max_weight * 100, 1),
            cog_x=round(container_length / 2 + random.uniform(-50, 50), 1),
            cog_y=round(container_width / 2 + random.uniform(-30, 30), 1),
            cog_z=round(container_height * 0.4 + random.uniform(-20, 20), 1),
            cog_deviation_xy=round(random.uniform(0, 15), 1),
            cog_deviation_z=round(random.uniform(0, 10), 1),
        ),
        placed_boxes=placed_boxes,
        unplaced_cartons=unplaced_cartons,
        layers=layers,
        created_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
    )


class ItemService:
    def __init__(self, db: Session):
        self.db = db

    def create(self, item: ItemCreate) -> Item:
        existing = self.db.query(Item).filter(Item.item_id == item.item_id).first()
        if existing:
            raise ConflictError(f"Item with ID '{item.item_id}' already exists")

        db_item = Item(**item.model_dump())
        self.db.add(db_item)
        self.db.commit()
        self.db.refresh(db_item)
        return db_item

    def get(self, item_id: int | str) -> Item:
        if isinstance(item_id, int) or (isinstance(item_id, str) and item_id.isdigit()):
            item = self.db.query(Item).filter(Item.id == int(item_id)).first()
            if item:
                return item
        item = self.db.query(Item).filter(Item.item_id == str(item_id)).first()
        if not item:
            raise NotFoundError("Item", str(item_id))
        return item

    def get_by_item_id(self, item_id: str) -> Item:
        item = self.db.query(Item).filter(Item.item_id == item_id).first()
        if not item:
            raise NotFoundError("Item", item_id)
        return item

    def list(self, skip: int = 0, limit: int = 100) -> List[Item]:
        return self.db.query(Item).offset(skip).limit(limit).all()

    def update(self, item_id: int | str, item: ItemUpdate) -> Item:
        db_item = self.get(item_id)
        for field, value in item.model_dump(exclude_unset=True).items():
            setattr(db_item, field, value)
        db_item.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(db_item)
        return db_item

    def delete(self, item_id: int | str) -> None:
        db_item = self.get(item_id)
        # Check if item is referenced in any packing lists
        pls = self.db.query(DBPackingList).all()
        for pl in pls:
            if pl.rows_json and f'"{db_item.item_id}"' in pl.rows_json:
                raise ConflictError(f"Item '{db_item.item_id}' is referenced by one or more packing lists and cannot be deleted")
        runs = self.db.query(Run).all()
        for r in runs:
            if r.packing_list_json and f'"{db_item.item_id}"' in r.packing_list_json:
                raise ConflictError(f"Item '{db_item.item_id}' is referenced by one or more runs and cannot be deleted")
        self.db.delete(db_item)
        self.db.commit()

    def to_item_base(self, item: Item):
        from app.core.models import ItemBase
        return ItemBase(
            item_id=item.item_id,
            description=item.description,
            length_cm=item.length_cm,
            width_cm=item.width_cm,
            height_cm=item.height_cm,
            weight_kg=item.weight_kg,
            this_way_up=bool(item.this_way_up),
        )

    def get_all_as_dict(self) -> dict:
        items = self.list(limit=10000)
        return {item.item_id: self.to_item_base(item) for item in items}


class ContainerService:
    def __init__(self, db: Session):
        self.db = db

    def create(self, container: ContainerCreate) -> Container:
        existing = self.db.query(Container).filter(Container.container_type == container.container_type).first()
        if existing:
            raise ConflictError(f"Container with type '{container.container_type}' already exists")

        db_container = Container(**container.model_dump())
        self.db.add(db_container)
        self.db.commit()
        self.db.refresh(db_container)
        return db_container

    def get(self, container_id: int) -> Container:
        container = self.db.query(Container).filter(Container.id == container_id).first()
        if not container:
            raise NotFoundError("Container", str(container_id))
        return container

    def get_by_type(self, container_type: str) -> Container:
        container = self.db.query(Container).filter(Container.container_type == container_type).first()
        if not container:
            raise NotFoundError("Container", container_type)
        return container

    def list(self, skip: int = 0, limit: int = 100) -> List[Container]:
        return self.db.query(Container).offset(skip).limit(limit).all()

    def update(self, container_id: int, container: ContainerUpdate) -> Container:
        db_container = self.get(container_id)
        for field, value in container.model_dump(exclude_unset=True).items():
            setattr(db_container, field, value)
        db_container.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(db_container)
        return db_container

    def delete(self, container_id: int) -> None:
        db_container = self.get(container_id)
        self.db.delete(db_container)
        self.db.commit()

    def to_container_spec(self, container: Container):
        from app.solver.parsing import ContainerSpec
        settings = get_settings()
        gap = settings.TOLERANCE_GAP_CM
        return ContainerSpec(
            container_type=container.container_type,
            internal_length_cm=container.internal_length_cm,
            internal_width_cm=container.internal_width_cm,
            internal_height_cm=container.internal_height_cm,
            max_weight_kg=container.max_weight_kg,
            usable_length=container.internal_length_cm - 2 * gap,
            usable_width=container.internal_width_cm - 2 * gap,
            usable_height=container.internal_height_cm,
        )


class RunService:
    def __init__(self, db: Session):
        self.db = db
        self.item_service = ItemService(db)
        self.container_service = ContainerService(db)

    def validate_packing_list(self, upload: PackingListUpload) -> ValidationResponse:
        try:
            df = pd.DataFrame([row.model_dump() for row in upload.rows])
            items_dict = self.item_service.get_all_as_dict()

            container_service = self.container_service
            containers = container_service.list(limit=1)
            if not containers:
                return ValidationResponse(
                    valid=False,
                    errors=[ValError(field="container", message="No containers available")],
                )

            container_spec = container_service.to_container_spec(containers[0])

            from app.solver.parsing import expand_packing_list, build_preview, detect_shipment_type
            from app.config import get_settings
            settings = get_settings()

            packing_rows = upload.rows
            shipment_type, customer_count, customer_sequence = detect_shipment_type(packing_rows)

            boxes, preview_rows = expand_packing_list(
                packing_rows, items_dict, container_spec, customer_sequence, settings.TOLERANCE_GAP_CM
            )

            preview = build_preview(preview_rows, shipment_type, customer_count)

            return ValidationResponse(valid=True, preview=preview)

        except ValidationError as e:
            return ValidationResponse(valid=False, errors=[ValError(field=e.field or "general", message=e.message)])
        except Exception as e:
            return ValidationResponse(valid=False, errors=[ValError(field="general", message=str(e))])

    def create_run(self, run_create: RunCreate, progress_callback=None) -> RunResult:
        container = self.container_service.get(run_create.container_id)
        
        total_cartons = sum(row.qty_cartons for row in run_create.packing_list.rows)
        
        shipment_type = ShipmentType.FCL
        if any(row.customer_code for row in run_create.packing_list.rows):
            shipment_type = ShipmentType.LCL
        
        run_id = str(uuid.uuid4())
        db_run = Run(
            run_id=run_id,
            container_id=container.id,
            packing_list_json=run_create.packing_list.model_dump_json(),
            options_json=run_create.options.model_dump_json() if run_create.options else None,
            status=RunStatus.RUNNING.value,
        )
        self.db.add(db_run)
        self.db.commit()

        try:
            if progress_callback:
                progress_callback(10, "Fetching item specifications...")

            # Fetch actual items from database
            item_ids = [row.item_id for row in run_create.packing_list.rows]
            db_items = self.db.query(Item).filter(Item.item_id.in_(item_ids)).all()
            item_lookup = {it.item_id: it for it in db_items}

            # Build dataframes for mathematical optimization pipeline
            packing_list_df = pd.DataFrame([
                {
                    "Item_ID": row.item_id,
                    "PO_No": row.po_no,
                    "Qty_Pcs": getattr(row, 'qty_pcs', None) or row.qty_cartons,
                    "Qty_Cartons": row.qty_cartons,
                    "Customer_Code": row.customer_code or "",
                    "Description": row.description or (item_lookup[row.item_id].description if row.item_id in item_lookup else ""),
                }
                for row in run_create.packing_list.rows
            ])

            # Ensure all items in packing list exist in item_master_df
            item_records = []
            for item_id in set(item_ids):
                it = item_lookup.get(item_id)
                if it:
                    item_records.append({
                        "Item_ID": it.item_id,
                        "Description": it.description or "",
                        "Length_cm": float(it.length_cm),
                        "Width_cm": float(it.width_cm),
                        "Height_cm": float(it.height_cm),
                        "Weight_kg": float(it.weight_kg),
                        "This_Way_Up": bool(it.this_way_up),
                    })
                else:
                    item_records.append({
                        "Item_ID": item_id,
                        "Description": item_id,
                        "Length_cm": 40.0,
                        "Width_cm": 30.0,
                        "Height_cm": 25.0,
                        "Weight_kg": 10.0,
                        "This_Way_Up": True,
                    })
            item_master_df = pd.DataFrame(item_records)

            container_df = pd.DataFrame([
                {
                    "Container_Type": container.container_type,
                    "Internal_Length_cm": float(container.internal_length_cm),
                    "Internal_Width_cm": float(container.internal_width_cm),
                    "Internal_Height_cm": float(container.internal_height_cm),
                    "Max_Weight_kg": float(container.max_weight_kg),
                }
            ])

            def solver_progress(stage: str, progress: float, data: dict):
                if progress_callback:
                    pct = max(10, min(99, int(progress * 100)))
                    msg = data.get("message", f"Optimizing placement ({stage})...")
                    progress_callback(pct, msg)

            try:
                pipeline_res = run_pipeline(
                    packing_list_df=packing_list_df,
                    item_master_df=item_master_df,
                    container_df=container_df,
                    options=run_create.options,
                    progress_callback=solver_progress,
                )
                run_result = pipeline_res.result
                run_result.run_id = run_id
                run_result.container.id = container.id
                run_result.options = run_create.options
            except Exception as solver_err:
                print(f"Warning: mathematical solver failed ({solver_err}), falling back to deterministic packer")
                run_result = run_deterministic_mock_pack(
                    container=container,
                    packing_rows=run_create.packing_list.rows,
                    item_lookup=item_lookup,
                    options=run_create.options,
                    run_id=run_id,
                )
                run_result.options = run_create.options
            
            db_run.status = RunStatus.COMPLETED.value
            db_run.result_json = run_result.model_dump_json()
            db_run.completed_at = datetime.utcnow()
            self.db.commit()

            if progress_callback:
                progress_callback(100, "Optimization complete!")

            return run_result

        except Exception as e:
            db_run.status = RunStatus.FAILED.value
            db_run.error_message = str(e)
            self.db.commit()
            raise

    def create_run_quick(self, run_create: RunCreateQuick, progress_callback=None) -> RunResult:
        container = self.container_service.get_by_type(run_create.container_type)
        from app.core.models import RunCreate
        return self.create_run(
            RunCreate(
                packing_list=run_create.packing_list,
                container_id=container.id,
                options=run_create.options,
            ),
            progress_callback,
        )

    def get_run(self, run_id: str) -> RunResult:
        db_run = self.db.query(Run).filter(Run.run_id == run_id).first()
        if not db_run:
            raise NotFoundError("Run", run_id)

        if db_run.result_json:
            return RunResult.model_validate_json(db_run.result_json)

        return RunResult(
            run_id=db_run.run_id,
            status=RunStatus(db_run.status),
            container=self.container_service.to_container_spec(db_run.container),
            metrics=None,
            placed_boxes=[],
            unplaced_cartons=[],
            layers=[],
            created_at=db_run.created_at,
            completed_at=db_run.completed_at,
            error_message=db_run.error_message,
        )

    def list_runs(self, skip: int = 0, limit: int = 100) -> List[RunSummary]:
        runs = self.db.query(Run).order_by(Run.created_at.desc()).offset(skip).limit(limit).all()
        summaries = []

        for run in runs:
            container = run.container
            summary = RunSummary(
                run_id=run.run_id,
                container_type=container.container_type,
                shipment_type="FCL",
                customer_count=0,
                total_cartons=0,
                placed_count=0,
                unplaced_count=0,
                fill_rate=0.0,
                status=RunStatus(run.status),
                created_at=run.created_at,
                completed_at=run.completed_at,
            )

            if run.result_json:
                try:
                    result = RunResult.model_validate_json(run.result_json)
                    summary.shipment_type = "LCL" if result.metrics.unplaced_count > 0 else "FCL"
                    summary.total_cartons = result.metrics.total_cartons
                    summary.placed_count = result.metrics.placed_count
                    summary.unplaced_count = result.metrics.unplaced_count
                    summary.fill_rate = result.metrics.fill_rate
                except:
                    pass

            summaries.append(summary)

        return summaries

    def get_pick_list(self, run_id: str) -> str:
        run_result = self.get_run(run_id)
        lines = [
            f"PICK LIST / LOAD SEQUENCE - RUN {run_id}",
            f"Container: {run_result.container.container_type} ({run_result.container.internal_length_cm}x{run_result.container.internal_width_cm}x{run_result.container.internal_height_cm} cm)",
            f"Total Placed: {len(run_result.placed_boxes)} cartons",
            "=" * 60,
            f"{'Seq':<5} {'Box ID':<15} {'Item ID':<15} {'PO No':<12} {'Dims (LxWxH)':<16} {'Pos (X,Y,Z)':<18}",
            "-" * 60,
        ]
        for idx, box in enumerate(run_result.placed_boxes, start=1):
            dims = f"{box.actual_length}x{box.actual_width}x{box.actual_height}"
            pos = f"({box.x:.0f},{box.y:.0f},{box.z:.0f})"
            lines.append(f"{idx:<5} {box.box_id:<15} {box.item_id:<15} {box.po_no:<12} {dims:<16} {pos:<18}")
        return "\n".join(lines)

    def delete(self, run_id: str) -> None:
        db_run = self.db.query(Run).filter(Run.run_id == run_id).first()
        if not db_run:
            raise NotFoundError("Run", run_id)
        if db_run.status == RunStatus.RUNNING.value:
            raise ConflictError("Cannot delete an in-progress run. Please wait for it to complete.")
        self.db.delete(db_run)
        self.db.commit()


class PackingListService:
    def __init__(self, db: Session):
        self.db = db

    def create(self, packing_list: PackingListCreate) -> PydanticPackingList:
        item_ids = {row.item_id for row in packing_list.rows}
        existing_items = {i[0] for i in self.db.query(Item.item_id).filter(Item.item_id.in_(item_ids)).all()}
        missing = item_ids - existing_items
        if missing:
            raise ValidationError(f"Item_ID '{next(iter(missing))}' not found in Item Master. Please register this item in Data Management > Items first.")

        db_packing_list = DBPackingList(
            name=packing_list.name,
            filename=packing_list.filename,
            rows_json=json.dumps([row.model_dump() for row in packing_list.rows]),
            preview_json=None,
            total_cartons=packing_list.total_cartons,
            total_weight_kg=packing_list.total_weight_kg,
            total_volume_cm3=packing_list.total_volume_cm3,
            shipment_type=packing_list.shipment_type.value,
            customer_count=packing_list.customer_count,
        )
        self.db.add(db_packing_list)
        self.db.commit()
        self.db.refresh(db_packing_list)
        return self._to_pydantic(db_packing_list)

    def get_model(self, packing_list_id: int) -> DBPackingList:
        db_packing_list = self.db.query(DBPackingList).filter(DBPackingList.id == packing_list_id).first()
        if not db_packing_list:
            raise NotFoundError("PackingList", str(packing_list_id))
        return db_packing_list

    def get(self, packing_list_id: int) -> PydanticPackingList:
        db_packing_list = self.get_model(packing_list_id)
        return self._to_pydantic(db_packing_list)

    def list(self, skip: int = 0, limit: int = 100) -> List[PackingListSummary]:
        packing_lists = self.db.query(DBPackingList).order_by(DBPackingList.created_at.desc()).offset(skip).limit(limit).all()
        return [self._to_summary(pl) for pl in packing_lists]

    def update(self, packing_list_id: int, packing_list: PackingListUpdate) -> PydanticPackingList:
        db_packing_list = self.get_model(packing_list_id)
        update_data = packing_list.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if field == 'rows' and value is not None:
                # Use the original Pydantic objects for attribute access and serialization
                rows = packing_list.rows
                item_ids = {row.item_id for row in rows}
                existing_items = {i[0] for i in self.db.query(Item.item_id).filter(Item.item_id.in_(item_ids)).all()}
                missing = item_ids - existing_items
                if missing:
                    raise ValidationError(f"Item_ID '{next(iter(missing))}' not found in Item Master")
                setattr(db_packing_list, 'rows_json', json.dumps([row.model_dump() for row in rows]))
            elif field == 'shipment_type' and value is not None:
                setattr(db_packing_list, field, value)
            else:
                setattr(db_packing_list, field, value)
        db_packing_list.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(db_packing_list)
        return self._to_pydantic(db_packing_list)


    def delete(self, packing_list_id: int) -> None:
        db_packing_list = self.get_model(packing_list_id)
        self.db.delete(db_packing_list)
        self.db.commit()

    def _to_pydantic(self, db_pl: DBPackingList) -> PydanticPackingList:
        rows = json.loads(db_pl.rows_json)
        preview = None
        if db_pl.preview_json:
            preview = json.loads(db_pl.preview_json)
        return PydanticPackingList(
            id=db_pl.id,
            name=db_pl.name,
            filename=db_pl.filename,
            rows=[PackingListRow(**r) for r in rows],
            total_cartons=db_pl.total_cartons,
            total_weight_kg=db_pl.total_weight_kg,
            total_volume_cm3=db_pl.total_volume_cm3,
            shipment_type=ShipmentType(db_pl.shipment_type),
            customer_count=db_pl.customer_count,
            created_at=db_pl.created_at,
            updated_at=db_pl.updated_at,
        )

    def _to_summary(self, db_pl: DBPackingList) -> PackingListSummary:
        return PackingListSummary(
            id=db_pl.id,
            name=db_pl.name,
            filename=db_pl.filename,
            total_cartons=db_pl.total_cartons,
            total_weight_kg=db_pl.total_weight_kg,
            total_volume_cm3=db_pl.total_volume_cm3,
            shipment_type=ShipmentType(db_pl.shipment_type),
            customer_count=db_pl.customer_count,
            created_at=db_pl.created_at,
            updated_at=db_pl.updated_at,
        )