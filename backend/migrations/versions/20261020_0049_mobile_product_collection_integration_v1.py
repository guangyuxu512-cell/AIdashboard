"""Add Team product library and durable mobile collection receipts.

Revision ID: 20261020_0049
Revises: 20261019_0048
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261020_0049"
down_revision = "20261019_0048"
branch_labels = None
depends_on = None

FEATURE_DATABASE = "control_center_feat_mobile_product_collection_integration"
FEATURE_TABLES = (
    "product_collection_persist_receipts",
    "product_library_product_versions",
    "product_collection_upload_receipts",
    "product_collection_capture_attempts",
    "product_collection_dispatches",
    "product_collection_items",
    "product_collection_requests",
    "product_library_products",
    "product_library_groups",
)


def _timestamps():
    return [
        sa.Column(
            name,
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        )
        for name in ("created_at", "updated_at")
    ]


def _scalar(connection, statement: str):
    return connection.scalar(sa.text(statement))


def upgrade():
    op.create_unique_constraint(
        "uq_selection_candidate_id_team",
        "product_selection_candidates",
        ["candidate_id", "team_id"],
    )

    op.create_table(
        "product_library_groups",
        sa.Column("group_id", sa.Uuid(), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("normalized_name", sa.String(120), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("group_id"),
        sa.ForeignKeyConstraint(
            ["team_id"],
            ["teams.team_id"],
            name="fk_product_library_groups_team_id_teams",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.user_id"],
            name="fk_product_library_groups_created_by_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("team_id", "normalized_name", name="uq_pl_group_team_name"),
        sa.UniqueConstraint("group_id", "team_id", name="uq_pl_group_id_team"),
        sa.CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),
        sa.CheckConstraint(
            "length(trim(normalized_name)) > 0",
            name="normalized_name_not_blank",
        ),
    )
    op.create_index(
        "ix_pl_group_team_archive_name",
        "product_library_groups",
        ["team_id", "archived_at", "name", "group_id"],
    )

    op.create_table(
        "product_library_products",
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("source_product_id", sa.String(128), nullable=False),
        sa.Column("group_id", sa.Uuid(), nullable=True),
        sa.Column("adopted_version_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("primary_image_url", sa.Text(), nullable=True),
        sa.Column("merchant_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column("category_path", postgresql.JSONB(), nullable=True),
        sa.Column("current_sale_price_cent", sa.BigInteger(), nullable=True),
        sa.Column("currency", sa.String(8), nullable=True),
        sa.Column("manual_revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_applied_capture_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_ingested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("product_id"),
        sa.ForeignKeyConstraint(
            ["team_id"],
            ["teams.team_id"],
            name="fk_product_library_products_team_id_teams",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.user_id"],
            name="fk_product_library_products_created_by_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["group_id", "team_id"],
            ["product_library_groups.group_id", "product_library_groups.team_id"],
            name="fk_pl_product_group_team",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "team_id",
            "platform",
            "source_product_id",
            name="uq_pl_product_team_source",
        ),
        sa.UniqueConstraint("product_id", "team_id", name="uq_pl_product_id_team"),
        sa.CheckConstraint("platform IN ('douyin','pinduoduo')", name="platform"),
        sa.CheckConstraint(
            "length(trim(source_product_id)) > 0",
            name="source_product_id_not_blank",
        ),
        sa.CheckConstraint("manual_revision >= 0", name="manual_revision_non_negative"),
        sa.CheckConstraint(
            "merchant_snapshot IS NULL OR jsonb_typeof(merchant_snapshot) = 'object'",
            name="merchant_snapshot_object",
        ),
        sa.CheckConstraint(
            "category_path IS NULL OR jsonb_typeof(category_path) = 'array'",
            name="category_path_array",
        ),
        sa.CheckConstraint(
            "current_sale_price_cent IS NULL OR current_sale_price_cent >= 0",
            name="sale_price_non_negative",
        ),
    )
    op.create_index(
        "ix_pl_product_team_group_updated",
        "product_library_products",
        ["team_id", "group_id", sa.text("updated_at DESC"), "product_id"],
    )
    op.create_index(
        "ix_pl_product_team_title",
        "product_library_products",
        ["team_id", "title", "product_id"],
    )

    op.create_table(
        "product_collection_requests",
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("submission_key", sa.Uuid(), nullable=False),
        sa.Column("source_kind", sa.String(32), nullable=False),
        sa.Column("target_group_id", sa.Uuid(), nullable=True),
        sa.Column("canonical_request_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("item_count", sa.Integer(), nullable=False),
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_requested_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("request_id"),
        sa.ForeignKeyConstraint(
            ["team_id"],
            ["teams.team_id"],
            name="fk_product_collection_requests_team_id_teams",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_user_id"],
            ["users.user_id"],
            name="fk_product_collection_requests_requested_by_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["cancel_requested_by_user_id"],
            ["users.user_id"],
            name="fk_pc_request_cancel_actor",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["target_group_id", "team_id"],
            ["product_library_groups.group_id", "product_library_groups.team_id"],
            name="fk_pc_request_group_team",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "team_id",
            "requested_by_user_id",
            "submission_key",
            name="uq_pc_request_actor_submission",
        ),
        sa.UniqueConstraint("request_id", "team_id", name="uq_pc_request_id_team"),
        sa.CheckConstraint(
            "source_kind IN ('manual','selection_candidates')",
            name="source_kind",
        ),
        sa.CheckConstraint(
            "status IN ('pending','running','partial','succeeded','failed','canceled')",
            name="status",
        ),
        sa.CheckConstraint(
            "canonical_request_hash ~ '^[a-f0-9]{64}$'",
            name="canonical_hash",
        ),
        sa.CheckConstraint("item_count > 0", name="item_count_positive"),
        sa.CheckConstraint(
            "(cancel_requested_at IS NULL) = (cancel_requested_by_user_id IS NULL)",
            name="cancel_pair",
        ),
        sa.CheckConstraint(
            "(status IN ('partial','succeeded','failed','canceled')) = "
            "(finished_at IS NOT NULL)",
            name="finished_terminal",
        ),
    )
    op.create_index(
        "ix_pc_request_team_created",
        "product_collection_requests",
        ["team_id", sa.text("created_at DESC"), "request_id"],
    )
    op.create_index(
        "ix_pc_request_status_created",
        "product_collection_requests",
        ["status", "created_at", "request_id"],
    )

    op.create_table(
        "product_collection_items",
        sa.Column("item_id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=True),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("source_product_id", sa.String(128), nullable=False),
        sa.Column("collection_mode", sa.String(32), nullable=False),
        sa.Column("target_group_id", sa.Uuid(), nullable=True),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("current_dispatch_id", sa.Uuid(), nullable=True),
        sa.Column("library_product_id", sa.Uuid(), nullable=True),
        sa.Column("expected_manual_revision", sa.Integer(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error_code", sa.String(96), nullable=True),
        sa.Column("last_error_stage", sa.String(64), nullable=True),
        sa.Column("last_error_message", sa.String(500), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("item_id"),
        sa.ForeignKeyConstraint(
            ["request_id", "team_id"],
            ["product_collection_requests.request_id", "product_collection_requests.team_id"],
            name="fk_pc_item_request_team",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id", "team_id"],
            ["product_selection_candidates.candidate_id", "product_selection_candidates.team_id"],
            name="fk_pc_item_candidate_team",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["target_group_id", "team_id"],
            ["product_library_groups.group_id", "product_library_groups.team_id"],
            name="fk_pc_item_group_team",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["library_product_id", "team_id"],
            ["product_library_products.product_id", "product_library_products.team_id"],
            name="fk_pc_item_product_team",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "request_id",
            "platform",
            "source_product_id",
            name="uq_pc_item_request_source",
        ),
        sa.UniqueConstraint("item_id", "team_id", name="uq_pc_item_id_team"),
        sa.CheckConstraint(
            "(platform = 'douyin' AND collection_mode = 'auto_gateway') OR "
            "(platform = 'pinduoduo' AND collection_mode = 'manual_return')",
            name="platform_collection_mode",
        ),
        sa.CheckConstraint(
            "length(trim(source_product_id)) > 0",
            name="source_product_id_not_blank",
        ),
        sa.CheckConstraint(
            "state IN ('pending_dispatch','dispatching','dispatched','running','received',"
            "'processing','succeeded','failed','canceled')",
            name="state",
        ),
        sa.CheckConstraint("attempt_count >= 0", name="attempt_count_non_negative"),
        sa.CheckConstraint(
            "expected_manual_revision IS NULL OR expected_manual_revision >= 0",
            name="manual_revision_non_negative",
        ),
        sa.CheckConstraint(
            "state <> 'succeeded' OR library_product_id IS NOT NULL",
            name="success_has_product",
        ),
        sa.CheckConstraint(
            "(state IN ('succeeded','failed','canceled')) = (finished_at IS NOT NULL)",
            name="finished_terminal",
        ),
    )
    op.create_index(
        "ix_pc_item_request_state",
        "product_collection_items",
        ["request_id", "state", "item_id"],
    )
    op.create_index(
        "ix_pc_item_team_state_created",
        "product_collection_items",
        ["team_id", "state", "created_at", "item_id"],
    )

    op.create_table(
        "product_collection_dispatches",
        sa.Column("dispatch_id", sa.Uuid(), nullable=False),
        sa.Column("item_id", sa.Uuid(), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("dispatch_no", sa.Integer(), nullable=False),
        sa.Column("external_job_id", sa.String(128), nullable=False),
        sa.Column("canonical_payload_hash", sa.String(64), nullable=False),
        sa.Column("gateway_id", sa.String(128), nullable=False),
        sa.Column("gateway_job_id", sa.String(128), nullable=True),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("delivery_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_id", sa.Uuid(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(96), nullable=True),
        sa.Column("last_error_stage", sa.String(64), nullable=True),
        sa.Column("last_error_message", sa.String(500), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("dispatch_id"),
        sa.ForeignKeyConstraint(
            ["item_id", "team_id"],
            ["product_collection_items.item_id", "product_collection_items.team_id"],
            name="fk_pc_dispatch_item_team",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("item_id", "dispatch_no", name="uq_pc_dispatch_item_no"),
        sa.UniqueConstraint("dispatch_id", "team_id", name="uq_pc_dispatch_id_team"),
        sa.UniqueConstraint(
            "dispatch_id",
            "gateway_id",
            "team_id",
            name="uq_pc_dispatch_gateway_team",
        ),
        sa.UniqueConstraint(
            "dispatch_id",
            "item_id",
            "team_id",
            name="uq_pc_dispatch_item_team",
        ),
        sa.UniqueConstraint(
            "gateway_id",
            "external_job_id",
            name="uq_pc_dispatch_external_job",
        ),
        sa.UniqueConstraint(
            "gateway_id",
            "gateway_job_id",
            name="uq_pc_dispatch_gateway_job",
        ),
        sa.CheckConstraint("dispatch_no > 0", name="dispatch_no_positive"),
        sa.CheckConstraint(
            "delivery_attempts >= 0",
            name="delivery_attempts_non_negative",
        ),
        sa.CheckConstraint(
            "canonical_payload_hash ~ '^[a-f0-9]{64}$'",
            name="payload_hash",
        ),
        sa.CheckConstraint(
            "state IN ('pending_delivery','delivering','dispatched','running','completed',"
            "'delivery_failed','execution_failed','canceled')",
            name="state",
        ),
        sa.CheckConstraint(
            "(state = 'delivering') = (lease_id IS NOT NULL AND lease_expires_at IS NOT NULL)",
            name="delivery_lease",
        ),
        sa.CheckConstraint(
            "state IN ('delivering','running') OR last_heartbeat_at IS NULL OR finished_at IS NOT NULL",
            name="heartbeat_state",
        ),
        sa.CheckConstraint(
            "state NOT IN ('dispatched','running','completed','execution_failed') "
            "OR gateway_job_id IS NOT NULL",
            name="gateway_job_required",
        ),
        sa.CheckConstraint(
            "(state IN ('completed','delivery_failed','execution_failed','canceled')) "
            "= (finished_at IS NOT NULL)",
            name="finished_terminal",
        ),
    )
    op.create_index(
        "uq_pc_dispatch_active_item",
        "product_collection_dispatches",
        ["item_id"],
        unique=True,
        postgresql_where=sa.text(
            "state IN ('pending_delivery','delivering','dispatched','running')",
        ),
    )
    op.create_index(
        "ix_pc_dispatch_claim",
        "product_collection_dispatches",
        ["state", "next_attempt_at", "created_at", "dispatch_id"],
    )

    op.create_table(
        "product_collection_capture_attempts",
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("dispatch_id", sa.Uuid(), nullable=False),
        sa.Column("gateway_id", sa.String(128), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("gateway_device_id", sa.String(128), nullable=False),
        sa.Column("gateway_job_id", sa.String(128), nullable=False),
        sa.Column("capture_batch_id", sa.String(128), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("ingest_credential_id", sa.Uuid(), nullable=False),
        sa.Column("ingest_credential_version", sa.Integer(), nullable=False),
        sa.Column("ingest_token_key_id", sa.String(128), nullable=False),
        sa.Column("ingest_token_salt", sa.String(32), nullable=False),
        sa.Column("ingest_token_hash", sa.String(64), nullable=False),
        sa.Column("token_issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("token_consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accept_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_content_sha256", sa.String(64), nullable=True),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(96), nullable=True),
        sa.Column("last_error_stage", sa.String(64), nullable=True),
        sa.Column("last_error_message", sa.String(500), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("attempt_id"),
        sa.ForeignKeyConstraint(
            ["dispatch_id", "gateway_id", "team_id"],
            [
                "product_collection_dispatches.dispatch_id",
                "product_collection_dispatches.gateway_id",
                "product_collection_dispatches.team_id",
            ],
            name="fk_pc_attempt_dispatch_gateway_team",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("attempt_id", "team_id", name="uq_pc_attempt_id_team"),
        sa.UniqueConstraint(
            "gateway_id",
            "gateway_job_id",
            "capture_batch_id",
            name="uq_pc_attempt_gateway_batch",
        ),
        sa.UniqueConstraint("dispatch_id", "attempt_no", name="uq_pc_attempt_dispatch_no"),
        sa.UniqueConstraint("ingest_credential_id", name="uq_pc_attempt_credential"),
        sa.CheckConstraint("attempt_no > 0", name="attempt_no_positive"),
        sa.CheckConstraint(
            "ingest_credential_version > 0",
            name="credential_version",
        ),
        sa.CheckConstraint("ingest_token_salt ~ '^[a-f0-9]{32}$'", name="token_salt"),
        sa.CheckConstraint("ingest_token_hash ~ '^[a-f0-9]{64}$'", name="token_hash"),
        sa.CheckConstraint(
            "accepted_content_sha256 IS NULL OR "
            "accepted_content_sha256 ~ '^[a-f0-9]{64}$'",
            name="content_hash",
        ),
        sa.CheckConstraint(
            "state IN ('registered','running','received','processing','persisted','failed',"
            "'superseded','canceled')",
            name="state",
        ),
        sa.CheckConstraint(
            "token_issued_at <= token_expires_at AND token_expires_at <= accept_until",
            name="credential_times",
        ),
        sa.CheckConstraint(
            "(token_consumed_at IS NULL) = (accepted_content_sha256 IS NULL)",
            name="consumed_content_pair",
        ),
        sa.CheckConstraint(
            "state NOT IN ('received','processing','persisted') OR "
            "(token_consumed_at IS NOT NULL AND accepted_content_sha256 IS NOT NULL)",
            name="received_consumed",
        ),
        sa.CheckConstraint(
            "(state IN ('persisted','failed','superseded','canceled')) "
            "= (finished_at IS NOT NULL)",
            name="finished_terminal",
        ),
    )
    op.create_index(
        "uq_pc_attempt_active_dispatch",
        "product_collection_capture_attempts",
        ["dispatch_id"],
        unique=True,
        postgresql_where=sa.text(
            "state IN ('registered','running','received','processing')",
        ),
    )
    op.create_index(
        "ix_pc_attempt_lease",
        "product_collection_capture_attempts",
        ["state", "lease_expires_at", "attempt_id"],
    )

    op.create_table(
        "product_collection_upload_receipts",
        sa.Column("upload_receipt_id", sa.Uuid(), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("upload_key", sa.String(160), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("raw_payload", postgresql.JSONB(), nullable=False),
        sa.Column("raw_format_version", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("processing_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processing_next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_id", sa.Uuid(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(96), nullable=True),
        sa.Column("last_error_stage", sa.String(64), nullable=True),
        sa.Column("last_error_message", sa.String(500), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("gateway_settlement_state", sa.String(32), nullable=True),
        sa.Column("gateway_settlement_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("settlement_error_code", sa.String(96), nullable=True),
        sa.Column("settlement_error_message", sa.String(500), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("upload_receipt_id"),
        sa.ForeignKeyConstraint(
            ["attempt_id", "team_id"],
            [
                "product_collection_capture_attempts.attempt_id",
                "product_collection_capture_attempts.team_id",
            ],
            name="fk_pc_upload_attempt_team",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("attempt_id", name="uq_pc_upload_attempt"),
        sa.UniqueConstraint("upload_key", name="uq_pc_upload_key"),
        sa.UniqueConstraint(
            "upload_receipt_id",
            "team_id",
            name="uq_pc_upload_id_team",
        ),
        sa.CheckConstraint("content_sha256 ~ '^[a-f0-9]{64}$'", name="content_hash"),
        sa.CheckConstraint("jsonb_typeof(raw_payload) = 'object'", name="raw_payload_object"),
        sa.CheckConstraint(
            "raw_format_version > 0",
            name="raw_version",
        ),
        sa.CheckConstraint(
            "state IN ('received','processing','persisted','failed','superseded')",
            name="state",
        ),
        sa.CheckConstraint(
            "processing_attempts >= 0",
            name="processing_attempts",
        ),
        sa.CheckConstraint(
            "(state = 'processing') = (lease_id IS NOT NULL AND lease_expires_at IS NOT NULL)",
            name="processing_lease",
        ),
        sa.CheckConstraint(
            "(state IN ('persisted','failed','superseded')) = (processed_at IS NOT NULL)",
            name="processed_terminal",
        ),
        sa.CheckConstraint(
            "processing_next_attempt_at IS NULL OR state = 'received'",
            name="processing_retry_state",
        ),
        sa.CheckConstraint(
            "gateway_settlement_state IS NULL OR "
            "gateway_settlement_state IN ('pending','delivering','settled','failed')",
            name="settlement_state",
        ),
        sa.CheckConstraint(
            "(state IN ('persisted','failed','superseded')) = "
            "(gateway_settlement_state IS NOT NULL)",
            name="terminal_has_settlement",
        ),
        sa.CheckConstraint(
            "gateway_settlement_attempts >= 0",
            name="settlement_attempts",
        ),
        sa.CheckConstraint(
            "(gateway_settlement_state = 'settled' AND settled_at IS NOT NULL) OR "
            "(gateway_settlement_state IS DISTINCT FROM 'settled' AND settled_at IS NULL)",
            name="settled_pair",
        ),
        sa.CheckConstraint(
            "gateway_settlement_state <> 'settled' OR "
            "(next_attempt_at IS NULL AND settlement_error_code IS NULL "
            "AND settlement_error_message IS NULL)",
            name="settled_clean",
        ),
        sa.CheckConstraint(
            "gateway_settlement_state <> 'failed' OR settlement_error_code IS NOT NULL",
            name="settlement_failed_error",
        ),
        sa.CheckConstraint(
            "next_attempt_at IS NULL OR gateway_settlement_state IS NOT DISTINCT FROM 'failed'",
            name="settlement_retry_state",
        ),
    )
    op.create_index(
        "ix_pc_upload_claim",
        "product_collection_upload_receipts",
        ["state", "processing_next_attempt_at", "received_at", "upload_receipt_id"],
    )
    op.create_index(
        "ix_pc_upload_settlement",
        "product_collection_upload_receipts",
        ["gateway_settlement_state", "next_attempt_at", "upload_receipt_id"],
    )

    op.create_table(
        "product_library_product_versions",
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("upload_receipt_id", sa.Uuid(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_format_version", sa.Integer(), nullable=False),
        sa.Column("cleaner_version", sa.String(64), nullable=False),
        sa.Column("raw_content_sha256", sa.String(64), nullable=False),
        sa.Column("uu_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("price_evidence", postgresql.JSONB(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("version_id"),
        sa.ForeignKeyConstraint(
            ["product_id", "team_id"],
            ["product_library_products.product_id", "product_library_products.team_id"],
            name="fk_pl_version_product_team",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["upload_receipt_id", "team_id"],
            [
                "product_collection_upload_receipts.upload_receipt_id",
                "product_collection_upload_receipts.team_id",
            ],
            name="fk_pl_version_upload_team",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("upload_receipt_id", name="uq_pl_version_upload"),
        sa.UniqueConstraint(
            "version_id",
            "product_id",
            "team_id",
            name="uq_pl_version_id_product_team",
        ),
        sa.CheckConstraint(
            "raw_content_sha256 ~ '^[a-f0-9]{64}$'",
            name="raw_content_hash",
        ),
        sa.CheckConstraint("jsonb_typeof(uu_snapshot) = 'object'", name="uu_snapshot_object"),
        sa.CheckConstraint(
            "jsonb_typeof(price_evidence) = 'object'",
            name="price_evidence_object",
        ),
        sa.CheckConstraint(
            "source_format_version > 0",
            name="source_version",
        ),
        sa.CheckConstraint(
            "length(trim(cleaner_version)) > 0",
            name="cleaner_version_not_blank",
        ),
    )
    op.create_index(
        "ix_pl_version_product_captured",
        "product_library_product_versions",
        ["product_id", sa.text("captured_at DESC"), "version_id"],
    )

    op.create_table(
        "product_collection_persist_receipts",
        sa.Column("persist_receipt_id", sa.Uuid(), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("upload_receipt_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("applied", sa.Boolean(), nullable=False),
        sa.Column("persisted_at", sa.DateTime(timezone=True), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("persist_receipt_id"),
        sa.ForeignKeyConstraint(
            ["upload_receipt_id", "team_id"],
            [
                "product_collection_upload_receipts.upload_receipt_id",
                "product_collection_upload_receipts.team_id",
            ],
            name="fk_pc_persist_upload_team",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["product_id", "team_id"],
            ["product_library_products.product_id", "product_library_products.team_id"],
            name="fk_pc_persist_product_team",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["version_id", "product_id", "team_id"],
            [
                "product_library_product_versions.version_id",
                "product_library_product_versions.product_id",
                "product_library_product_versions.team_id",
            ],
            name="fk_pc_persist_version_product_team",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("upload_receipt_id", name="uq_pc_persist_upload"),
        sa.UniqueConstraint("version_id", name="uq_pc_persist_version"),
        sa.CheckConstraint(
            "outcome IN ('applied','not_applied','superseded')",
            name="outcome",
        ),
        sa.CheckConstraint("applied = (outcome = 'applied')", name="applied_outcome"),
    )

    op.create_foreign_key(
        "fk_library_product_adopted_version",
        "product_library_products",
        "product_library_product_versions",
        ["adopted_version_id", "product_id", "team_id"],
        ["version_id", "product_id", "team_id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_collection_item_current_dispatch",
        "product_collection_items",
        "product_collection_dispatches",
        ["current_dispatch_id", "item_id", "team_id"],
        ["dispatch_id", "item_id", "team_id"],
        ondelete="RESTRICT",
    )


def downgrade():
    if op.get_context().as_sql:
        raise RuntimeError("0049 downgrade requires an online exact Feature target check")
    connection = op.get_bind()
    if _scalar(connection, "SELECT current_database()") != FEATURE_DATABASE:
        raise RuntimeError(
            "0049 downgrade permits only the registered mobile product collection Feature database",
        )

    connection.execute(
        sa.text(
            "LOCK TABLE product_selection_candidates, " + ", ".join(FEATURE_TABLES)
            + " IN ACCESS EXCLUSIVE MODE",
        ),
    )
    for table_name in FEATURE_TABLES:
        if _scalar(
            connection,
            f"SELECT EXISTS (SELECT 1 FROM {table_name} LIMIT 1)",
        ):
            raise RuntimeError(
                "0049 contains mobile product collection facts; retain schema and audit data",
            )

    op.drop_constraint(
        "fk_collection_item_current_dispatch",
        "product_collection_items",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_library_product_adopted_version",
        "product_library_products",
        type_="foreignkey",
    )
    for table_name in FEATURE_TABLES:
        op.drop_table(table_name)
    op.drop_constraint(
        "uq_selection_candidate_id_team",
        "product_selection_candidates",
        type_="unique",
    )
