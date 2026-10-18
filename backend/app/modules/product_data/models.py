"""The four approved product-data tables; no queue, scheduler or cleanup."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint,
    Index, Integer, Numeric, String, Text, UniqueConstraint, Uuid, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin
from app.platforms.douyin.product_data import PRODUCT_METRICS
from app.shared.identifiers import generate_id


def exact_json_keys(column: str, keys: tuple[str, ...]) -> str:
    array = "ARRAY[" + ",".join("'" + key + "'" for key in keys) + "]"
    return f"jsonb_typeof({column}) = 'object' AND {column} ?& {array} AND ({column} - {array}) = '{{}}'::jsonb"


def metric_checks() -> tuple[CheckConstraint, ...]:
    codes = tuple(metric.code for metric in PRODUCT_METRICS)
    checks = [
        CheckConstraint(exact_json_keys("raw_units", codes), name="unit_keys"),
        CheckConstraint(exact_json_keys("metric_states", codes), name="state_keys"),
    ]
    for index, metric in enumerate(PRODUCT_METRICS):
        code = metric.code
        unit = f"raw_units -> '{code}'"
        state = f"metric_states ->> '{code}'"
        checks.extend((
            CheckConstraint(
                f"({unit} = 'null'::jsonb OR (jsonb_typeof({unit}) = 'number' AND (raw_units ->> '{code}') ~ '^[0-9]+$'))",
                name=f"unit_{index}",
            ),
            CheckConstraint(
                f"jsonb_typeof(metric_states -> '{code}') = 'string' AND {state} IN ('available','missing','null','invalid')",
                name=f"state_{index}",
            ),
            CheckConstraint(
                f"{code} IS NULL OR {code}::text NOT IN ('NaN','Infinity','-Infinity')",
                name=f"finite_{index}",
            ),
            CheckConstraint(
                f"{state} <> 'available' OR ({code} IS NOT NULL AND {code} >= 0 AND "
                f"(raw_units ->> '{code}' = '{metric.observed_unit}') IS TRUE"
                + (f" AND {code} = trunc({code})" if metric.kind == "count" else "") + ")",
                name=f"available_{index}",
            ),
        ))
    return tuple(checks)


class ShopProductDataProduct(TimestampMixin, Base):
    __tablename__ = "shop_product_data_products"
    __table_args__ = (
        UniqueConstraint("shop_id", "platform", "platform_product_id", name="uq_spd_product_identity"),
        UniqueConstraint("shop_product_id", "shop_id", name="uq_spd_product_shop"),
        CheckConstraint("platform = 'douyin'", name="platform"),
        CheckConstraint("platform_product_id ~ '^[0-9]{1,32}$'", name="product_id"),
    )

    shop_product_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=generate_id)
    shop_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("shops.shop_id", ondelete="RESTRICT"), nullable=False)
    platform: Mapped[str] = mapped_column(String(16), nullable=False)
    platform_product_id: Mapped[str] = mapped_column(String(32), nullable=False)


class ShopProductDataSeries(TimestampMixin, Base):
    __tablename__ = "shop_product_data_series"
    __table_args__ = (
        UniqueConstraint("shop_id", "rolling_series_hash", name="uq_spd_series_scope"),
        UniqueConstraint("series_id", "shop_id", name="uq_spd_series_shop"),
        ForeignKeyConstraint(
            ["current_generation_id", "series_id"],
            ["shop_product_data_generations.generation_id", "shop_product_data_generations.series_id"],
            ondelete="RESTRICT", use_alter=True, name="fk_spd_series_current",
        ),
        ForeignKeyConstraint(
            ["previous_generation_id", "series_id"],
            ["shop_product_data_generations.generation_id", "shop_product_data_generations.series_id"],
            ondelete="RESTRICT", use_alter=True, name="fk_spd_series_previous",
        ),
        CheckConstraint("rolling_series_hash ~ '^[a-f0-9]{64}$'", name="scope_hash"),
        CheckConstraint("period IN ('1d','7d','30d') AND sale_type = '1' AND content_type = '1'", name="native_scope"),
        CheckConstraint("next_sequence > 0 AND published_sequence >= 0 AND published_sequence < next_sequence", name="sequences"),
        CheckConstraint("(current_generation_id IS NULL AND published_sequence = 0 AND previous_generation_id IS NULL) OR (current_generation_id IS NOT NULL AND published_sequence > 0)", name="current_pair"),
        CheckConstraint("previous_generation_id IS NULL OR current_generation_id <> previous_generation_id", name="distinct_pointers"),
    )

    series_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=generate_id)
    shop_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("shops.shop_id", ondelete="RESTRICT"), nullable=False)
    rolling_series_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    period: Mapped[str] = mapped_column(String(8), nullable=False)
    sale_type: Mapped[str] = mapped_column(String(8), nullable=False)
    content_type: Mapped[str] = mapped_column(String(8), nullable=False)
    request_contract: Mapped[str] = mapped_column(String(64), nullable=False)
    metric_contract: Mapped[str] = mapped_column(String(64), nullable=False)
    next_sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    published_sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    current_generation_id: Mapped[UUID | None] = mapped_column(Uuid)
    previous_generation_id: Mapped[UUID | None] = mapped_column(Uuid)


class ShopProductDataGeneration(TimestampMixin, Base):
    __tablename__ = "shop_product_data_generations"
    __table_args__ = (
        ForeignKeyConstraint(["series_id", "shop_id"], ["shop_product_data_series.series_id", "shop_product_data_series.shop_id"], ondelete="RESTRICT", name="fk_spd_generation_series_shop"),
        UniqueConstraint("generation_id", "shop_id", name="uq_spd_generation_shop"),
        UniqueConstraint("generation_id", "series_id", name="uq_spd_generation_series"),
        UniqueConstraint("series_id", "sequence", name="uq_spd_generation_sequence"),
        UniqueConstraint("requested_by_user_id", "submission_key", name="uq_spd_generation_actor_key"),
        Index("uq_spd_active_slice", "shop_id", "source_scope_hash", unique=True, postgresql_where=text("status IN ('pending','running')")),
        Index("ix_spd_generation_actor", "requested_by_user_id", "requested_team_id", "created_at", "generation_id"),
        CheckConstraint("source_scope_hash ~ '^[a-f0-9]{64}$'", name="scope_hash"),
        CheckConstraint("sequence > 0", name="sequence"),
        CheckConstraint("status IN ('pending','running','succeeded','failed')", name="status"),
        CheckConstraint("start_date <= end_date", name="date_order"),
        CheckConstraint("(period = '1d' AND date_type = '20' AND end_date - start_date = 0) OR (period = '7d' AND date_type = '21' AND end_date - start_date = 6) OR (period = '30d' AND date_type = '23' AND end_date - start_date = 29)", name="native_window"),
        CheckConstraint("received_pages >= 0 AND (expected_total IS NULL OR expected_total > 0) AND (received_total IS NULL OR received_total >= 0) AND (raw_complete_rows IS NULL OR raw_complete_rows >= 0) AND (unit_complete_rows IS NULL OR unit_complete_rows >= 0)", name="counts"),
        CheckConstraint("(received_total IS NULL OR expected_total IS NULL OR received_total <= expected_total) AND (raw_complete_rows IS NULL OR (received_total IS NOT NULL AND raw_complete_rows <= received_total)) AND (unit_complete_rows IS NULL OR (raw_complete_rows IS NOT NULL AND unit_complete_rows <= raw_complete_rows))", name="coverage_counts"),
        CheckConstraint("stage IN ('queued','session_preparation','signing','platform_response','response_parse','collection_coverage','publication','execution','complete')", name="stage"),
        CheckConstraint(exact_json_keys("request_scope", ("shop_id", "period", "start_date", "end_date", "timezone", "platform", "sale_type", "content_type", "request_contract", "metric_contract")), name="scope_keys"),
        CheckConstraint(
            "(status = 'pending' AND lease_id IS NULL AND lease_until IS NULL AND started_at IS NULL AND finished_at IS NULL AND published_at IS NULL AND NOT pages_complete) OR "
            "(status = 'running' AND lease_id IS NOT NULL AND lease_until IS NOT NULL AND started_at IS NOT NULL AND finished_at IS NULL AND published_at IS NULL AND NOT pages_complete) OR "
            "(status = 'succeeded' AND lease_id IS NULL AND lease_until IS NULL AND started_at IS NOT NULL AND finished_at IS NOT NULL AND published_at IS NOT NULL AND pages_complete AND expected_total IS NOT NULL AND received_total IS NOT NULL AND received_total = expected_total AND raw_complete_rows IS NOT NULL AND unit_complete_rows IS NOT NULL AND failure_code IS NULL) OR "
            "(status = 'failed' AND lease_id IS NULL AND lease_until IS NULL AND finished_at IS NOT NULL AND published_at IS NULL AND NOT pages_complete AND failure_code IS NOT NULL)",
            name="state_fields",
        ),
    )

    generation_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=generate_id)
    series_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    shop_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    requested_by_user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False)
    requested_team_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("teams.team_id", ondelete="RESTRICT"))
    submission_key: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    period: Mapped[str] = mapped_column(String(8), nullable=False)
    date_type: Mapped[str] = mapped_column(String(8), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    source_scope_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    request_scope: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    received_pages: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    expected_total: Mapped[int | None] = mapped_column(Integer)
    received_total: Mapped[int | None] = mapped_column(Integer)
    raw_complete_rows: Mapped[int | None] = mapped_column(Integer)
    unit_complete_rows: Mapped[int | None] = mapped_column(Integer)
    pages_complete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    failure_code: Mapped[str | None] = mapped_column(String(96))
    lease_id: Mapped[UUID | None] = mapped_column(Uuid)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ShopProductDataMetricSnapshot(Base):
    __tablename__ = "shop_product_data_metric_snapshots"
    __table_args__ = (
        ForeignKeyConstraint(["generation_id", "shop_id"], ["shop_product_data_generations.generation_id", "shop_product_data_generations.shop_id"], ondelete="RESTRICT", name="fk_spd_snapshot_generation_shop"),
        ForeignKeyConstraint(["shop_product_id", "shop_id"], ["shop_product_data_products.shop_product_id", "shop_product_data_products.shop_id"], ondelete="RESTRICT", name="fk_spd_snapshot_product_shop"),
        *metric_checks(),
    )

    generation_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    shop_product_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    shop_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    observed_title: Mapped[str | None] = mapped_column(Text)
    observed_image_url: Mapped[str | None] = mapped_column(Text)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    raw_units: Mapped[dict] = mapped_column(JSONB, nullable=False)
    metric_states: Mapped[dict] = mapped_column(JSONB, nullable=False)
    product_show_cnt: Mapped[Decimal | None] = mapped_column(Numeric)
    product_click_cnt: Mapped[Decimal | None] = mapped_column(Numeric)
    product_show_click_converse_uv_rate: Mapped[Decimal | None] = mapped_column(Numeric)
    click_add_to_cart_uv: Mapped[Decimal | None] = mapped_column(Numeric)
    product_add_show_converse_uv_ratio: Mapped[Decimal | None] = mapped_column(Numeric)
    net_pay_cnt: Mapped[Decimal | None] = mapped_column(Numeric)
    pay_cnt_exclude_refund: Mapped[Decimal | None] = mapped_column(Numeric)
    product_click_pay_converse_uv_rate: Mapped[Decimal | None] = mapped_column(Numeric)
    pay_refund_ratio: Mapped[Decimal | None] = mapped_column(Numeric)
    pay_amt: Mapped[Decimal | None] = mapped_column(Numeric)
    pay_cnt: Mapped[Decimal | None] = mapped_column(Numeric)
    pay_ucnt: Mapped[Decimal | None] = mapped_column(Numeric)
    per_user_price: Mapped[Decimal | None] = mapped_column(Numeric)
    pay_refund_success_amt: Mapped[Decimal | None] = mapped_column(Numeric)
    pay_refund_success_order_cnt: Mapped[Decimal | None] = mapped_column(Numeric)
    product_show_ucnt: Mapped[Decimal | None] = mapped_column(Numeric)
    product_click_ucnt: Mapped[Decimal | None] = mapped_column(Numeric)
