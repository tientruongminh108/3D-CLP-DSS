from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Response
from sqlalchemy.orm import Session
from typing import List
import pandas as pd
from io import StringIO
from datetime import datetime

from app.core.database import get_db
from app.core.models import (
    Item, ItemCreate, ItemUpdate,
    Container, ContainerCreate, ContainerUpdate,
    PackingListUpload, PackingListPreview, PackingListRow,
    RunCreate, RunCreateQuick, RunOptions,
    RunResult, RunSummary, ValidationResponse,
    PackingListCreate, PackingListUpdate, PackingList, PackingListSummary,
)
from app.core.exceptions import DSSException
from app.services import ItemService, ContainerService, RunService, PackingListService
from app.core.database import Item as DBItem, Container as DBContainer, PackingList as DBPackingList

router = APIRouter()


@router.post("/items", response_model=Item, status_code=status.HTTP_201_CREATED)
def create_item(item: ItemCreate, db: Session = Depends(get_db)):
    try:
        service = ItemService(db)
        return service.create(item)
    except DSSException as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.get("/items", response_model=List[Item])
def list_items(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    service = ItemService(db)
    return service.list(skip, limit)


@router.get("/items/{item_id}", response_model=Item)
def get_item(item_id: str, db: Session = Depends(get_db)):
    try:
        service = ItemService(db)
        return service.get(item_id)
    except DSSException as e:
        raise HTTPException(status_code=404, detail=e.message)


@router.put("/items/{item_id}", response_model=Item)
def update_item(item_id: str, item: ItemUpdate, db: Session = Depends(get_db)):
    try:
        service = ItemService(db)
        return service.update(item_id, item)
    except DSSException as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: str, db: Session = Depends(get_db)):
    try:
        service = ItemService(db)
        service.delete(item_id)
    except DSSException as e:
        if e.code == "CONFLICT":
            raise HTTPException(status_code=409, detail=e.message)
        raise HTTPException(status_code=404, detail=e.message)


@router.post("/containers", response_model=Container, status_code=status.HTTP_201_CREATED)
def create_container(container: ContainerCreate, db: Session = Depends(get_db)):
    try:
        service = ContainerService(db)
        return service.create(container)
    except DSSException as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.get("/containers", response_model=List[Container])
