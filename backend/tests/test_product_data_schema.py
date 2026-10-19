from datetime import date
from decimal import Decimal
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKeyConstraint,
    Index,
    MetaData,
    Table,
    Uuid,
    UniqueConstraint,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app.core.database import Base
from app.modules.access.models import Team  # noqa: F401
from app.modules.shops.models import Shop  # noqa: F401
from app.modules.users.models import User  # noqa: F401
from app.modules.product_data.models import (
    ShopProductDataCollectionBatch,
    ShopProductDataGeneration,
    ShopProductDataMetricSnapshot,
    ShopProductDataProduct,
    ShopProductDataSeries,
)
from app.modules.product_data.schemas import (
    ProductDataCollectionBatchRequest,
    ProductDataMetricRange,
    ProductDataQuery,
)
from app.modules.product_data.exceptions import ProductDataUnitUnconfirmedError
from app.modules.product_data.schemas import METRIC_BY_CODE
from app.platforms.douyin.product_data import ProductMetricDefinition


MODEL_TABLES = [model.__table__ for model in (
    ShopProductDataCollectionBatch,
    ShopProductDataProduct,
    ShopProductDataSeries,
    ShopProductDataGeneration,
    ShopProductDataMetricSnapshot,
)]


def migration(revision: str):
    names = {
        "0047": "20261017_0047_shop_product_data_v1.py",
        "0048": "20261019_0048_shop_product_data_batch_queue_v1.py",
    }
    path = Path(__file__).parents[1] / "migrations/versions" / names[revision]
    spec = importlib.util.spec_from_file_location(
        "product_data_" + revision + "_test",
        path,
    )
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def query(**changes):
    return ProductDataQuery.model_validate({"period": "1d", "start_date": date(2026, 1, 1),
        "end_date": date(2026, 1, 1)} | changes)


def test_query_default_pagination_and_exact_count_boundaries():
    result = query(ranges=[{"metric": "net_pay_cnt", "min_value": "0", "max_value": "900719925474099312345"}])
    assert result.page == 1 and result.page_size == 20
    assert result.ranges[0].min_value == 0
    assert result.ranges[0].max_value == Decimal("900719925474099312345")
    result.require_verified_units()


def test_collection_batch_requires_distinct_finite_shop_set():
    shops = tuple(uuid4() for _ in range(100))
    request = ProductDataCollectionBatchRequest(
        shop_ids=shops,
        period="1d",
        submission_key=uuid4(),
    )
    assert request.shop_ids == shops
    with pytest.raises(ValidationError):
        ProductDataCollectionBatchRequest(
            shop_ids=(shops[0], shops[0]),
            period="1d",
            submission_key=uuid4(),
        )
    with pytest.raises(ValidationError):
        ProductDataCollectionBatchRequest(
            shop_ids=shops + (uuid4(),),
            period="1d",
            submission_key=uuid4(),
        )


@pytest.mark.parametrize("changes", [{"page_size": 101}, {"page": 0}, {"sort_field": "raw_sql"},
    {"sort_field": "net_pay_cnt"}, {"period": "custom"}, {"sale_type": "2"}, {"group_id": "x"}])
def test_unsupported_query_never_silently_downgrades(changes):
    with pytest.raises(ValidationError): query(**changes)


@pytest.mark.parametrize("value", [True, 0.1, "NaN", "Infinity", "-1", "1.5"])
def test_count_range_validation(value):
    with pytest.raises(ValidationError):
        ProductDataMetricRange(metric="net_pay_cnt", min_value=value)


@pytest.mark.parametrize("code", ["product_show_click_converse_uv_rate", "product_add_show_converse_uv_ratio",
                                  "product_click_pay_converse_uv_rate", "pay_refund_ratio"])
