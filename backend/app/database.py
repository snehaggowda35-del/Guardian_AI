from datetime import datetime
from pathlib import Path
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
from .config import get_settings

settings = get_settings()

# Resolve relative SQLite URLs from the project root, not the shell's current
# directory. This keeps the dashboard, extension and test commands on the same
# database even when uvicorn is started from a different folder.
database_url = settings.database_url
if database_url.startswith("sqlite:///"):
    raw_path = database_url.removeprefix("sqlite:///")
    if raw_path.startswith("./"):
        raw_path = raw_path[2:]
    if not Path(raw_path).is_absolute():
        raw_path = str(Path(__file__).resolve().parents[2] / raw_path)
    database_url = "sqlite:///" + raw_path.replace("\\", "/")

engine = create_engine(database_url, connect_args={"check_same_thread": False} if database_url.startswith("sqlite") else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


class Parent(Base):
    __tablename__ = "parents"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    devices: Mapped[list["Device"]] = relationship(back_populates="parent")


class Device(Base):
    __tablename__ = "devices"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    parent_id: Mapped[int] = mapped_column(ForeignKey("parents.id"), index=True)
    label: Mapped[str] = mapped_column(String(100), default="Child browser")
    status: Mapped[str] = mapped_column(String(20), default="linked")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    parent: Mapped[Parent] = relationship(back_populates="devices")


class LinkCode(Base):
    __tablename__ = "link_codes"
    code: Mapped[str] = mapped_column(String(12), primary_key=True)
    parent_id: Mapped[int] = mapped_column(ForeignKey("parents.id"))
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used: Mapped[bool] = mapped_column(Boolean, default=False)


class RiskEvent(Base):
    __tablename__ = "risk_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"), index=True)
    source: Mapped[str] = mapped_column(String(30))
    category: Mapped[str] = mapped_column(String(40))
    severity: Mapped[str] = mapped_column(String(20))
    score: Mapped[int] = mapped_column(Integer)
    confidence: Mapped[float] = mapped_column(Float)
    trigger_text: Mapped[str] = mapped_column(Text)
    context_text: Mapped[str] = mapped_column(Text, default="[]")
    rationale: Mapped[str] = mapped_column(Text)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    decisions: Mapped[list["AgentDecision"]] = relationship(back_populates="event", cascade="all, delete-orphan")


class AgentDecision(Base):
    __tablename__ = "agent_decisions"
    id: Mapped[int] = mapped_column(primary_key=True)
    risk_event_id: Mapped[str] = mapped_column(ForeignKey("risk_events.id"))
    agent_name: Mapped[str] = mapped_column(String(50))
    decision: Mapped[str] = mapped_column(String(100))
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    event: Mapped[RiskEvent] = relationship(back_populates="decisions")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
