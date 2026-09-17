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


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()