def test_verified_ratio_ranges_use_exact_fractions_and_amount_sort_is_supported(code):
    selected = query(ranges=[{"metric": code, "min_value": "0.0029", "max_value": "0.0101"}])
    selected.require_verified_units()
    assert selected.ranges[0].min_value == Decimal("0.0029")
    assert selected.ranges[0].max_value == Decimal("0.0101")
    query(sort_field="pay_amt", sort_direction="desc").require_verified_units()


@pytest.mark.parametrize("value", [True, 0.1, "NaN", "Infinity", "-1"])
def test_ratio_ranges_keep_exact_nonnegative_finite_input_validation(value):
    with pytest.raises(ValidationError):
        ProductDataMetricRange(metric="pay_refund_ratio", min_value=value)


def test_unknown_future_unit_is_still_rejected_before_repository(monkeypatch):
    monkeypatch.setitem(METRIC_BY_CODE, "pay_amt", ProductMetricDefinition("pay_amt", "amount", 6))
    with pytest.raises(ProductDataUnitUnconfirmedError):
        query(sort_field="pay_amt", sort_direction="asc").require_verified_units()


def test_model_and_frozen_migration_columns_and_checks_match_without_a_database(monkeypatch):
    initial = migration("0047")
    queue = migration("0048")
    metadata = MetaData(naming_convention=Base.metadata.naming_convention)
    for name, key in (("shops", "shop_id"), ("users", "user_id"), ("teams", "team_id")):
        Table(name, metadata, Column(key, Uuid, primary_key=True))
    def create_table(name, *args): return Table(name, metadata, *args)
    def create_fk(name, source, target, local, remote, **kwargs):
        metadata.tables[source].append_constraint(ForeignKeyConstraint(local, [target+"."+key for key in remote], name=name, **kwargs))
    def create_index(name, table_name, columns, **kwargs):
        return Index(name, *(metadata.tables[table_name].c[key] for key in columns), **kwargs)
    def drop_index(name, *, table_name):
        table = metadata.tables[table_name]
        table.indexes.remove(next(item for item in table.indexes if item.name == name))
    def drop_constraint(name, table_name, **_kwargs):
        table = metadata.tables[table_name]
        table.constraints.remove(next(
            item for item in table.constraints
            if item.name == name or item.name.endswith("_" + name)
        ))
    def add_column(table_name, column):
        metadata.tables[table_name].append_column(column)
    def alter_column(table_name, column_name, **kwargs):
        column = metadata.tables[table_name].c[column_name]
        if "nullable" in kwargs:
            column.nullable = kwargs["nullable"]
        if "server_default" in kwargs:
            column.server_default = kwargs["server_default"]
    def create_unique(name, table_name, columns):
        metadata.tables[table_name].append_constraint(
            UniqueConstraint(*columns, name=name),
        )
    def create_check(name, table_name, condition):
        metadata.tables[table_name].append_constraint(
            CheckConstraint(condition, name=name),
        )
    initial_op = SimpleNamespace(
        create_table=create_table,
        create_index=create_index,
        create_foreign_key=create_fk,
    )
    monkeypatch.setattr(initial, "op", initial_op)
    initial.upgrade()
    queue_op = SimpleNamespace(
        get_bind=lambda: SimpleNamespace(scalar=lambda *_: False),
        create_table=create_table,
        add_column=add_column,
        alter_column=alter_column,
        execute=lambda *_: None,
        drop_constraint=drop_constraint,
        drop_index=drop_index,
        create_foreign_key=create_fk,
        create_unique_constraint=create_unique,
        create_index=create_index,
        create_check_constraint=create_check,
    )
    monkeypatch.setattr(queue, "op", queue_op)
    queue.upgrade()
    for model in MODEL_TABLES:
        frozen = metadata.tables[model.name]
        assert set(model.c.keys()) == set(frozen.c.keys())
        assert {c.name: str(c.sqltext) for c in model.constraints if isinstance(c, CheckConstraint)} == {
            c.name: str(c.sqltext) for c in frozen.constraints if isinstance(c, CheckConstraint)}
        assert str(CreateTable(model).compile(dialect=postgresql.dialect()))
        assert str(CreateTable(frozen).compile(dialect=postgresql.dialect()))
    actor_key = next(c for c in ShopProductDataCollectionBatch.__table__.constraints
                     if isinstance(c, UniqueConstraint) and c.name == "uq_spd_batch_actor_key")
    assert tuple(c.name for c in actor_key.columns) == ("requested_by_user_id", "submission_key")
    assert "uq_spd_generation_actor_key" not in {
        constraint.name for constraint in ShopProductDataGeneration.__table__.constraints
    }
    assert {index.name for index in ShopProductDataGeneration.__table__.indexes} == {
        index.name for index in metadata.tables[ShopProductDataGeneration.__tablename__].indexes
    }
    assert not ShopProductDataGeneration.__table__.c.requested_by_user_id.nullable


