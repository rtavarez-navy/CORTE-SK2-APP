"""Modelo mínimo para el piloto. Migraciones controladas antes de producción."""
from datetime import datetime, date, timezone
from sqlalchemy import ForeignKey, Integer, String, DateTime, Date, Boolean, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database import Base


def now_utc():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(220), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Workstation(Base):
    __tablename__ = "workstations"
    id: Mapped[int] = mapped_column(primary_key=True)
    laser_number: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    key_sha256: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class CPAOrder(Base):
    __tablename__ = "cpa_orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_number: Mapped[str] = mapped_column(String(32), nullable=False)
    line: Mapped[str] = mapped_column(String(12), nullable=False)
    max_pieces: Mapped[int] = mapped_column(Integer, nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (UniqueConstraint("order_number", "line", name="uq_cpa_order_line"),)


class Production(Base):
    __tablename__ = "production"
    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    cpa_order_id: Mapped[int] = mapped_column(ForeignKey("cpa_orders.id", ondelete="RESTRICT"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    workstation_id: Mapped[int] = mapped_column(ForeignKey("workstations.id"), nullable=False)
    shift: Mapped[str] = mapped_column(String(2), nullable=False)
    pieces: Mapped[int] = mapped_column(Integer, nullable=False)
    duplicate_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    business_date: Mapped[date] = mapped_column(Date, nullable=False)
    operator: Mapped[User] = relationship()
    workstation: Mapped[Workstation] = relationship()
    cpa_order: Mapped[CPAOrder] = relationship()
    __table_args__ = (Index("ix_production_cpa_order", "cpa_order_id"),
                      Index("ix_production_business_date", "business_date"))