def list_containers(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    service = ContainerService(db)
    return service.list(skip, limit)


@router.get("/containers/{container_id}", response_model=Container)
def get_container(container_id: int, db: Session = Depends(get_db)):
    try:
        service = ContainerService(db)
        return service.get(container_id)
    except DSSException as e:
        raise HTTPException(status_code=404, detail=e.message)


@router.put("/containers/{container_id}", response_model=Container)
def update_container(container_id: int, container: ContainerUpdate, db: Session = Depends(get_db)):
    try:
        service = ContainerService(db)
        return service.update(container_id, container)
    except DSSException as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.delete("/containers/{container_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_container(container_id: int, db: Session = Depends(get_db)):
    try:
        service = ContainerService(db)
        service.delete(container_id)
    except DSSException as e:
        raise HTTPException(status_code=404, detail=e.message)


@router.post("/packing-lists/validate", response_model=ValidationResponse)
def validate_packing_list(upload: PackingListUpload, db: Session = Depends(get_db)):
    service = RunService(db)
    return service.validate_packing_list(upload)


@router.post("/packing-lists/validate-csv", response_model=ValidationResponse)
async def validate_packing_list_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = await file.read()
    try:
        df = pd.read_csv(StringIO(content.decode('utf-8')))
        rows = []
        for _, row in df.iterrows():
            rows.append({
                "item_id": str(row.get("Item_ID", "")),
                "po_no": str(row.get("PO_No", "")),
                "customer_code": str(row.get("Customer_Code", "")) if pd.notna(row.get("Customer_Code")) else None,
                "description": str(row.get("Description", "")) if pd.notna(row.get("Description")) else None,
                "qty_pcs": int(row.get("Qty_Pcs", 0)),
                "qty_cartons": int(row.get("Qty_Cartons", 0)),
            })
        upload = PackingListUpload(rows=rows)
        service = RunService(db)
        return service.validate_packing_list(upload)
    except Exception as e:
        return ValidationResponse(valid=False, errors=[ValueError(field="file", message=str(e))])


@router.post("/runs", response_model=RunResult, status_code=status.HTTP_201_CREATED)
def create_run(run: RunCreate, db: Session = Depends(get_db)):
    try:
        service = RunService(db)
        return service.create_run(run)
    except DSSException as e:
        raise HTTPException(status_code=400, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/runs/quick", response_model=RunResult, status_code=status.HTTP_201_CREATED)
def create_run_quick(run: RunCreateQuick, db: Session = Depends(get_db)):
    try:
        service = RunService(db)
        return service.create_run_quick(run)
    except DSSException as e:
        raise HTTPException(status_code=400, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/runs", response_model=List[RunSummary])
def list_runs(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    service = RunService(db)
    return service.list_runs(skip, limit)


@router.get("/runs/{run_id}", response_model=RunResult)
def get_run(run_id: str, db: Session = Depends(get_db)):
    try:
        service = RunService(db)
        return service.get_run(run_id)
    except DSSException as e:
        raise HTTPException(status_code=404, detail=e.message)


@router.get("/runs/{run_id}/pick-list")
def get_pick_list(run_id: str, db: Session = Depends(get_db)):
    """GET /runs/{run_id}/pick-list - returns text/plain pick list document."""
    try:
        service = RunService(db)
        content = service.get_pick_list(run_id)
        return Response(content=content, media_type="text/plain")
    except DSSException as e:
        raise HTTPException(status_code=404, detail=e.message)


# ============================================
# BULK UPLOAD ENDPOINTS
# ============================================

@router.post("/items/upload-csv", response_model=dict)
async def upload_items_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload Item Master data from CSV file"""
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV")
    
    content = await file.read()
    try:
        df = pd.read_csv(StringIO(content.decode('utf-8-sig')))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid CSV format: {str(e)}")
    
    # Normalize column names
    df.columns = df.columns.str.strip().str.lower().str.replace('\ufeff', '').str.replace(' ', '_').str.replace('-', '_')
    
    # Map possible column names
    col_mapping = {
        'item_id': ['item_id', 'item_code', 'itemcode', 'sku', 'id', 'code'],
        'description': ['description', 'name', 'item_name', 'itemname', 'desc'],
        'length_cm': ['length_cm', 'length', 'l', 'len', 'length(cm)', 'length_(cm)'],
        'width_cm': ['width_cm', 'width', 'w', 'wid', 'width(cm)', 'width_(cm)'],
        'height_cm': ['height_cm', 'height', 'h', 'hei', 'height(cm)', 'height_(cm)'],
        'weight_kg': ['weight_kg', 'weight', 'kg', 'wt', 'weight(kg)', 'weight_(kg)'],
        'this_way_up': ['this_way_up', 'thiswayup', 'orientation', 'upright'],
        'stacking_group': ['stacking_group', 'stack_group', 'stackgroup', 'group', 'stack'],
        'max_load_bearing_kg': ['max_load_bearing_kg', 'max_load', 'maxload', 'load_bearing', 'loadbearing', 'max_load_bearing'],
    }
    
    def get_col(df_cols, possible_names):
        for name in possible_names:
            if name in df_cols:
                return name
        return None
    
    mapped_cols = {}
    for standard_name, possible_names in col_mapping.items():
        col = get_col(df.columns.tolist(), possible_names)
        if col:
            mapped_cols[standard_name] = col
    
    # Check required columns
    required = ['item_id', 'description', 'length_cm', 'width_cm', 'height_cm', 'weight_kg']
    missing = [r for r in required if r not in mapped_cols]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing required columns: {missing}. Found columns: {list(df.columns)}")
    
    df = df.dropna(how='all')
    service = ItemService(db)
    created = 0
    updated = 0
    errors = []
    
    for idx, row in df.iterrows():
        try:
            raw_item_id = row[mapped_cols['item_id']]
            if pd.isna(raw_item_id) or not str(raw_item_id).strip():
                continue
            item_id_str = str(raw_item_id).strip()
            
            raw_desc = row[mapped_cols['description']]
            desc_str = str(raw_desc).strip() if pd.notna(raw_desc) and str(raw_desc).strip() else item_id_str
            
            item_data = {
                'item_id': item_id_str,
                'description': desc_str,
                'length_cm': float(row[mapped_cols['length_cm']]),
                'width_cm': float(row[mapped_cols['width_cm']]),
                'height_cm': float(row[mapped_cols['height_cm']]),
                'weight_kg': float(row[mapped_cols['weight_kg']]),
            }
            
            # Optional fields
            if 'this_way_up' in mapped_cols:
                val = row[mapped_cols['this_way_up']]
                if pd.notna(val) and str(val).strip():
                    item_data['this_way_up'] = str(val).strip().lower() in ['true', 'yes', '1', 'y', 't']
            
            if 'stacking_group' in mapped_cols:
                val = row[mapped_cols['stacking_group']]
                if pd.notna(val) and str(val).strip():
                    grp_str = str(val).strip().upper()
                    if grp_str in ('1', 'STURDY'):
                        item_data['stacking_group'] = 1
                    elif grp_str in ('2', 'FRAGILE'):
                        item_data['stacking_group'] = 2
                    else:
                        try:
                            grp_val = int(float(grp_str))
                            if grp_val in (1, 2):
                                item_data['stacking_group'] = grp_val
                            else:
                                errors.append(f"Row {idx + 2}: Stacking group must be 1 (STURDY) or 2 (FRAGILE)")
                                continue
                        except (ValueError, TypeError):
                            errors.append(f"Row {idx + 2}: Stacking group must be 1 (STURDY) or 2 (FRAGILE)")
                            continue
            
            if 'max_load_bearing_kg' in mapped_cols:
                val = row[mapped_cols['max_load_bearing_kg']]
                if pd.notna(val) and str(val).strip() and str(val).strip().lower() not in ['nan', 'none', 'null', '']:
                    try:
                        f_load = float(val)
                        if f_load > 0:
                            item_data['max_load_bearing_kg'] = f_load
                        else:
                            item_data['max_load_bearing_kg'] = None
                    except (ValueError, TypeError):
                        pass
                else:
                    item_data['max_load_bearing_kg'] = None
            
            # Validate required fields
            if not item_data['item_id'] or not item_data['description']:
                errors.append(f"Row {idx + 2}: Missing required fields")
                continue
            if item_data['length_cm'] <= 0 or item_data['width_cm'] <= 0 or item_data['height_cm'] <= 0 or item_data['weight_kg'] <= 0:
                errors.append(f"Row {idx + 2}: Dimensions and weight must be positive")
                continue
            
            # Check if item exists
            existing = db.query(DBItem).filter(DBItem.item_id == item_data['item_id']).first()
            if existing:
                # Update existing
                for key, value in item_data.items():
                    setattr(existing, key, value)
                existing.updated_at = datetime.utcnow()
                updated += 1
            else:
                # Create new
                db_item = DBItem(**item_data)
                db.add(db_item)
                created += 1
        
        except Exception as e:
            errors.append(f"Row {idx + 2}: {str(e)}")
    
    db.commit()
    
    return {
        "success": True,
        "created": created,
        "updated": updated,
        "errors": errors,
        "total_rows": len(df)
    }


@router.post("/containers/upload-csv", response_model=dict)
async def upload_containers_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload Container Spec data from CSV file"""
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV")
    
    content = await file.read()
    try:
        df = pd.read_csv(StringIO(content.decode('utf-8')))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid CSV format: {str(e)}")
    
    # Normalize column names
    df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_').str.replace('-', '_')
    
    # Map possible column names
    col_mapping = {
        'container_type': ['container_type', 'container_type', 'type', 'container_id', 'containerid', 'name', 'id', 'code'],
        'internal_length_cm': ['internal_length_cm', 'internal_length', 'length_cm', 'length', 'l', 'len'],
        'internal_width_cm': ['internal_width_cm', 'internal_width', 'width_cm', 'width', 'w', 'wid'],
        'internal_height_cm': ['internal_height_cm', 'internal_height', 'height_cm', 'height', 'h', 'hei'],
        'max_weight_kg': ['max_weight_kg', 'max_weight', 'weight', 'weight_kg', 'kg', 'capacity'],
    }
    
    def get_col(df_cols, possible_names):
        for name in possible_names:
            if name in df_cols:
                return name
        return None
    
    mapped_cols = {}
    for standard_name, possible_names in col_mapping.items():
        col = get_col(df.columns.tolist(), possible_names)
        if col:
            mapped_cols[standard_name] = col
    
    # Check required columns
    required = ['container_type', 'internal_length_cm', 'internal_width_cm', 'internal_height_cm', 'max_weight_kg']
    missing = [r for r in required if r not in mapped_cols]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing required columns: {missing}. Found columns: {list(df.columns)}")
    
    df = df.dropna(how='all')
    service = ContainerService(db)
    created = 0
    updated = 0
    errors = []
    
    for idx, row in df.iterrows():
        try:
            raw_c_type = row[mapped_cols['container_type']]
            if pd.isna(raw_c_type) or not str(raw_c_type).strip():
                continue
            c_type_str = str(raw_c_type).strip()

            container_data = {
                'container_type': c_type_str,
                'internal_length_cm': float(row[mapped_cols['internal_length_cm']]),
                'internal_width_cm': float(row[mapped_cols['internal_width_cm']]),
                'internal_height_cm': float(row[mapped_cols['internal_height_cm']]),
                'max_weight_kg': float(row[mapped_cols['max_weight_kg']]),
            }
            
            # Validate required fields
            if not container_data['container_type']:
                errors.append(f"Row {idx + 2}: Missing container type")
                continue
            if container_data['internal_length_cm'] <= 0 or container_data['internal_width_cm'] <= 0 or container_data['internal_height_cm'] <= 0 or container_data['max_weight_kg'] <= 0:
                errors.append(f"Row {idx + 2}: Dimensions and weight must be positive")
                continue
            
            # Check if container exists
            existing = db.query(DBContainer).filter(DBContainer.container_type == container_data['container_type']).first()
            if existing:
                # Update existing
                for key, value in container_data.items():
                    setattr(existing, key, value)
                existing.updated_at = datetime.utcnow()
                updated += 1
            else:
                # Create new
                db_container = DBContainer(**container_data)
                db.add(db_container)
                created += 1
        
        except Exception as e:
            errors.append(f"Row {idx + 2}: {str(e)}")
    
    db.commit()
    
    return {
        "success": True,
        "created": created,
        "updated": updated,
        "errors": errors,
        "total_rows": len(df)
    }


@router.post("/packing-lists/upload-csv", response_model=dict)
async def upload_packing_list_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload Packing List data from CSV file - validates and returns preview"""
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV")
    
    content = await file.read()
    try:
        df = pd.read_csv(StringIO(content.decode('utf-8')))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid CSV format: {str(e)}")
    
    # Normalize column names
    df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_').str.replace('-', '_')
    
    # Map possible column names
    col_mapping = {
        'item_id': ['item_id', 'item_code', 'itemcode', 'sku', 'id', 'code'],
        'po_no': ['po_no', 'po_no', 'po', 'po_number', 'order_no', 'order'],
        'customer_code': ['customer_code', 'customer_code', 'customer', 'client_code', 'client', 'cust'],
        'description': ['description', 'name', 'item_name', 'itemname', 'desc'],
        'qty_pcs': ['qty_pcs', 'qty_pcs', 'pieces', 'pcs', 'qty'],
        'qty_cartons': ['qty_cartons', 'qty_cartons', 'cartons', 'ctns', 'quantity'],
    }
    
    def get_col(df_cols, possible_names):
        for name in possible_names:
            if name in df_cols:
                return name
        return None
    
    mapped_cols = {}
    for standard_name, possible_names in col_mapping.items():
        col = get_col(df.columns.tolist(), possible_names)
        if col:
            mapped_cols[standard_name] = col
    
    # Check required columns
    required = ['item_id', 'po_no', 'qty_cartons']
    missing = [r for r in required if r not in mapped_cols]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing required columns: {missing}. Found columns: {list(df.columns)}")
    
    df = df.dropna(how='all')
    rows = []
    errors = []
    
    for idx, row in df.iterrows():
        try:
            raw_item_id = row[mapped_cols['item_id']]
            if pd.isna(raw_item_id) or not str(raw_item_id).strip():
                continue
            raw_po = row[mapped_cols['po_no']]
            if pd.isna(raw_po) or not str(raw_po).strip():
                continue
            raw_qty = row[mapped_cols['qty_cartons']]
            if pd.isna(raw_qty) or str(raw_qty).strip() == '':
                continue
            
            item_id = str(raw_item_id).strip()
            po_no = str(raw_po).strip()
            qty_cartons = int(float(raw_qty))
            
            if not item_id or not po_no or qty_cartons <= 0:
                errors.append(f"Row {idx + 2}: Missing or invalid required fields")
                continue
            
            row_data = {
                'item_id': item_id,
                'po_no': po_no,
                'qty_cartons': qty_cartons,
            }
            
            if 'customer_code' in mapped_cols:
                val = row[mapped_cols['customer_code']]
                if pd.notna(val) and str(val).strip():
                    row_data['customer_code'] = str(val)
            
            if 'description' in mapped_cols:
                val = row[mapped_cols['description']]
                if pd.notna(val) and str(val).strip():
                    row_data['description'] = str(val)
            
            if 'qty_pcs' in mapped_cols:
                val = row[mapped_cols['qty_pcs']]
                if pd.notna(val):
                    row_data['qty_pcs'] = int(val)
                else:
                    row_data['qty_pcs'] = qty_cartons
            else:
                row_data['qty_pcs'] = qty_cartons
            
            rows.append(row_data)
        
        except Exception as e:
            errors.append(f"Row {idx + 2}: {str(e)}")
    
    # Validate against existing items and containers
    if rows:
        try:
            upload = PackingListUpload(rows=rows)
            service = RunService(db)
            validation = service.validate_packing_list(upload)
            
            return {
                "success": validation.valid,
                "rows_parsed": len(rows),
                "errors": errors + ([e.message for e in validation.errors] if validation.errors else []),
                "preview": validation.preview.model_dump() if validation.preview else None
            }
        except Exception as e:
            errors.append(f"Validation error: {str(e)}")
    
    return {
        "success": len(errors) == 0,
        "rows_parsed": len(rows),
        "errors": errors,
        "preview": None
    }


# ============================================
# PACKING LIST CRUD ENDPOINTS
# ============================================

@router.post("/packing-lists", response_model=PackingList, status_code=status.HTTP_201_CREATED)
def create_packing_list(packing_list: PackingListCreate, db: Session = Depends(get_db)):
    try:
        service = PackingListService(db)
        return service.create(packing_list)
    except DSSException as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.get("/packing-lists", response_model=List[PackingListSummary])
def list_packing_lists(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    service = PackingListService(db)
    return service.list(skip, limit)


@router.get("/packing-lists/{packing_list_id}", response_model=PackingList)
def get_packing_list(packing_list_id: int, db: Session = Depends(get_db)):
    try:
        service = PackingListService(db)
        return service.get(packing_list_id)
    except DSSException as e:
        raise HTTPException(status_code=404, detail=e.message)


@router.put("/packing-lists/{packing_list_id}", response_model=PackingList)
def update_packing_list(packing_list_id: int, packing_list: PackingListUpdate, db: Session = Depends(get_db)):
    try:
        service = PackingListService(db)
        return service.update(packing_list_id, packing_list)
    except DSSException as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.delete("/packing-lists/{packing_list_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_packing_list(packing_list_id: int, db: Session = Depends(get_db)):
    try:
        service = PackingListService(db)
        service.delete(packing_list_id)
    except DSSException as e:
        raise HTTPException(status_code=404, detail=e.message)


@router.post("/packing-lists/upload-csv-and-save", response_model=dict)
async def upload_and_save_packing_list_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload Packing List CSV, validate, and save to database"""
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV")
    
    content = await file.read()
    try:
        df = pd.read_csv(StringIO(content.decode('utf-8')))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid CSV format: {str(e)}")
    
    # Normalize column names
    df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_').str.replace('-', '_')
    
    # Map possible column names
    col_mapping = {
        'item_id': ['item_id', 'item_code', 'itemcode', 'sku', 'id', 'code'],
        'po_no': ['po_no', 'po_no', 'po', 'po_number', 'order_no', 'order'],
        'customer_code': ['customer_code', 'customer_code', 'customer', 'client_code', 'client', 'cust'],
        'description': ['description', 'name', 'item_name', 'itemname', 'desc'],
        'qty_pcs': ['qty_pcs', 'qty_pcs', 'pieces', 'pcs', 'qty'],
        'qty_cartons': ['qty_cartons', 'qty_cartons', 'cartons', 'ctns', 'quantity'],
    }
    
    def get_col(df_cols, possible_names):
        for name in possible_names:
            if name in df_cols:
                return name
        return None
    
    mapped_cols = {}
    for standard_name, possible_names in col_mapping.items():
        col = get_col(df.columns.tolist(), possible_names)
        if col:
            mapped_cols[standard_name] = col
    
    # Check required columns
    required = ['item_id', 'po_no', 'qty_cartons']
    missing = [r for r in required if r not in mapped_cols]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing required columns: {missing}. Found columns: {list(df.columns)}")
    
    df = df.dropna(how='all')
    rows = []
    errors = []
    
    for idx, row in df.iterrows():
        try:
            raw_item_id = row[mapped_cols['item_id']]
            if pd.isna(raw_item_id) or not str(raw_item_id).strip():
                continue
            raw_po = row[mapped_cols['po_no']]
            if pd.isna(raw_po) or not str(raw_po).strip():
                continue
            raw_qty = row[mapped_cols['qty_cartons']]
            if pd.isna(raw_qty) or str(raw_qty).strip() == '':
                continue
            
            item_id = str(raw_item_id).strip()
            po_no = str(raw_po).strip()
            qty_cartons = int(float(raw_qty))
            
            if not item_id or not po_no or qty_cartons <= 0:
                errors.append(f"Row {idx + 2}: Missing or invalid required fields")
                continue
            
            row_data = {
                'item_id': item_id,
                'po_no': po_no,
                'qty_cartons': qty_cartons,
            }
            
            if 'customer_code' in mapped_cols:
                val = row[mapped_cols['customer_code']]
                if pd.notna(val) and str(val).strip():
                    row_data['customer_code'] = str(val)
            
            if 'description' in mapped_cols:
                val = row[mapped_cols['description']]
                if pd.notna(val) and str(val).strip():
                    row_data['description'] = str(val)
            
            if 'qty_pcs' in mapped_cols:
                val = row[mapped_cols['qty_pcs']]
                if pd.notna(val):
                    row_data['qty_pcs'] = int(val)
                else:
                    row_data['qty_pcs'] = qty_cartons
            else:
                row_data['qty_pcs'] = qty_cartons
            
            rows.append(row_data)
        
        except Exception as e:
            errors.append(f"Row {idx + 2}: {str(e)}")
    
    # Validate against existing items and containers
    if rows:
        try:
            upload = PackingListUpload(rows=rows)
            service = RunService(db)
            validation = service.validate_packing_list(upload)
            
            if validation.valid and validation.preview:
                # Save to database
                pl_service = PackingListService(db)
                pl_create = PackingListCreate(
                    name=file.filename.replace('.csv', ''),
                    filename=file.filename,
                    rows=[PackingListRow(**r) for r in rows],
                    total_cartons=validation.preview.total_cartons,
                    total_weight_kg=validation.preview.total_weight_kg,
                    total_volume_cm3=validation.preview.total_volume_cm3,
                    shipment_type=validation.preview.shipment_type,
                    customer_count=validation.preview.customer_count,
                )
                saved_pl = pl_service.create(pl_create)
                
                return {
                    "success": True,
                    "packing_list_id": saved_pl.id,
                    "name": saved_pl.name,
                    "rows_parsed": len(rows),
                    "errors": errors,
                    "preview": validation.preview.model_dump()
                }
            else:
                return {
                    "success": False,
                    "rows_parsed": len(rows),
                    "errors": errors + ([e.message for e in validation.errors] if validation.errors else []),
                    "preview": validation.preview.model_dump() if validation.preview else None
                }
        except Exception as e:
            errors.append(f"Validation error: {str(e)}")
    
    return {
        "success": len(errors) == 0,
        "rows_parsed": len(rows),
        "errors": errors,
        "preview": None
    }


from datetime import datetime