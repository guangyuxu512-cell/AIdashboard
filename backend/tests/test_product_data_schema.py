from datetime import date
from decimal import Decimal
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from sqlalchemy import CheckConstraint, Column, ForeignKeyConstraint, MetaData, Table, Uuid, UniqueConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app.core.database import Base
from app.modules.access.models import Team  # noqa: F401
from app.modules.shops.models import Shop  # noqa: F401
from app.modules.users.models import User  # noqa: F401
from app.modules.product_data.models import (
    ShopProductDataGeneration, ShopProductDataMetricSnapshot, ShopProductDataProduct, ShopProductDataSeries,
)
from app.modules.product_data.schemas import ProductDataMetricRange, ProductDataQuery
from app.modules.product_data.exceptions import ProductDataUnitUnconfirmedError


MODEL_TABLES = [model.__table__ for model in (ShopProductDataProduct, ShopProductDataSeries,
                                           ShopProductDataGeneration, ShopProductDataMetricSnapshot)]


def migration():
    path = Path(__file__).parents[1] / "migrations/versions/20261017_0047_shop_product_data_v1.py"
    spec = importlib.util.spec_from_file_location("product_data_0047_test", path)
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


@pytest.mark.parametrize("changes", [{"page_size": 101}, {"page": 0}, {"sort_field": "raw_sql"},
    {"sort_field": "net_pay_cnt"}, {"period": "custom"}, {"sale_type": "2"}, {"group_id": "x"}])
def test_unsupported_query_never_silently_downgrades(changes):
    with pytest.raises(ValidationError): query(**changes)


@pytest.mark.parametrize("value", [True, 0.1, "NaN", "Infinity", "-1", "1.5"])
def test_count_range_validation(value):
    with pytest.raises(ValidationError):
        ProductDataMetricRange(metric="net_pay_cnt", min_value=value)


def test_ratio_range_and_amount_sort_are_unit_gated_before_repository():
    selected = query(ranges=[{"metric": "pay_refund_ratio", "min_value": "10"}])
    with pytest.raises(ProductDataUnitUnconfirmedError): selected.require_verified_units()
    with pytest.raises(ProductDataUnitUnconfirmedError): query(sort_field="pay_amt", sort_direction="desc").require_verified_units()


def test_model_and_frozen_migration_columns_and_checks_match_without_a_database(monkeypatch):
    module = migration()
    metadata = MetaData(naming_convention=Base.metadata.naming_convention)
    for name, key in (("shops", "shop_id"), ("users", "user_id"), ("teams", "team_id")):
        Table(name, metadata, Column(key, Uuid, primary_key=True))
    def create_table(name, *args): return Table(name, metadata, *args)
    def create_fk(name, source, target, local, remote, **kwargs):
        metadata.tables[source].append_constraint(ForeignKeyConstraint(local, [target+"."+key for key in remote], name=name, **kwargs))
    monkeypatch.setattr(module, "op", SimpleNamespace(create_table=create_table, create_index=lambda *a, **k: None,
                                                     create_foreign_key=create_fk))
    module.upgrade()
    for model in MODEL_TABLES:
        frozen = metadata.tables[model.name]
        assert set(model.c.keys()) == set(frozen.c.keys())
        assert {c.name: str(c.sqltext) for c in model.constraints if isinstance(c, CheckConstraint)} == {
            c.name: str(c.sqltext) for c in frozen.constraints if isinstance(c, CheckConstraint)}
        assert str(CreateTable(model).compile(dialect=postgresql.dialect()))
        assert str(CreateTable(frozen).compile(dialect=postgresql.dialect()))
    actor_key = next(c for c in ShopProductDataGeneration.__table__.constraints
                     if isinstance(c, UniqueConstraint) and c.name == "uq_spd_generation_actor_key")
    assert tuple(c.name for c in actor_key.columns) == ("requested_by_user_id", "submission_key")
    assert not ShopProductDataGeneration.__table__.c.requested_by_user_id.nullable


@pytest.mark.parametrize("target,offline,has_rows", [("control_center_integration", False, False),
    ("control_center_feat_shop_product_data_copy", False, False),
    ("control_center_feat_shop_product_data", True, False), ("control_center_feat_shop_product_data", False, True)])
def test_downgrade_refuses_wrong_target_offline_and_any_business_row(target, offline, has_rows, monkeypatch):
    module = migration()
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
