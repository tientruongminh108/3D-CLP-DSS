from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, CheckConstraint, event
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.pool import StaticPool
from datetime import datetime
from app.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
    poolclass=StaticPool if "sqlite" in settings.DATABASE_URL else None,
)

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if "sqlite" in settings.DATABASE_URL:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(String(50), unique=True, index=True, nullable=False)
    description = Column(String(200), nullable=False)
    length_cm = Column(Float, nullable=False)
    width_cm = Column(Float, nullable=False)
    height_cm = Column(Float, nullable=False)
    weight_kg = Column(Float, nullable=False)
    this_way_up = Column(Boolean, default=True, nullable=False)
    stacking_group = Column(Integer, default=1, nullable=False)
    max_load_bearing_kg = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint("length_cm > 0", name="item_length_positive"),
        CheckConstraint("width_cm > 0", name="item_width_positive"),
        CheckConstraint("height_cm > 0", name="item_height_positive"),
        CheckConstraint("weight_kg > 0", name="item_weight_positive"),
        CheckConstraint("stacking_group IN (1, 2)", name="item_stacking_group_valid"),
    )


class Container(Base):
    __tablename__ = "containers"

    id = Column(Integer, primary_key=True, index=True)
    container_type = Column(String(50), unique=True, index=True, nullable=False)
    internal_length_cm = Column(Float, nullable=False)
    internal_width_cm = Column(Float, nullable=False)
    internal_height_cm = Column(Float, nullable=False)
    max_weight_kg = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint("internal_length_cm > 0", name="container_length_positive"),
        CheckConstraint("internal_width_cm > 0", name="container_width_positive"),
        CheckConstraint("internal_height_cm > 0", name="container_height_positive"),
        CheckConstraint("max_weight_kg > 0", name="container_weight_positive"),
    )


class Run(Base):
    __tablename__ = "runs"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String(36), unique=True, index=True, nullable=False)
    container_id = Column(Integer, ForeignKey("containers.id", ondelete="CASCADE"), nullable=False)
    packing_list_json = Column(Text, nullable=False)
    options_json = Column(Text, nullable=True)
    status = Column(String(20), default="pending", nullable=False)
    result_json = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    container = relationship("Container")


class PackingList(Base):
    __tablename__ = "packing_lists"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    filename = Column(String(255), nullable=True)
    rows_json = Column(Text, nullable=False)
    preview_json = Column(Text, nullable=True)
    total_cartons = Column(Integer, default=0)
    total_weight_kg = Column(Float, default=0)
    total_volume_cm3 = Column(Float, default=0)
    shipment_type = Column(String(10), default="FCL")
    customer_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


def init_db():
    Base.metadata.create_all(bind=engine)


def seed_defaults(db_session=None):
    """Seed default container and items if database is empty."""
    db = db_session or SessionLocal()
    try:
        container_count = db.query(Container).count()
        if container_count == 0:
            default_container = Container(
                container_type="40ft High Cube (40HC)",
                internal_length_cm=1203.0,
                internal_width_cm=235.0,
                internal_height_cm=269.0,
                max_weight_kg=28620.0,
            )
            db.add(default_container)
            db.commit()

        item_count = db.query(Item).count()
        if item_count == 0:
            import os
            import pandas as pd
            csv_paths = [
                os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "item_master.csv"),
                os.path.join(os.path.dirname(__file__), "..", "..", "data", "item_master.csv"),
                "/app/data/item_master.csv",
            ]
            for p in csv_paths:
                p = os.path.abspath(p)
                if os.path.exists(p):
                    try:
                        df = pd.read_csv(p, encoding="utf-8-sig")
                        for _, row in df.iterrows():
                            val_twu = row.get("This_Way_Up", True)
                            twu = str(val_twu).strip().lower() in ["true", "yes", "1", "y", "t"] if pd.notna(val_twu) else True
                            val_sg = row.get("Stacking_Group", 1)
                            try:
                                sg = int(val_sg) if int(val_sg) in (1, 2) else 1
                            except Exception:
                                sg = 1
                            val_load = row.get("Max_Load_Bearing_kg", None)
                            max_load = None
                            if pd.notna(val_load) and str(val_load).strip() and str(val_load).strip().lower() not in ["nan", "none", "null", ""]:
                                try:
                                    max_load = float(val_load)
                                except Exception:
                                    max_load = None
                            item = Item(
                                item_id=str(row["Item_ID"]).strip(),
                                description=str(row["Description"]).strip(),
                                length_cm=float(row["Length_cm"]),
                                width_cm=float(row["Width_cm"]),
                                height_cm=float(row["Height_cm"]),
                                weight_kg=float(row["Weight_kg"]),
                                this_way_up=twu,
                                stacking_group=sg,
                                max_load_bearing_kg=max_load,
                            )
                            db.add(item)
                        db.commit()
                        break
                    except Exception:
                        db.rollback()
    except Exception:
        db.rollback()
    finally:
        if db_session is None:
            db.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()