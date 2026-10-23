"""Team-owned product library and mobile collection persistence models."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin
from app.shared.identifiers import generate_id


class ProductLibraryGroup(TimestampMixin, Base):
    __tablename__ = "product_library_groups"
    __table_args__ = (
        UniqueConstraint("team_id", "normalized_name", name="uq_pl_group_team_name"),
        UniqueConstraint("group_id", "team_id", name="uq_pl_group_id_team"),
        CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),
        CheckConstraint("length(trim(normalized_name)) > 0", name="normalized_name_not_blank"),
        Index("ix_pl_group_team_archive_name", "team_id", "archived_at", "name", "group_id"),
    )

    group_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=generate_id)
    team_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("teams.team_id", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_by_user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=False,
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProductLibraryProduct(TimestampMixin, Base):
    __tablename__ = "product_library_products"
    __table_args__ = (
        UniqueConstraint(
            "team_id",
            "platform",
            "source_product_id",
            name="uq_pl_product_team_source",
        ),
        UniqueConstraint("product_id", "team_id", name="uq_pl_product_id_team"),
        ForeignKeyConstraint(
            ["group_id", "team_id"],
            ["product_library_groups.group_id", "product_library_groups.team_id"],
            name="fk_pl_product_group_team",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["adopted_version_id", "product_id", "team_id"],
            [
                "product_library_product_versions.version_id",
                "product_library_product_versions.product_id",
                "product_library_product_versions.team_id",
            ],
            name="fk_library_product_adopted_version",
            ondelete="RESTRICT",
            use_alter=True,
        ),
        CheckConstraint("platform IN ('douyin','pinduoduo')", name="platform"),
        CheckConstraint("length(trim(source_product_id)) > 0", name="source_product_id_not_blank"),
        CheckConstraint("manual_revision >= 0", name="manual_revision_non_negative"),
        CheckConstraint(
            "merchant_snapshot IS NULL OR jsonb_typeof(merchant_snapshot) = 'object'",
            name="merchant_snapshot_object",
        ),
        CheckConstraint(
            "category_path IS NULL OR jsonb_typeof(category_path) = 'array'",
            name="category_path_array",
        ),
        CheckConstraint(
            "current_sale_price_cent IS NULL OR current_sale_price_cent >= 0",
            name="sale_price_non_negative",
        ),
        Index(
            "ix_pl_product_team_group_updated",
            "team_id",
            "group_id",
            text("updated_at DESC"),
            "product_id",
        ),
        Index("ix_pl_product_team_title", "team_id", "title", "product_id"),
    )

    product_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=generate_id)
    team_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("teams.team_id", ondelete="RESTRICT"),
        nullable=False,
    )
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    source_product_id: Mapped[str] = mapped_column(String(128), nullable=False)
    group_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    adopted_version_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    title: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    primary_image_url: Mapped[str | None] = mapped_column(Text)
    merchant_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    category_path: Mapped[list[str] | None] = mapped_column(JSONB(none_as_null=True))
    current_sale_price_cent: Mapped[int | None] = mapped_column(BigInteger)
    currency: Mapped[str | None] = mapped_column(String(8))
    manual_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    last_applied_capture_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_ingested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=False,
    )


class ProductCollectionRequest(TimestampMixin, Base):
    __tablename__ = "product_collection_requests"
    __table_args__ = (
        UniqueConstraint(
            "team_id",
            "requested_by_user_id",
            "submission_key",
            name="uq_pc_request_actor_submission",
        ),
        UniqueConstraint("request_id", "team_id", name="uq_pc_request_id_team"),
        ForeignKeyConstraint(
            ["target_group_id", "team_id"],
            ["product_library_groups.group_id", "product_library_groups.team_id"],
            name="fk_pc_request_group_team",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "source_kind IN ('manual','selection_candidates')",
            name="source_kind",
        ),
        CheckConstraint(
            "status IN ('pending','running','partial','succeeded','failed','canceled')",
            name="status",
        ),
        CheckConstraint(
            "canonical_request_hash ~ '^[a-f0-9]{64}$'",
            name="canonical_hash",
        ),
        CheckConstraint("item_count > 0", name="item_count_positive"),
        CheckConstraint(
            "(cancel_requested_at IS NULL) = (cancel_requested_by_user_id IS NULL)",
            name="cancel_pair",
        ),
        CheckConstraint(
            "(status IN ('partial','succeeded','failed','canceled')) = (finished_at IS NOT NULL)",
            name="finished_terminal",
        ),
        Index("ix_pc_request_team_created", "team_id", text("created_at DESC"), "request_id"),
        Index("ix_pc_request_status_created", "status", "created_at", "request_id"),
    )

    request_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=generate_id)
    team_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("teams.team_id", ondelete="RESTRICT"),
        nullable=False,
    )
    requested_by_user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=False,
    )
    submission_key: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    target_group_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    canonical_request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    item_count: Mapped[int] = mapped_column(Integer, nullable=False)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_requested_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "users.user_id",
            name="fk_pc_request_cancel_actor",
            ondelete="RESTRICT",
        ),
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProductCollectionItem(TimestampMixin, Base):
    __tablename__ = "product_collection_items"
    __table_args__ = (
        UniqueConstraint(
            "request_id",
            "platform",
            "source_product_id",
            name="uq_pc_item_request_source",
        ),
        UniqueConstraint("item_id", "team_id", name="uq_pc_item_id_team"),
        ForeignKeyConstraint(
            ["request_id", "team_id"],
            ["product_collection_requests.request_id", "product_collection_requests.team_id"],
            name="fk_pc_item_request_team",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["candidate_id", "team_id"],
            ["product_selection_candidates.candidate_id", "product_selection_candidates.team_id"],
            name="fk_pc_item_candidate_team",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["target_group_id", "team_id"],
            ["product_library_groups.group_id", "product_library_groups.team_id"],
            name="fk_pc_item_group_team",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["library_product_id", "team_id"],
            ["product_library_products.product_id", "product_library_products.team_id"],
            name="fk_pc_item_product_team",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["current_dispatch_id", "item_id", "team_id"],
            [
                "product_collection_dispatches.dispatch_id",
                "product_collection_dispatches.item_id",
                "product_collection_dispatches.team_id",
            ],
            name="fk_collection_item_current_dispatch",
            ondelete="RESTRICT",
            use_alter=True,
        ),
        CheckConstraint(
            "(platform = 'douyin' AND collection_mode = 'auto_gateway') OR "
            "(platform = 'pinduoduo' AND collection_mode = 'manual_return')",
            name="platform_collection_mode",
        ),
        CheckConstraint("length(trim(source_product_id)) > 0", name="source_product_id_not_blank"),
        CheckConstraint(
            "state IN ('pending_dispatch','dispatching','dispatched','running','received',"
            "'processing','succeeded','failed','canceled')",
            name="state",
        ),
        CheckConstraint("attempt_count >= 0", name="attempt_count_non_negative"),
        CheckConstraint(
            "expected_manual_revision IS NULL OR expected_manual_revision >= 0",
            name="manual_revision_non_negative",
        ),
        CheckConstraint(
            "state <> 'succeeded' OR library_product_id IS NOT NULL",
            name="success_has_product",
        ),
        CheckConstraint(
            "(state IN ('succeeded','failed','canceled')) = (finished_at IS NOT NULL)",
            name="finished_terminal",
        ),
        Index("ix_pc_item_request_state", "request_id", "state", "item_id"),
        Index("ix_pc_item_team_state_created", "team_id", "state", "created_at", "item_id"),
    )

    item_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=generate_id)
    request_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    team_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    candidate_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    source_product_id: Mapped[str] = mapped_column(String(128), nullable=False)
    collection_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    target_group_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    current_dispatch_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    library_product_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    expected_manual_revision: Mapped[int | None] = mapped_column(Integer)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    last_error_code: Mapped[str | None] = mapped_column(String(96))
    last_error_stage: Mapped[str | None] = mapped_column(String(64))
    last_error_message: Mapped[str | None] = mapped_column(String(500))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProductCollectionDispatch(TimestampMixin, Base):
    __tablename__ = "product_collection_dispatches"
    __table_args__ = (
        ForeignKeyConstraint(
            ["item_id", "team_id"],
            ["product_collection_items.item_id", "product_collection_items.team_id"],
            name="fk_pc_dispatch_item_team",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("item_id", "dispatch_no", name="uq_pc_dispatch_item_no"),
        UniqueConstraint("dispatch_id", "team_id", name="uq_pc_dispatch_id_team"),
        UniqueConstraint(
            "dispatch_id",
            "gateway_id",
            "team_id",
            name="uq_pc_dispatch_gateway_team",
        ),
        UniqueConstraint(
            "dispatch_id",
            "item_id",
            "team_id",
            name="uq_pc_dispatch_item_team",
        ),
        UniqueConstraint("gateway_id", "external_job_id", name="uq_pc_dispatch_external_job"),
        UniqueConstraint("gateway_id", "gateway_job_id", name="uq_pc_dispatch_gateway_job"),
        Index(
            "uq_pc_dispatch_active_item",
            "item_id",
            unique=True,
            postgresql_where=text(
                "state IN ('pending_delivery','delivering','dispatched','running')",
            ),
        ),
        Index(
            "ix_pc_dispatch_claim",
            "state",
            "next_attempt_at",
            "created_at",
            "dispatch_id",
        ),
        CheckConstraint("dispatch_no > 0", name="dispatch_no_positive"),
        CheckConstraint("delivery_attempts >= 0", name="delivery_attempts_non_negative"),
        CheckConstraint("canonical_payload_hash ~ '^[a-f0-9]{64}$'", name="payload_hash"),
        CheckConstraint(
            "state IN ('pending_delivery','delivering','dispatched','running','completed',"
            "'delivery_failed','execution_failed','canceled')",
            name="state",
        ),
        CheckConstraint(
            "(state = 'delivering') = (lease_id IS NOT NULL AND lease_expires_at IS NOT NULL)",
            name="delivery_lease",
        ),
        CheckConstraint(
            "state IN ('delivering','running') OR last_heartbeat_at IS NULL OR finished_at IS NOT NULL",
            name="heartbeat_state",
        ),
        CheckConstraint(
            "state NOT IN ('dispatched','running','completed','execution_failed') "
            "OR gateway_job_id IS NOT NULL",
            name="gateway_job_required",
        ),
        CheckConstraint(
            "(state IN ('completed','delivery_failed','execution_failed','canceled')) "
            "= (finished_at IS NOT NULL)",
            name="finished_terminal",
        ),
    )

    dispatch_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=generate_id)
    item_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    team_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    dispatch_no: Mapped[int] = mapped_column(Integer, nullable=False)
    external_job_id: Mapped[str] = mapped_column(String(128), nullable=False)
    canonical_payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    gateway_id: Mapped[str] = mapped_column(String(128), nullable=False)
    gateway_job_id: Mapped[str | None] = mapped_column(String(128))
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    delivery_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(96))
    last_error_stage: Mapped[str | None] = mapped_column(String(64))
    last_error_message: Mapped[str | None] = mapped_column(String(500))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProductCollectionCaptureAttempt(TimestampMixin, Base):
    __tablename__ = "product_collection_capture_attempts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["dispatch_id", "gateway_id", "team_id"],
            [
                "product_collection_dispatches.dispatch_id",
                "product_collection_dispatches.gateway_id",
                "product_collection_dispatches.team_id",
            ],
            name="fk_pc_attempt_dispatch_gateway_team",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("attempt_id", "team_id", name="uq_pc_attempt_id_team"),
        UniqueConstraint(
            "gateway_id",
            "gateway_job_id",
            "capture_batch_id",
            name="uq_pc_attempt_gateway_batch",
        ),
        UniqueConstraint("dispatch_id", "attempt_no", name="uq_pc_attempt_dispatch_no"),
        UniqueConstraint("ingest_credential_id", name="uq_pc_attempt_credential"),
        Index(
            "uq_pc_attempt_active_dispatch",
            "dispatch_id",
            unique=True,
            postgresql_where=text("state IN ('registered','running','received','processing')"),
        ),
        Index("ix_pc_attempt_lease", "state", "lease_expires_at", "attempt_id"),
        CheckConstraint("attempt_no > 0", name="attempt_no_positive"),
        CheckConstraint("ingest_credential_version > 0", name="credential_version"),
        CheckConstraint("ingest_token_salt ~ '^[a-f0-9]{32}$'", name="token_salt"),
        CheckConstraint("ingest_token_hash ~ '^[a-f0-9]{64}$'", name="token_hash"),
        CheckConstraint(
            "accepted_content_sha256 IS NULL OR accepted_content_sha256 ~ '^[a-f0-9]{64}$'",
            name="content_hash",
        ),
        CheckConstraint(
            "state IN ('registered','running','received','processing','persisted','failed',"
            "'superseded','canceled')",
            name="state",
        ),
        CheckConstraint(
            "token_issued_at <= token_expires_at AND token_expires_at <= accept_until",
            name="credential_times",
        ),
        CheckConstraint(
            "(token_consumed_at IS NULL) = (accepted_content_sha256 IS NULL)",
            name="consumed_content_pair",
        ),
        CheckConstraint(
            "state NOT IN ('received','processing','persisted') OR "
            "(token_consumed_at IS NOT NULL AND accepted_content_sha256 IS NOT NULL)",
            name="received_consumed",
        ),
        CheckConstraint(
            "(state IN ('persisted','failed','superseded','canceled')) = (finished_at IS NOT NULL)",
            name="finished_terminal",
        ),
    )

    attempt_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=generate_id)
    dispatch_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    gateway_id: Mapped[str] = mapped_column(String(128), nullable=False)
    team_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    gateway_device_id: Mapped[str] = mapped_column(String(128), nullable=False)
    gateway_job_id: Mapped[str] = mapped_column(String(128), nullable=False)
    capture_batch_id: Mapped[str] = mapped_column(String(128), nullable=False)
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    ingest_credential_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    ingest_credential_version: Mapped[int] = mapped_column(Integer, nullable=False)
    ingest_token_key_id: Mapped[str] = mapped_column(String(128), nullable=False)
    ingest_token_salt: Mapped[str] = mapped_column(String(32), nullable=False)
    ingest_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    token_issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    token_consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    token_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accept_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_content_sha256: Mapped[str | None] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(96))
    last_error_stage: Mapped[str | None] = mapped_column(String(64))
    last_error_message: Mapped[str | None] = mapped_column(String(500))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProductCollectionUploadReceipt(TimestampMixin, Base):
    __tablename__ = "product_collection_upload_receipts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["attempt_id", "team_id"],
            [
                "product_collection_capture_attempts.attempt_id",
                "product_collection_capture_attempts.team_id",
            ],
            name="fk_pc_upload_attempt_team",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("attempt_id", name="uq_pc_upload_attempt"),
        UniqueConstraint("upload_key", name="uq_pc_upload_key"),
        UniqueConstraint("upload_receipt_id", "team_id", name="uq_pc_upload_id_team"),
        CheckConstraint("content_sha256 ~ '^[a-f0-9]{64}$'", name="content_hash"),
        CheckConstraint("jsonb_typeof(raw_payload) = 'object'", name="raw_payload_object"),
        CheckConstraint("raw_format_version > 0", name="raw_version"),
        CheckConstraint(
            "state IN ('received','processing','persisted','failed','superseded')",
            name="state",
        ),
        CheckConstraint("processing_attempts >= 0", name="processing_attempts"),
        CheckConstraint(
            "(state = 'processing') = (lease_id IS NOT NULL AND lease_expires_at IS NOT NULL)",
            name="processing_lease",
        ),
        CheckConstraint(
            "(state IN ('persisted','failed','superseded')) = (processed_at IS NOT NULL)",
            name="processed_terminal",
        ),
        CheckConstraint(
            "processing_next_attempt_at IS NULL OR state = 'received'",
            name="processing_retry_state",
        ),
        CheckConstraint(
            "gateway_settlement_state IS NULL OR "
            "gateway_settlement_state IN ('pending','delivering','settled','failed')",
            name="settlement_state",
        ),
        CheckConstraint(
            "(state IN ('persisted','failed','superseded')) = "
            "(gateway_settlement_state IS NOT NULL)",
            name="terminal_has_settlement",
        ),
        CheckConstraint(
            "gateway_settlement_attempts >= 0",
            name="settlement_attempts",
        ),
        CheckConstraint(
            "(gateway_settlement_state = 'settled' AND settled_at IS NOT NULL) OR "
            "(gateway_settlement_state IS DISTINCT FROM 'settled' AND settled_at IS NULL)",
            name="settled_pair",
        ),
        CheckConstraint(
            "gateway_settlement_state <> 'settled' OR "
            "(next_attempt_at IS NULL AND settlement_error_code IS NULL "
            "AND settlement_error_message IS NULL)",
            name="settled_clean",
        ),
        CheckConstraint(
            "gateway_settlement_state <> 'failed' OR settlement_error_code IS NOT NULL",
            name="settlement_failed_error",
        ),
        CheckConstraint(
            "next_attempt_at IS NULL OR gateway_settlement_state IS NOT DISTINCT FROM 'failed'",
            name="settlement_retry_state",
        ),
        Index(
            "ix_pc_upload_claim",
            "state",
            "processing_next_attempt_at",
            "received_at",
            "upload_receipt_id",
        ),
        Index(
            "ix_pc_upload_settlement",
            "gateway_settlement_state",
            "next_attempt_at",
            "upload_receipt_id",
        ),
    )

    upload_receipt_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=generate_id,
    )
    team_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    attempt_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    upload_key: Mapped[str] = mapped_column(String(160), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    raw_format_version: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    processing_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    processing_next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(96))
    last_error_stage: Mapped[str | None] = mapped_column(String(64))
    last_error_message: Mapped[str | None] = mapped_column(String(500))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    gateway_settlement_state: Mapped[str | None] = mapped_column(String(32))
    gateway_settlement_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    settlement_error_code: Mapped[str | None] = mapped_column(String(96))
    settlement_error_message: Mapped[str | None] = mapped_column(String(500))


class ProductLibraryProductVersion(TimestampMixin, Base):
    __tablename__ = "product_library_product_versions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["product_id", "team_id"],
            ["product_library_products.product_id", "product_library_products.team_id"],
            name="fk_pl_version_product_team",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["upload_receipt_id", "team_id"],
            [
                "product_collection_upload_receipts.upload_receipt_id",
                "product_collection_upload_receipts.team_id",
            ],
            name="fk_pl_version_upload_team",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("upload_receipt_id", name="uq_pl_version_upload"),
        UniqueConstraint(
            "version_id",
            "product_id",
            "team_id",
            name="uq_pl_version_id_product_team",
        ),
        CheckConstraint("raw_content_sha256 ~ '^[a-f0-9]{64}$'", name="raw_content_hash"),
        CheckConstraint("jsonb_typeof(uu_snapshot) = 'object'", name="uu_snapshot_object"),
        CheckConstraint("jsonb_typeof(price_evidence) = 'object'", name="price_evidence_object"),
        CheckConstraint("source_format_version > 0", name="source_version"),
        CheckConstraint("length(trim(cleaner_version)) > 0", name="cleaner_version_not_blank"),
        Index(
            "ix_pl_version_product_captured",
            "product_id",
            text("captured_at DESC"),
            "version_id",
        ),
    )

    version_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=generate_id)
    product_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    team_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    upload_receipt_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_format_version: Mapped[int] = mapped_column(Integer, nullable=False)
    cleaner_version: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    uu_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    price_evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ProductCollectionPersistReceipt(TimestampMixin, Base):
    __tablename__ = "product_collection_persist_receipts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["upload_receipt_id", "team_id"],
            [
                "product_collection_upload_receipts.upload_receipt_id",
                "product_collection_upload_receipts.team_id",
            ],
            name="fk_pc_persist_upload_team",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["product_id", "team_id"],
            ["product_library_products.product_id", "product_library_products.team_id"],
            name="fk_pc_persist_product_team",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["version_id", "product_id", "team_id"],
            [
                "product_library_product_versions.version_id",
                "product_library_product_versions.product_id",
                "product_library_product_versions.team_id",
            ],
            name="fk_pc_persist_version_product_team",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("upload_receipt_id", name="uq_pc_persist_upload"),
        UniqueConstraint("version_id", name="uq_pc_persist_version"),
        CheckConstraint(
            "outcome IN ('applied','not_applied','superseded')",
            name="outcome",
        ),
        CheckConstraint("applied = (outcome = 'applied')", name="applied_outcome"),
    )

    persist_receipt_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=generate_id,
    )
    team_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    upload_receipt_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    product_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    version_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    applied: Mapped[bool] = mapped_column(Boolean, nullable=False)
    persisted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
