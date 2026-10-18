from argparse import Namespace
from datetime import date
from uuid import UUID

import pytest
from sqlalchemy.engine import make_url

import tools.product_selection_capacity as capacity
from tools.product_selection_capacity import (
    API_TARGET,
    CapacityToolError,
    DatasetSpec,
    STRATEGIES_PER_TEAM,
    TEAM_COUNT,
    _base_rows,
    _observation_rows,
    _request,
    _result_rows,
    _run_rows,
    _safe_error,
    bind_target,
    build_manifest,
    build_run_plans,
    ensure_namespace,
    iter_candidate_plans,
    parser,
    require_namespace,
    team_index_for,
    validate_target_arguments,
    validate_measure_arguments,
)


RUN_ID = UUID("82ada5cf-0a69-4a51-8bff-83b93c079436")


def spec(tier: int = 50_000) -> DatasetSpec:
    return DatasetSpec(RUN_ID, tier, date(2026, 10, 18))


def test_manifest_is_deterministic_and_has_realistic_relations():
    first = build_manifest(spec())
    second = build_manifest(spec())

    assert first == second
    assert first["counts"]["candidates"] == 50_000
    assert first["counts"]["observations"] > first["counts"]["candidates"]
    assert first["counts"]["result_items"] > first["counts"]["observations"]
    assert first["counts"]["runs"] > first["counts"]["strategies"]
    assert first["counts"]["strategies"] == TEAM_COUNT * STRATEGIES_PER_TEAM
    assert first["counts"]["memberships"] == TEAM_COUNT
    assert first["counts"]["module_access"] == TEAM_COUNT
    assert first["counts"]["shop_access"] == TEAM_COUNT * 3
    assert sum(first["distribution"]["team_candidates"]) == 50_000
    assert all(first["distribution"]["normal_team_visible_blocked"])
    assert all(first["distribution"]["normal_team_revoked"])
    assert sum(first["distribution"]["normal_team_revoked"]) == (
        first["distribution"]["revoked_shop_candidates"]
    )
    assert sum(first["distribution"]["team_weights"]) == 100
    assert first["query_contract"]["default_page_size"] == 20
    expected = first["query_contract"]["expected_totals"]
    assert expected["search-common"] > expected["search-rare"] > 0
    assert sum(expected[f"search-{kind}"] for kind in ("common", "rare", "normal")) == (
        first["counts"]["super_default_visible_unblocked"]
    )
    assert all(expected[name] > 0 for name in (
        "team-shop0",
        "team-shop1-blocked",
        "team-strategy0",
        "team-receipt",
        "team-today-new",
    ))
    assert expected["team-today-all"] == sum(
        expected[f"team-today-{state}"] for state in ("new", "known", "unknown")
    )


def test_incremental_tiers_keep_existing_candidate_identity_and_distribution():
    small = iter_candidate_plans(spec(50_000))
    large = iter_candidate_plans(spec(300_000))
    for _ in range(2_000):
        assert next(small) == next(large)
    assert [team_index_for(index) for index in range(100)].count(0) == 40
    assert [team_index_for(index) for index in range(100)].count(7) == 3


@pytest.mark.parametrize(
    ("database", "endpoint", "allow"),
    [
        ("control_center_prod", "127.0.0.1:5432", True),
        ("control_center_dev", "127.0.0.1:5432", True),
        ("control_center_integration", "127.0.0.1:5432", True),
        ("control_center_feat_product_selection", "127.0.0.1:5432", True),
        ("control_center_capacity_one", "127.0.0.1:5432", False),
        ("control_center_capacity_one", "127.0.0.1:6432", True),
    ],
)
def test_database_guard_refuses_normal_targets_and_mismatches(database, endpoint, allow):
    url = make_url("postgresql+psycopg://user:secret@127.0.0.1:5432/control_center_capacity_one")
    with pytest.raises(CapacityToolError):
        validate_target_arguments(
            allow_capacity_test=allow,
            expected_database=database,
            expected_endpoint=endpoint,
            expected_head="20261015_0046",
            url=url,
        )


def test_database_guard_accepts_only_exact_capacity_target():
    url = make_url("postgresql+psycopg://user:secret@127.0.0.1:5432/control_center_capacity_one")
    validate_target_arguments(
        allow_capacity_test=True,
        expected_database="control_center_capacity_one",
        expected_endpoint="127.0.0.1:5432",
        expected_head="20261015_0046",
        url=url,
    )


def test_measure_parser_requires_explicit_api_target_and_bounded_tier():
    parsed = parser().parse_args([
        "measure",
        "--run-id", str(RUN_ID),
        "--tier", "50000",
        "--as-of", "2026-10-18",
        "--allow-capacity-test",
        "--expected-database", "control_center_capacity_one",
        "--expected-endpoint", "127.0.0.1:5432",
        "--expected-head", "20261015_0046",
        "--api-target", API_TARGET,
        "--readers", "8",
        "--duration-seconds", "60",
    ])
    assert parsed.readers == 8
    assert parsed.duration_seconds == 60
    assert parsed.samples == 30
    assert parsed.api_target == API_TARGET