@pytest.mark.parametrize("target,offline,has_rows", [("control_center_integration", False, False),
    ("control_center_feat_shop_product_data_copy", False, False),
    ("control_center_feat_shop_product_data", True, False), ("control_center_feat_shop_product_data", False, True)])
def test_downgrade_refuses_wrong_target_offline_and_any_business_row(target, offline, has_rows, monkeypatch):
    module = migration("0047")
    calls = []
    class Connection:
        def scalar(self, statement):
            calls.append(str(statement))
            return target if "current_database" in str(statement) else has_rows
        def execute(self, statement): calls.append(str(statement))
    monkeypatch.setattr(module, "op", SimpleNamespace(get_context=lambda: SimpleNamespace(as_sql=offline),
        get_bind=lambda: Connection(), drop_table=lambda *a: calls.append("DROP"), drop_constraint=lambda *a, **k: calls.append("DROP")))
    with pytest.raises(RuntimeError): module.downgrade()
    assert "DROP" not in calls
    if target != "control_center_feat_shop_product_data" or offline:
        assert not any("LOCK" in call for call in calls)


@pytest.mark.parametrize(
    "target,offline,incompatible",
    [
        ("control_center_integration", False, False),
        ("control_center_feat_shop_product_data_batch_queue", True, False),
        ("control_center_feat_shop_product_data_batch_queue", False, True),
    ],
)
def test_batch_queue_downgrade_refuses_wrong_target_offline_and_new_history(
    target,
    offline,
    incompatible,
    monkeypatch,
):
    module = migration("0048")
    calls = []

    class Connection:
        checks = 0

        def scalar(self, statement):
            calls.append(str(statement))
            if "current_database" in str(statement):
                return target
            self.checks += 1
            return incompatible if self.checks == 1 else False

        def execute(self, statement):
            calls.append(str(statement))

    monkeypatch.setattr(
        module,
        "op",
        SimpleNamespace(
            get_context=lambda: SimpleNamespace(as_sql=offline),
            get_bind=lambda: Connection(),
            drop_table=lambda *args: calls.append(("DROP TABLE", args)),
            drop_constraint=lambda *args, **kwargs: calls.append(("DROP CONSTRAINT", args, kwargs)),
            drop_index=lambda *args, **kwargs: calls.append(("DROP INDEX", args, kwargs)),
            drop_column=lambda *args: calls.append(("DROP COLUMN", args)),
            create_unique_constraint=lambda *args: calls.append(("CREATE UNIQUE", args)),
            create_index=lambda *args, **kwargs: calls.append(("CREATE INDEX", args, kwargs)),
            create_check_constraint=lambda *args: calls.append(("CREATE CHECK", args)),
        ),
    )
    with pytest.raises(RuntimeError):
        module.downgrade()
    assert not any(isinstance(call, tuple) for call in calls)
    if target != module.FEATURE_DATABASE or offline:
        assert not any("LOCK TABLE" in call for call in calls if isinstance(call, str))
