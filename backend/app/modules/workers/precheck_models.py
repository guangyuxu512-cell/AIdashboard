"""Non-sensitive local shop inventory and stable application task identity."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class WorkerRpaShopInventory(Base):
    __tablename__ = "worker_rpa_shop_inventories"
    __table_args__ = (
        CheckConstraint("jsonb_typeof(shops) = 'array'", name="worker_rpa_shops_array"),
        CheckConstraint("jsonb_array_length(shops) <= 500", name="worker_rpa_shops_limit"),
        CheckConstraint("NOT available OR installation_id IS NOT NULL", name="worker_rpa_available_installation"),
    )
    device_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("devices.device_id", ondelete="RESTRICT"), primary_key=True)
    installation_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    shops: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    last_discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ApplicationWorkerPrecheck(Base):
    __tablename__ = "application_worker_prechecks"
    __table_args__ = (
        UniqueConstraint("task_id", name="uq_application_worker_prechecks_task"),
        CheckConstraint("length(trim(product_id)) > 0", name="precheck_product_not_blank"),
        CheckConstraint("revision > 0", name="precheck_revision_positive"),
        CheckConstraint("request_hash ~ '^[0-9a-f]{64}$'", name="precheck_request_hash"),
    )
    client_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    product_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    task_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("tasks.task_id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