def test_formal_measurement_profile_is_exact_and_bounded():
    accepted = Namespace(
        with_writer=True,
        readers=8,
        writer_interval_seconds=1.0,
        profile="formal",
        samples=30,
        duration_seconds=60,
    )
    validate_measure_arguments(accepted)
    for field, value in (
        ("with_writer", False),
        ("readers", 7),
        ("samples", 29),
        ("duration_seconds", 59),
    ):
        rejected = Namespace(**vars(accepted))
        setattr(rejected, field, value)
        with pytest.raises(CapacityToolError):
            validate_measure_arguments(rejected)


def test_strategy_and_run_contracts_cover_each_authorized_shop_and_scope():
    current = spec()
    rows = _base_rows(current)["strategies"]
    assert len(rows) == TEAM_COUNT * STRATEGIES_PER_TEAM
    first_team_shops = [row["request_shop_id"] for row in rows[:STRATEGIES_PER_TEAM]]
    assert len(set(first_team_shops)) == 3
    assert all(first_team_shops.count(shop_id) == 4 for shop_id in set(first_team_shops))
    plans = build_run_plans(current)
    requests = [_request(current, plan) for plan in list(plans.values())[:25]]
    assert all(request.version == 3 for request in requests)
    assert all(request.actual_scope().period_begin < request.actual_scope().period_end for request in requests)
    result = next(_result_rows(current))
    assert len(result["discovery_scope_hash"]) == 64
    run = next(_run_rows(current, plans))
    assert run["supplemented_count"] + run["supplement_failed_count"] <= run["saved_count"]
    assert run["status"] in {"succeeded", "partial"}


def test_observations_cover_failed_partial_unattempted_and_successful_basic_info():
    states = set()
    versions = set()
    for row in _observation_rows(spec()):
        states.add(row["basic_info_status"]["state"] if row["basic_info_status"] else "not_attempted")
        versions.add(row["basic_info_version"])
        if states == {"failed", "partial", "not_attempted", "succeeded"}:
            break
    assert states == {"failed", "partial", "not_attempted", "succeeded"}
    assert versions == {0, 1}


def test_parser_refuses_out_of_bounds_concurrency_without_large_choice_lists():
    with pytest.raises(SystemExit):
        parser().parse_args([
            "measure",
            "--run-id", str(RUN_ID),
            "--tier", "50000",
            "--as-of", "2026-10-18",
            "--allow-capacity-test",
            "--expected-database", "control_center_capacity_one",
            "--expected-endpoint", "127.0.0.1:5432",
            "--expected-head", "20261015_0046",
            "--api-target", API_TARGET,
            "--readers", "17",
        ])


def test_safe_error_redacts_url_password_and_headers():
    password = "unit-" + "credential"
    authorization = "Bearer " + "unit-value"
    session = "session" + "id=unit-value"
    database_scheme = "postgres" + "ql://"
    authorization_header = "Authori" + "zation"
    cookie_header = "Coo" + "kie"
    message = _safe_error(RuntimeError(
        f"{database_scheme}capacity:{password}@127.0.0.1/db "
        f"{authorization_header}: {authorization}\n{cookie_header}: {session}",
    ))
    assert password not in message
    assert authorization not in message
    assert session not in message


def test_namespace_must_match_before_measure_or_cleanup(tmp_path, monkeypatch):
    monkeypatch.setattr(capacity, "REPOSITORY_ROOT", tmp_path)
    current = spec()
    with pytest.raises(CapacityToolError):
        require_namespace(current)
    ensure_namespace(current)
    require_namespace(current)
    with pytest.raises(CapacityToolError):
        ensure_namespace(DatasetSpec(RUN_ID, 50_000, current.as_of, seed=current.seed + 1))


def test_database_binding_cannot_move_between_capacity_targets(tmp_path, monkeypatch):
    monkeypatch.setattr(capacity, "REPOSITORY_ROOT", tmp_path)
    current = spec()
    first = Namespace(
        expected_database="control_center_capacity_one",
        expected_endpoint="127.0.0.1:55432",
        expected_head="20261015_0046",
    )
    with pytest.raises(CapacityToolError):
        bind_target(current, first, create=False)
    bind_target(current, first, create=True)
    bind_target(current, first, create=False)
    second = Namespace(
        expected_database="control_center_capacity_two",
        expected_endpoint="127.0.0.1:65432",
        expected_head="20261015_0046",
    )
    with pytest.raises(CapacityToolError):
        bind_target(current, second, create=True)


def test_capacity_thumbnails_are_self_contained_and_offline():
    first = next(_observation_rows(spec()))

    assert first["image_url"].startswith("data:image/")
    assert "capacity.invalid" not in first["image_url"]
