"""Guarded candidate-pool capacity fixture and measurement tool.

The default ``plan`` command is offline.  Every database command requires an
explicit opt-in plus an exact database and endpoint match, and refuses all
normal development, Feature, Integration, and production database names.

This is not a platform collector.  It never loads ShopSession data, calls the
Douyin signer, or starts application schedulers/executors.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack, contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from hashlib import sha256
import json
import math
from pathlib import Path
import re
import threading
import time as monotonic_time
from typing import Any, Literal
from uuid import UUID, uuid5
from zoneinfo import ZoneInfo

from sqlalchemy import Engine, delete, event, func, select, text
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import create_database_engine
from app.modules.access.contracts import ActorContext, HumanPrincipal
from app.modules.access.enums import DataScope
from app.modules.access.models import (
    Team,
    TeamMembership,
    TeamModuleAccess,
    TeamShopAccess,
)
from app.modules.access.module_access import ModuleCode
from app.modules.access.roles import DEFAULT_ROLE_CODE
from app.modules.access.service import ActorContextService
from app.modules.product_selection.models import (
    ProductSelectionCandidate as Candidate,
    ProductSelectionObservation as Observation,
    ProductSelectionResultItem as ResultItem,
    ProductSelectionRun as SelectionRun,
    ProductSelectionStrategy as Strategy,
)
from app.modules.product_selection.result_service import SelectionResultService, discovery_key
from app.modules.product_selection.run_contract import (
    SelectionDateOutcome,
    SelectionDatePlan,
    SelectionRelativeConditions,
    SelectionResolvedRequest,
    SelectionRunOriginal,
    SelectionStrategySnapshot,
)
from app.modules.product_selection.service import ProductSelectionFactService
from app.modules.product_selection.source import SelectionSourceScope
from app.modules.product_selection.strategy_contract import (
    SelectionStrategyConditions,
    SelectionStrategySchedule,
)
from app.modules.shops.enums import ShopPlatform
from app.modules.shops.models import Shop
from app.modules.users.models import User
from app.platforms.douyin.product_selection import (
    CompassMerchant,
    CompassMetricRange,
    CompassRangeEndpoint,
    CompassRankPage,
    CompassRankProduct,
    FieldObservation,
)


TIERS = (50_000, 300_000, 500_000)
TEAM_WEIGHTS = (40, 16, 12, 10, 8, 6, 5, 3)
TEAM_COUNT = len(TEAM_WEIGHTS)
SHOPS_PER_TEAM = 4
AUTHORIZED_SHOPS_PER_TEAM = 3
RUN_ITEM_BATCH = 1_000
DEFAULT_SEED = 20_261_018
CAPACITY_DATABASE = re.compile(r"^control_center_capacity_[a-z0-9_]+$")
API_TARGET = "asgi://product-selection-capacity"
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
# Keep browser rendering deterministic and offline. The source link remains a
# non-fetching fixture URL, while thumbnails use an inline pixel so benchmark
# rows never wait on DNS or an external image host.
CAPACITY_IMAGE_DATA_URL = (
    "data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs="
)

SCOPE_SPECS: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    ("7", ("1000009092", "1000009142"), ("家居", "智能家居", "末级 A")),
    ("8", ("2000001001",), ("服饰", "上衣", "末级 B")),
    ("9", ("3000002001", "3000002002"), ("美妆", "护理", "末级 C")),
    ("10", ("4000003001",), ("食品", "零食", "末级 D")),
)
STRATEGIES_PER_TEAM = AUTHORIZED_SHOPS_PER_TEAM * len(SCOPE_SPECS)


class CapacityToolError(RuntimeError):
    """A safe, user-actionable refusal without credential-bearing details."""


@dataclass(frozen=True, slots=True)
class DatasetSpec:
    run_id: UUID
    candidate_count: int
    as_of: date
    seed: int = DEFAULT_SEED

    def __post_init__(self) -> None:
        if self.candidate_count not in TIERS:
            raise ValueError(f"candidate_count must be one of {TIERS}")


@dataclass(frozen=True, slots=True)
class ObservationPlan:
    candidate_index: int
    variant: int
    team_index: int
    shop_slot: int
    scope_index: int
    checked_at: datetime
    run_label: str
    history_run_label: str | None


@dataclass(frozen=True, slots=True)
class CandidatePlan:
    index: int
    team_index: int
    blocked: bool
    title_kind: Literal["common", "rare", "normal"]
    observations: tuple[ObservationPlan, ...]


@dataclass(slots=True)
class RunPlan:
    label: str
    team_index: int
    shop_slot: int
    scope_index: int
    batch: int
    history: bool
    strategy_index: int | None
    occurred_at: datetime
    item_count: int = 0
    supplemented_count: int = 0
    supplement_failed_count: int = 0


@dataclass(frozen=True, slots=True)
class SqlSample:
    category: str
    duration_ms: float
    statement_hash: str
    statement: str
    parameters: Any


_sql_samples: ContextVar[list[SqlSample] | None] = ContextVar(
    "product_selection_capacity_sql_samples",
    default=None,
)


def stable_id(namespace: UUID, label: str) -> UUID:
    return uuid5(namespace, label)


def team_index_for(candidate_index: int) -> int:
    bucket = candidate_index % sum(TEAM_WEIGHTS)
    cumulative = 0
    for index, weight in enumerate(TEAM_WEIGHTS):
        cumulative += weight
        if bucket < cumulative:
            return index
    raise AssertionError("team weights must cover every bucket")


def _status_bucket(pattern_index: int) -> int:
    """Spread status cases across Team buckets instead of correlating moduli."""
    return (pattern_index * 37 + (pattern_index // 100) * 13) % 20


def _has_second_observation(pattern_index: int) -> bool:
    return (pattern_index * 17 + (pattern_index // 100) * 7) % 5 == 0


def _discovery_state(spec: DatasetSpec, candidate_index: int) -> Literal["new", "known", "unknown"]:
    pattern_index = candidate_index + spec.seed
    bucket = (pattern_index * 7 + (pattern_index // 100) * 5) % 3
    return ("new", "known", "unknown")[bucket]


def _scope(spec: DatasetSpec, scope_index: int, *, backup: bool = False) -> SelectionSourceScope:
    industry_id, categories, _ = SCOPE_SPECS[scope_index]
    shift = 1 if backup else 0
    begin = spec.as_of - timedelta(days=7 + shift)
    end = spec.as_of - timedelta(days=1 + shift)
    return SelectionSourceScope(
        industry_id=industry_id,
        category_id=",".join(categories),
        brand_type="-1",
        price_bin="不限",
        search_info="",
        rank_data_type="1",
        begin_date=f"{begin:%Y/%m/%d} 00:00:00",
        end_date=f"{end:%Y/%m/%d} 00:00:00",
        date_type="21",
        activity_id="",
    )


def _run_time(
    spec: DatasetSpec,
    batch: int,
    team_index: int,
    shop_slot: int,
    scope_index: int,
    history: bool,
) -> datetime:
    shanghai_noon = datetime.combine(spec.as_of, time(12), tzinfo=UTC) - timedelta(hours=8)
    days = (batch * 7 + team_index * 11 + shop_slot * 5 + scope_index * 3) % 30
    value = shanghai_noon - timedelta(days=days, minutes=team_index * 3 + scope_index)
    return value - timedelta(days=7) if history else value


def iter_candidate_plans(spec: DatasetSpec) -> Iterator[CandidatePlan]:
    group_ordinals: defaultdict[tuple[int, int, int], int] = defaultdict(int)
    for candidate_index in range(spec.candidate_count):
        pattern_index = candidate_index + spec.seed
        team_index = team_index_for(pattern_index)
        status_bucket = _status_bucket(pattern_index)
        revoked = status_bucket == 0
        primary_shop = 3 if revoked else pattern_index % AUTHORIZED_SHOPS_PER_TEAM
        primary_scope = (pattern_index // 7) % len(SCOPE_SPECS)
        raw_observations = [(0, primary_shop, primary_scope)]
        if _has_second_observation(pattern_index) and not revoked:
            raw_observations.append(
                (1, (primary_shop + 1) % AUTHORIZED_SHOPS_PER_TEAM, (primary_scope + 1) % len(SCOPE_SPECS)),
            )
        observations: list[ObservationPlan] = []
        for variant, shop_slot, scope_index in raw_observations:
            group = (team_index, shop_slot, scope_index)
            ordinal = group_ordinals[group]
            group_ordinals[group] += 1
            batch = ordinal // RUN_ITEM_BATCH
            label = f"run:{team_index}:{shop_slot}:{scope_index}:{batch}"
            history = pattern_index % 4 == 0
            observations.append(ObservationPlan(
                candidate_index=candidate_index,
                variant=variant,
                team_index=team_index,
                shop_slot=shop_slot,
                scope_index=scope_index,
                checked_at=_run_time(
                    spec,
                    batch,
                    team_index,
                    shop_slot,
                    scope_index,
                    False,
                ),
                run_label=label,
                history_run_label=f"{label}:history" if history else None,
            ))
        title_kind = _title_kind(pattern_index)
        yield CandidatePlan(
            index=candidate_index,
            team_index=team_index,
            blocked=status_bucket == 1,
            title_kind=title_kind,
            observations=tuple(observations),
        )


def _title_kind(pattern_index: int) -> Literal["common", "rare", "normal"]:
    if pattern_index % 500 == 0:
        return "rare"
    if pattern_index % 10 < 3:
        return "common"
    return "normal"


def _run_strategy_index(team_index: int, shop_slot: int, scope_index: int, batch: int) -> int | None:
    if shop_slot >= AUTHORIZED_SHOPS_PER_TEAM or (team_index + shop_slot + scope_index + batch) % 5 == 0:
        return None
    return shop_slot * len(SCOPE_SPECS) + scope_index


def build_run_plans(spec: DatasetSpec) -> dict[str, RunPlan]:
    runs: dict[str, RunPlan] = {}
    for candidate in iter_candidate_plans(spec):
        for observation in candidate.observations:
            pieces = observation.run_label.split(":")
            batch = int(pieces[-1])
            current = runs.setdefault(observation.run_label, RunPlan(
                label=observation.run_label,
                team_index=observation.team_index,
                shop_slot=observation.shop_slot,
                scope_index=observation.scope_index,
                batch=batch,
                history=False,
                strategy_index=_run_strategy_index(
                    observation.team_index,
                    observation.shop_slot,
                    observation.scope_index,
                    batch,
                ),
                occurred_at=observation.checked_at,
            ))
            current.item_count += 1
            basic_bucket = candidate.index % 10
            if basic_bucket >= 3:
                current.supplemented_count += 1
            elif basic_bucket <= 1:
                current.supplement_failed_count += 1
            if observation.history_run_label is not None:
                history = runs.setdefault(observation.history_run_label, RunPlan(
                    label=observation.history_run_label,
                    team_index=observation.team_index,
                    shop_slot=observation.shop_slot,
                    scope_index=observation.scope_index,
                    batch=batch,
                    history=True,
                    strategy_index=current.strategy_index,
                    occurred_at=_run_time(
                        spec,
                        batch,
                        observation.team_index,
                        observation.shop_slot,
                        observation.scope_index,
                        True,
                    ),
                ))
                history.item_count += 1
                if basic_bucket >= 3:
                    history.supplemented_count += 1
                elif basic_bucket <= 1:
                    history.supplement_failed_count += 1
    return runs


def representative_run_plan(spec: DatasetSpec, runs: Mapping[str, RunPlan]) -> RunPlan:
    eligible = [
        run for run in runs.values()
        if run.team_index == 0 and run.strategy_index == 0 and not run.history
    ]
    if not eligible:
        raise CapacityToolError("deterministic dataset has no representative strategy run")
    latest = max(run.occurred_at for run in eligible)
    return min(
        (run for run in eligible if run.occurred_at == latest),
        key=lambda run: str(_run_id(spec, run.label)),
    )


def _team_id(spec: DatasetSpec, team_index: int) -> UUID:
    return stable_id(spec.run_id, f"team:{team_index}")


def _user_id(spec: DatasetSpec, team_index: int) -> UUID:
    return stable_id(spec.run_id, f"user:{team_index}")


def _membership_id(spec: DatasetSpec, team_index: int) -> UUID:
    return stable_id(spec.run_id, f"membership:{team_index}")


def _shop_id(spec: DatasetSpec, team_index: int, shop_slot: int) -> UUID:
    return stable_id(spec.run_id, f"shop:{team_index}:{shop_slot}")


def _strategy_id(spec: DatasetSpec, team_index: int, strategy_index: int) -> UUID:
    return stable_id(spec.run_id, f"strategy:{team_index}:{strategy_index}")


def _candidate_id(spec: DatasetSpec, candidate_index: int) -> UUID:
    return stable_id(spec.run_id, f"candidate:{candidate_index}")


def _observation_id(spec: DatasetSpec, candidate_index: int, variant: int) -> UUID:
    return stable_id(spec.run_id, f"observation:{candidate_index}:{variant}")


def _run_id(spec: DatasetSpec, label: str) -> UUID:
    return stable_id(spec.run_id, label)


def _result_item_id(spec: DatasetSpec, candidate_index: int, variant: int, history: bool) -> UUID:
    suffix = "history" if history else "current"
    return stable_id(spec.run_id, f"result:{candidate_index}:{variant}:{suffix}")


def _product_id(candidate_index: int) -> str:
    return str(8_000_000_000_000_000_000 + candidate_index)


def _title(candidate: CandidatePlan) -> str:
    prefix = {
        "common": "容量常见商品",
        "rare": "容量稀有关键词 ZXQ",
        "normal": "容量标准商品",
    }[candidate.title_kind]
    return f"{prefix} {candidate.index:06d} 长标题用于真实省略与搜索校验"


def _title_for_index(spec: DatasetSpec, candidate_index: int) -> str:
    return _title(CandidatePlan(
        index=candidate_index,
        team_index=team_index_for(candidate_index + spec.seed),
        blocked=_status_bucket(candidate_index + spec.seed) == 1,
        title_kind=_title_kind(candidate_index + spec.seed),
        observations=(),
    ))


def _metric(state: str, at: datetime, value: int) -> dict[str, Any]:
    result: dict[str, Any] = {"state": state, "retrieved_at": at.isoformat()}
    if state == "available":
        result["value_range"] = [
            {"value": str(value), "value_type": "int", "unit": "count"},
            {"value": str(value + 9), "value_type": "int", "unit": "count"},
        ]
    return result


def _metrics(candidate_index: int, at: datetime) -> dict[str, Any]:
    states = ("available", "available", "missing", "null", "invalid")
    names = ("pay_amt", "pay_combo_cnt", "product_click_cnt", "video_cnt")
    return {
        name: _metric(states[(candidate_index + offset) % len(states)], at, candidate_index % 100)
        for offset, name in enumerate(names)
    }


def _basic_status(candidate_index: int, at: datetime) -> tuple[dict[str, Any] | None, int, datetime | None]:
    bucket = candidate_index % 10
    if bucket == 2:
        return None, 0, None
    if bucket == 0:
        unknown = {"last_attempt_state": "unknown", "last_success_at": None}
        return ({
            "version": 1,
            "attempted_at": at.isoformat(),
            "request_started_at": (at - timedelta(seconds=2)).isoformat(),
            "state": "failed",
            "category_path": unknown,
            "first_on_shelf_date": unknown,
            "bad_comment_rate": unknown,
            "error_code": "PLATFORM_REQUEST_FAILED",
            "error_stage": "basic_info_request",
            "platform_business_code": None,
        }, 0, None)
    partial = bucket == 1
    field = {"last_attempt_state": "available", "last_success_at": at.isoformat()}
    unknown = {"last_attempt_state": "unknown", "last_success_at": None}
    return ({
        "version": 1,
        "attempted_at": at.isoformat(),
        "request_started_at": (at - timedelta(seconds=2)).isoformat(),
        "state": "partial" if partial else "succeeded",
        "category_path": field,
        "first_on_shelf_date": unknown if partial else field,
        "bad_comment_rate": unknown if partial else field,
        "error_code": "PRODUCT_SELECTION_BASIC_INFO_PARTIAL" if partial else None,
        "error_stage": "basic_info_parse" if partial else None,
        "platform_business_code": None,
    }, 1, None if partial else at)


def _original_request(
    spec: DatasetSpec,
    *,
    team_index: int,
    shop_slot: int,
    scope_index: int,
) -> SelectionRunOriginal:
    scope = _scope(spec, scope_index)
    _, categories, _ = SCOPE_SPECS[scope_index]
    return SelectionRunOriginal(
        shop_id=_shop_id(spec, team_index, shop_slot),
        channel="short-video",
        period="7d",
        industry_id=scope.industry_id,
        category_ids=categories,
        brand="all",
        price_mode="all",
        first_listed_only=False,
        rank_from=1,
        rank_to=200,
    )


def _request(spec: DatasetSpec, run: RunPlan) -> SelectionResolvedRequest:
    scope = _scope(spec, run.scope_index)
    backup = _scope(spec, run.scope_index, backup=True)
    original = _original_request(
        spec,
        team_index=run.team_index,
        shop_slot=run.shop_slot,
        scope_index=run.scope_index,
    )
    strategy = None
    if run.strategy_index is not None:
        strategy = SelectionStrategySnapshot(
            strategy_id=_strategy_id(spec, run.team_index, run.strategy_index),
            version=1,
        )
    return SelectionResolvedRequest(
        version=3,
        original=original,
        scope=scope,
        page_numbers=tuple(range(1, 21)),
        date_plan=SelectionDatePlan(accepted_local_date=spec.as_of, backup_scope=backup),
        date_outcome=SelectionDateOutcome(state="primary"),
        strategy=strategy,
    )


def _strategy_payload(spec: DatasetSpec, team_index: int, strategy_index: int) -> tuple[dict[str, Any], dict[str, Any]]:
    scope_index = strategy_index % len(SCOPE_SPECS)
    scope = _scope(spec, scope_index)
    _, categories, _ = SCOPE_SPECS[scope_index]
    request = SelectionRelativeConditions(
        channel="short-video",
        period="7d",
        industry_id=scope.industry_id,
        category_ids=categories,
        brand="all",
        price_mode="all",
        first_listed_only=False,
        rank_from=1,
        rank_to=200,
    )
    schedule = SelectionStrategySchedule(
        scheduled=strategy_index % 2 == 0,
        kind="hourly" if strategy_index % 2 == 0 else "daily",
        interval_hours=1 + strategy_index,
        daily_time=f"{9 + strategy_index:02d}:00",
    )
    return (
        SelectionStrategyConditions(request=request).model_dump(mode="json"),
        schedule.model_dump(mode="json"),
    )


def build_manifest(spec: DatasetSpec) -> dict[str, Any]:
    runs = build_run_plans(spec)
    receipt_run = representative_run_plan(spec, runs)
    team_candidates = [0] * TEAM_COUNT
    team_visible = [0] * TEAM_COUNT
    team_blocked_visible = [0] * TEAM_COUNT
    team_revoked = [0] * TEAM_COUNT
    observations = 0
    current_items = 0
    history_items = 0
    revoked_candidates = 0
    title_counts: Counter[str] = Counter()
    today_candidates = 0
    expected_queries: Counter[str] = Counter()
    for candidate in iter_candidate_plans(spec):
        team_candidates[candidate.team_index] += 1
        title_counts[candidate.title_kind] += 1
        revoked = candidate.observations[0].shop_slot == 3
        if revoked:
            revoked_candidates += 1
            team_revoked[candidate.team_index] += 1
        elif candidate.blocked:
            team_blocked_visible[candidate.team_index] += 1
        else:
            team_visible[candidate.team_index] += 1
        observations += len(candidate.observations)
        current_items += len(candidate.observations)
        history_items += sum(item.history_run_label is not None for item in candidate.observations)
        if any(item.checked_at.astimezone(ZoneInfo("Asia/Shanghai")).date() == spec.as_of for item in candidate.observations):
            today_candidates += 1
        if not candidate.blocked:
            expected_queries[f"search-{candidate.title_kind}"] += 1
        if candidate.team_index != 0:
            continue
        authorized = [item for item in candidate.observations if item.shop_slot < AUTHORIZED_SHOPS_PER_TEAM]
        if candidate.blocked:
            if any(item.shop_slot == 1 for item in authorized):
                expected_queries["team-shop1-blocked"] += 1
            continue
        if any(item.shop_slot == 0 for item in authorized):
            expected_queries["team-shop0"] += 1
        if any(item.scope_index == 0 for item in authorized):
            expected_queries["team-scope0"] += 1
        if any(
            _run_strategy_index(
                item.team_index,
                item.shop_slot,
                item.scope_index,
                int(item.run_label.split(":")[-1]),
            ) == 0
            for item in authorized
        ):
            expected_queries["team-strategy0"] += 1
        if any(item.run_label == receipt_run.label for item in authorized):
            expected_queries["team-receipt"] += 1
        if any(
            item.checked_at.astimezone(ZoneInfo("Asia/Shanghai")).date() == spec.as_of
            for item in authorized
        ):
            expected_queries["team-today-all"] += 1
            state = _discovery_state(spec, candidate.index)
            if state == "new":
                expected_queries["team-today-new"] += 1
            elif state == "known":
                expected_queries["team-today-known"] += 1
            else:
                expected_queries["team-today-unknown"] += 1
    result_items = current_items + history_items
    super_default = spec.candidate_count - sum(1 for item in iter_candidate_plans(spec) if item.blocked)
    return {
        "schema_version": 1,
        "run_id": str(spec.run_id),
        "seed": spec.seed,
        "as_of": spec.as_of.isoformat(),
        "tier": spec.candidate_count,
        "distribution": {
            "team_weights": list(TEAM_WEIGHTS),
            "team_candidates": team_candidates,
            "normal_team_visible_unblocked": team_visible,
            "normal_team_visible_blocked": team_blocked_visible,
            "normal_team_revoked": team_revoked,
            "revoked_shop_candidates": revoked_candidates,
            "title_kinds": dict(sorted(title_counts.items())),
        },
        "counts": {
            "users": TEAM_COUNT + 1,
            "teams": TEAM_COUNT,
            "memberships": TEAM_COUNT,
            "module_access": TEAM_COUNT,
            "shop_access": TEAM_COUNT * AUTHORIZED_SHOPS_PER_TEAM,
            "shops": TEAM_COUNT * SHOPS_PER_TEAM,
            "strategies": TEAM_COUNT * STRATEGIES_PER_TEAM,
            "candidates": spec.candidate_count,
            "observations": observations,
            "runs": len(runs),
            "result_items": result_items,
            "current_result_items": current_items,
            "historical_result_items": history_items,
            "super_default_visible_unblocked": super_default,
            "today_candidate_upper_bound": today_candidates,
        },
        "query_contract": {
            "default_page_size": 20,
            "search_terms": {
                "common": "容量常见商品",
                "rare": "容量稀有关键词 ZXQ",
                "none": "容量绝不匹配 QQQ-NO-RESULT",
            },
            "sorts": ["checked_at", "first_on_shelf_date", "rank"],
            "result_scopes": ["all", "today", "today_new", "today_known"],
            "representative_receipt_id": str(_run_id(spec, receipt_run.label)),
            "representative_strategy_id": str(_strategy_id(spec, 0, 0)),
            "expected_totals": dict(sorted(expected_queries.items())),
        },
        "acceptance": {
            "correctness_percent": 100,
            "http_errors": 0,
            "timeouts": 0,
            "formal_warm_samples_per_case": 30,
            "formal_concurrent_readers": 8,
            "formal_concurrent_writers": 1,
            "formal_concurrency_duration_seconds": 60,
            "statement_timeout_ms": 8_000,
            "warm_serial_api_p95_ms": 1_500,
            "warm_search_or_deep_api_p95_ms": 3_000,
            "mixed_8_read_1_write_p95_ms": 4_000,
            "separate_browser_after_response_p95_ms": 800,
            "browser_included_in_cli_acceptance": False,
        },
        "ownership": {
            "namespace": str(spec.run_id),
            "team_ids": [str(_team_id(spec, index)) for index in range(TEAM_COUNT)],
            "shop_ids": [
                str(_shop_id(spec, team_index, shop_slot))
                for team_index in range(TEAM_COUNT)
                for shop_slot in range(SHOPS_PER_TEAM)
            ],
            "user_ids": [str(_user_id(spec, index)) for index in range(TEAM_COUNT)] + [
                str(stable_id(spec.run_id, "user:super")),
            ],
        },
    }


def manifest_path(spec: DatasetSpec) -> Path:
    return REPOSITORY_ROOT / ".codex" / "product-selection-capacity" / str(spec.run_id) / f"manifest-{spec.candidate_count}.json"


def evidence_path(spec: DatasetSpec) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return REPOSITORY_ROOT / ".codex" / "product-selection-capacity" / str(spec.run_id) / f"measure-{spec.candidate_count}-{stamp}.json"


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def namespace_path(spec: DatasetSpec) -> Path:
    return REPOSITORY_ROOT / ".codex" / "product-selection-capacity" / str(spec.run_id) / "namespace.json"


def target_path(spec: DatasetSpec) -> Path:
    return namespace_path(spec).with_name("target.json")


def ensure_namespace(spec: DatasetSpec) -> None:
    path = namespace_path(spec)
    expected = {
        "schema_version": 1,
        "run_id": str(spec.run_id),
        "seed": spec.seed,
        "as_of": spec.as_of.isoformat(),
    }
    if path.exists():
        current = json.loads(path.read_text(encoding="utf-8"))
        if current != expected:
            raise CapacityToolError("run namespace already exists with different seed or as-of date")
        return
    write_json(path, expected)


def require_namespace(spec: DatasetSpec) -> None:
    path = namespace_path(spec)
    if not path.exists():
        raise CapacityToolError("offline plan must be created before measure or cleanup")
    current = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        "schema_version": 1,
        "run_id": str(spec.run_id),
        "seed": spec.seed,
        "as_of": spec.as_of.isoformat(),
    }
    if current != expected:
        raise CapacityToolError("run namespace does not match seed or as-of date")


def bind_target(spec: DatasetSpec, args: argparse.Namespace, *, create: bool) -> None:
    path = target_path(spec)
    expected = {
        "schema_version": 1,
        "database": args.expected_database,
        "endpoint": args.expected_endpoint,
        "migration_head": args.expected_head,
    }
    if not path.exists():
        if not create:
            raise CapacityToolError("seed must bind the registered target before measure or cleanup")
        write_json(path, expected)
        return
    current = json.loads(path.read_text(encoding="utf-8"))
    if current != expected:
        raise CapacityToolError("run namespace is already bound to a different database target")


def _database_url() -> URL:
    configured = get_settings().database_url
    if configured is None:
        raise CapacityToolError("BACKEND_DATABASE_URL is required for database commands")
    value = make_url(str(configured))
    if not value.drivername.startswith("postgresql"):
        raise CapacityToolError("capacity commands require PostgreSQL")
    return value


def validate_target_arguments(
    *, allow_capacity_test: bool, expected_database: str | None,
    expected_endpoint: str | None, expected_head: str | None, url: URL,
) -> None:
    if not allow_capacity_test:
        raise CapacityToolError("database commands require --allow-capacity-test")
    if not expected_database or not expected_endpoint or not expected_head:
        raise CapacityToolError("exact database, endpoint, and Migration head confirmations are required")
    if not CAPACITY_DATABASE.fullmatch(expected_database):
        raise CapacityToolError("only a control_center_capacity_* database is allowed")
    if url.database != expected_database:
        raise CapacityToolError("configured database does not match --expected-database")
    actual_endpoint = f"{url.host or ''}:{url.port or 5432}"
    if actual_endpoint != expected_endpoint:
        raise CapacityToolError("configured PostgreSQL endpoint does not match --expected-endpoint")


def guarded_engine(args: argparse.Namespace) -> Engine:
    url = _database_url()
    validate_target_arguments(
        allow_capacity_test=args.allow_capacity_test,
        expected_database=args.expected_database,
        expected_endpoint=args.expected_endpoint,
        expected_head=args.expected_head,
        url=url,
    )
    engine = create_database_engine(get_settings())
    engine.hide_parameters = True
    with engine.connect() as connection:
        database, head = connection.execute(text(
            "SELECT current_database(), (SELECT version_num FROM alembic_version)",
        )).one()
        if database != args.expected_database:
            raise CapacityToolError("server database identity changed after connection")
        if head != args.expected_head:
            raise CapacityToolError("Migration head does not match --expected-head")
    return engine


def install_statement_timeout(engine: Engine, milliseconds: int) -> None:
    if getattr(engine, "_capacity_timeout_installed", False):
        return

    @event.listens_for(engine, "checkout")
    def set_capacity_session_limits(dbapi_connection, _record, _proxy):
        with dbapi_connection.cursor() as cursor:
            cursor.execute(f"SET statement_timeout = '{milliseconds}ms'")
            cursor.execute("SET application_name = 'product-selection-capacity'")

    setattr(engine, "_capacity_timeout_installed", True)


def acquire_database_run_lock(engine: Engine, spec: DatasetSpec):
    key = spec.run_id.int % ((1 << 63) - 1)
    connection = engine.connect()
    try:
        locked = connection.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": key})
        if not locked:
            raise CapacityToolError("another capacity command owns this run namespace")
        return connection, key
    except Exception:
        connection.close()
        raise


def release_database_run_lock(connection: Any, key: int) -> None:
    try:
        connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": key})
    finally:
        connection.close()


def _set_statement_timeout(connection: Any, milliseconds: int) -> None:
    connection.exec_driver_sql(f"SET LOCAL statement_timeout = '{milliseconds}ms'")


def _chunks(rows: Iterable[dict[str, Any]], size: int) -> Iterator[list[dict[str, Any]]]:
    current: list[dict[str, Any]] = []
    for row in rows:
        current.append(row)
        if len(current) == size:
            yield current
            current = []
    if current:
        yield current


def _insert_chunks(
    engine: Engine,
    table: Any,
    rows: Iterable[dict[str, Any]],
    *,
    chunk_size: int,
    statement_timeout_ms: int,
) -> int:
    affected = 0
    for chunk in _chunks(rows, chunk_size):
        with engine.begin() as connection:
            _set_statement_timeout(connection, statement_timeout_ms)
            result = connection.execute(
                postgresql_insert(table).values(chunk).on_conflict_do_nothing(),
            )
            affected += max(result.rowcount or 0, 0)
    return affected


def _upsert_run_chunks(
    engine: Engine,
    rows: Iterable[dict[str, Any]],
    *,
    chunk_size: int,
    statement_timeout_ms: int,
) -> int:
    """Insert deterministic runs and repair only mutable counts on tier growth."""
    affected = 0
    for chunk in _chunks(rows, chunk_size):
        statement = postgresql_insert(SelectionRun.__table__).values(chunk)
        incoming = statement.excluded
        with engine.begin() as connection:
            _set_statement_timeout(connection, statement_timeout_ms)
            result = connection.execute(statement.on_conflict_do_update(
                index_elements=[SelectionRun.run_id],
                set_={
                    "status": incoming.status,
                    "result_count": incoming.result_count,
                    "saved_count": incoming.saved_count,
                    "supplemented_count": incoming.supplemented_count,
                    "supplement_failed_count": incoming.supplement_failed_count,
                    "error_code": incoming.error_code,
                    "error_stage": incoming.error_stage,
                    "updated_at": incoming.updated_at,
                },
            ))
            affected += max(result.rowcount or 0, 0)
    return affected


def _verify_unshared_selection_rows(engine: Engine, spec: DatasetSpec) -> None:
    team_ids = [_team_id(spec, index) for index in range(TEAM_COUNT)]
    candidate_ids = select(Candidate.candidate_id).where(Candidate.team_id.in_(team_ids))
    run_ids = select(SelectionRun.run_id).where(SelectionRun.team_id.in_(team_ids))
    checks = {
        "candidate": select(func.count()).select_from(Candidate).where(Candidate.team_id.not_in(team_ids)),
        "strategy": select(func.count()).select_from(Strategy).where(Strategy.team_id.not_in(team_ids)),
        "run": select(func.count()).select_from(SelectionRun).where(SelectionRun.team_id.not_in(team_ids)),
        "observation": select(func.count()).select_from(Observation).where(Observation.candidate_id.not_in(candidate_ids)),
        "result": select(func.count()).select_from(ResultItem).where(ResultItem.execution_run_id.not_in(run_ids)),
    }
    with engine.connect() as connection:
        foreign = {name: connection.scalar(statement) or 0 for name, statement in checks.items()}
        other_super = connection.scalar(select(func.count()).select_from(User).where(
            User.is_super_account.is_(True),
            User.user_id != stable_id(spec.run_id, "user:super"),
        )) or 0
    if any(foreign.values()) or other_super:
        raise CapacityToolError(
            "target contains selection rows or a super account outside this run namespace",
        )


def _verify_existing_namespace_anchors(
    engine: Engine,
    base: Mapping[str, Sequence[dict[str, Any]]],
) -> None:
    checks = (
        (
            Team,
            "team_id",
            base["teams"],
            ("name", "enabled"),
        ),
        (
            User,
            "user_id",
            base["users"],
            ("login_name", "display_name", "password_hash", "enabled", "is_super_account"),
        ),
        (
            Shop,
            "shop_id",
            base["shops"],
            (
                "platform_shop_id",
                "display_name",
                "platform",
                "enabled",
                "owner_user_id",
                "deleted_at",
            ),
        ),
        (
            Strategy,
            "strategy_id",
            base["strategies"],
            (
                "team_id",
                "request_shop_id",
                "name",
                "version",
                "enabled",
                "conditions",
                "schedule_config",
            ),
        ),
    )
    with Session(engine) as session:
        for model, key_name, expected_rows, fields in checks:
            key = getattr(model, key_name)
            expected = {row[key_name]: row for row in expected_rows}
            existing = session.scalars(select(model).where(key.in_(expected))).all()
            for row in existing:
                values = expected[getattr(row, key_name)]
                if any(getattr(row, field) != values[field] for field in fields):
                    raise CapacityToolError(
                        f"target contains a conflicting deterministic {model.__tablename__} row",
                    )


def _base_rows(spec: DatasetSpec) -> dict[str, list[dict[str, Any]]]:
    stamp = datetime.combine(spec.as_of, time(1), tzinfo=UTC)
    teams = [
        {
            "team_id": _team_id(spec, index),
            "name": f"capacity-{spec.run_id}-team-{index}",
            "enabled": True,
            "created_at": stamp,
            "updated_at": stamp,
        }
        for index in range(TEAM_COUNT)
    ]
    users = [
        {
            "user_id": _user_id(spec, index),
            "display_name": f"capacity-{spec.run_id}-user-{index}",
            "login_name": f"capacity-{spec.run_id.hex[:12]}-{index}",
            "password_hash": None,
            "enabled": True,
            "is_super_account": False,
            "created_at": stamp,
            "updated_at": stamp,
        }
        for index in range(TEAM_COUNT)
    ]
    users.append({
        "user_id": stable_id(spec.run_id, "user:super"),
        "display_name": f"capacity-{spec.run_id}-super",
        "login_name": f"capacity-{spec.run_id.hex[:12]}-super",
        "password_hash": None,
        "enabled": True,
        "is_super_account": True,
        "created_at": stamp,
        "updated_at": stamp,
    })
    shops = [
        {
            "shop_id": _shop_id(spec, team_index, shop_slot),
            "display_name": f"capacity-{spec.run_id}-shop-{team_index}-{shop_slot}",
            "platform": ShopPlatform.DOUYIN,
            "platform_shop_id": f"capacity-{spec.run_id.hex[:12]}-{team_index}-{shop_slot}",
            "enabled": True,
            "owner_user_id": None,
            "deleted_at": None,
            "created_at": stamp,
            "updated_at": stamp,
        }
        for team_index in range(TEAM_COUNT)
        for shop_slot in range(SHOPS_PER_TEAM)
    ]
    memberships = [
        {
            "membership_id": _membership_id(spec, index),
            "team_id": _team_id(spec, index),
            "user_id": _user_id(spec, index),
            "role_code": DEFAULT_ROLE_CODE,
            "data_scope": DataScope.TEAM.value,
            "enabled": True,
            "created_at": stamp,
            "updated_at": stamp,
        }
        for index in range(TEAM_COUNT)
    ]
    module_access = [
        {
            "team_id": _team_id(spec, index),
            "module_code": ModuleCode.PRODUCT_SELECTION.value,
            "created_at": stamp,
        }
        for index in range(TEAM_COUNT)
    ]
    shop_access = [
        {
            "team_id": _team_id(spec, team_index),
            "shop_id": _shop_id(spec, team_index, shop_slot),
            "created_at": stamp,
        }
        for team_index in range(TEAM_COUNT)
        for shop_slot in range(AUTHORIZED_SHOPS_PER_TEAM)
    ]
    strategies: list[dict[str, Any]] = []
    for team_index in range(TEAM_COUNT):
        for strategy_index in range(STRATEGIES_PER_TEAM):
            conditions, schedule = _strategy_payload(spec, team_index, strategy_index)
            strategies.append({
                "strategy_id": _strategy_id(spec, team_index, strategy_index),
                "team_id": _team_id(spec, team_index),
                "created_by_user_id": _user_id(spec, team_index),
                "request_shop_id": _shop_id(spec, team_index, strategy_index // len(SCOPE_SPECS)),
                "name": f"capacity strategy {team_index}-{strategy_index}",
                "version": 1,
                "enabled": True,
                "conditions": conditions,
                "schedule_config": schedule,
                "created_at": stamp + timedelta(minutes=strategy_index),
                "updated_at": stamp + timedelta(minutes=strategy_index),
            })
    return {
        "teams": teams,
        "users": users,
        "shops": shops,
        "memberships": memberships,
        "module_access": module_access,
        "shop_access": shop_access,
        "strategies": strategies,
    }


def _run_rows(spec: DatasetSpec, plans: Mapping[str, RunPlan]) -> Iterator[dict[str, Any]]:
    for label in sorted(plans):
        plan = plans[label]
        request = _request(spec, plan)
        occurred_at = plan.occurred_at
        partial = plan.supplement_failed_count > 0
        yield {
            "run_id": _run_id(spec, label),
            "operation_kind": "rank",
            "target_observation_id": None,
            "result_detail_version": 1,
            "team_id": _team_id(spec, plan.team_index),
            "created_by_user_id": _user_id(spec, plan.team_index),
            "request_shop_id": _shop_id(spec, plan.team_index, plan.shop_slot),
            "submission_key": stable_id(spec.run_id, f"submission:{label}"),
            "strategy_id": (
                _strategy_id(spec, plan.team_index, plan.strategy_index)
                if plan.strategy_index is not None else None
            ),
            "reused_run_id": None,
            "request_fingerprint": request.fingerprint(),
            "request_conditions": request.model_dump(mode="json"),
            "status": "partial" if partial else "succeeded",
            "stage": "completed",
            "result_count": plan.item_count,
            "saved_count": plan.item_count,
            "supplemented_count": plan.supplemented_count,
            "supplement_failed_count": plan.supplement_failed_count,
            "error_code": "PRODUCT_SELECTION_BASIC_INFO_PARTIAL" if partial else None,
            "error_stage": "basic_info" if partial else None,
            "platform_business_code": None,
            "started_at": occurred_at - timedelta(seconds=3),
            "finished_at": occurred_at + timedelta(seconds=2),
            "lease_id": None,
            "lease_expires_at": None,
            "created_at": occurred_at - timedelta(seconds=4),
            "updated_at": occurred_at + timedelta(seconds=2),
        }


def _candidate_rows(spec: DatasetSpec) -> Iterator[dict[str, Any]]:
    for candidate in iter_candidate_plans(spec):
        created_at = min(item.checked_at for item in candidate.observations) - timedelta(days=7)
        updated_at = max(item.checked_at for item in candidate.observations)
        yield {
            "candidate_id": _candidate_id(spec, candidate.index),
            "team_id": _team_id(spec, candidate.team_index),
            "created_by_user_id": _user_id(spec, candidate.team_index),
            "platform": "douyin",
            "platform_product_id": _product_id(candidate.index),
            "blocked": candidate.blocked,
            "blocked_changed_at": updated_at if candidate.blocked else None,
            "blocked_changed_by_user_id": _user_id(spec, candidate.team_index) if candidate.blocked else None,
            "discovery_tracking_version": 1,
            "created_at": created_at,
            "updated_at": updated_at,
        }


def _observation_rows(spec: DatasetSpec) -> Iterator[dict[str, Any]]:
    for candidate in iter_candidate_plans(spec):
        for observation in candidate.observations:
            checked_at = observation.checked_at
            scope = _scope(spec, observation.scope_index)
            _, _, category = SCOPE_SPECS[observation.scope_index]
            status, version, retrieved_at = _basic_status(candidate.index, checked_at)
            yield {
                "observation_id": _observation_id(spec, candidate.index, observation.variant),
                "candidate_id": _candidate_id(spec, candidate.index),
                "request_shop_id": _shop_id(spec, observation.team_index, observation.shop_slot),
                "last_run_id": _run_id(spec, observation.run_label),
                "source_scope_hash": scope.fingerprint(),
                "source_context": scope.context(),
                "period_begin": scope.period_begin,
                "period_end": scope.period_end,
                "title": _title(candidate),
                "image_url": CAPACITY_IMAGE_DATA_URL,
                "source_url": f"https://capacity.invalid/product/{_product_id(candidate.index)}",
                "merchant_snapshot": [{
                    "platform_shop_id": f"merchant-{candidate.team_index}-{candidate.index % 97}",
                    "name": f"容量商家 {candidate.index % 97}",
                }],
                "category_path": list(category) if version else None,
                "price_band": f"{candidate.index % 100}-{candidate.index % 100 + 50}",
                "rank": candidate.index % 200 + 1,
                "previous_rank": (candidate.index + 3) % 200 + 1,
                "previous_checked_at": checked_at - timedelta(days=1),
                "newly_on_ranking": candidate.index % 11 == 0,
                "first_seen_at": checked_at - timedelta(days=7),
                "checked_at": checked_at,
                "metrics_retrieved_at": checked_at,
                "video_metric_ranges": _metrics(candidate.index, checked_at),
                "first_on_shelf_date": (spec.as_of - timedelta(days=candidate.index % 365)) if version and candidate.index % 10 != 1 else None,
                "bad_comment_rate_raw": Decimal(candidate.index % 50) / Decimal(10_000) if version and candidate.index % 10 != 1 else None,
                "bad_comment_rate_unit": 4 if version and candidate.index % 10 != 1 else None,
                "basic_info_retrieved_at": retrieved_at,
                "last_attempt_at": checked_at,
                "last_successful_request_started_at": checked_at - timedelta(seconds=3),
                "last_error_code": status["error_code"] if status else None,
                "last_error_stage": status["error_stage"] if status else None,
                "basic_info_status": status,
                "basic_info_version": version,
                "created_at": checked_at - timedelta(days=7),
                "updated_at": checked_at,
            }


def _result_rows(spec: DatasetSpec) -> Iterator[dict[str, Any]]:
    for candidate in iter_candidate_plans(spec):
        for observation in candidate.observations:
            checked_at = observation.checked_at
            state = _discovery_state(spec, candidate.index)
            discovery_scope_hash = discovery_key(
                _team_id(spec, candidate.team_index),
                _original_request(
                    spec,
                    team_index=candidate.team_index,
                    shop_slot=observation.shop_slot,
                    scope_index=observation.scope_index,
                ),
            )
            current_snapshot = {
                "version": 1,
                "rank": candidate.index % 200 + 1,
                "previous_rank": (candidate.index + 3) % 200 + 1,
                "previous_checked_at": (checked_at - timedelta(days=1)).isoformat(),
                "price_band": f"{candidate.index % 100}-{candidate.index % 100 + 50}",
                "newly_on_ranking": candidate.index % 11 == 0,
                "video_metric_ranges": _metrics(candidate.index, checked_at),
            }
            yield {
                "item_id": _result_item_id(spec, candidate.index, observation.variant, False),
                "execution_run_id": _run_id(spec, observation.run_label),
                "observation_id": _observation_id(spec, candidate.index, observation.variant),
                "discovery_scope_hash": discovery_scope_hash,
                "discovery_state": state,
                "hit_at": checked_at,
                "snapshot": current_snapshot,
            }
            if observation.history_run_label is not None:
                historical_at = checked_at - timedelta(days=7)
                historical = dict(current_snapshot)
                historical.update(
                    rank=(candidate.index + 5) % 200 + 1,
                    previous_rank=None,
                    previous_checked_at=None,
                    newly_on_ranking=False,
                    video_metric_ranges=_metrics(candidate.index + 1, historical_at),
                )
                yield {
                    "item_id": _result_item_id(spec, candidate.index, observation.variant, True),
                    "execution_run_id": _run_id(spec, observation.history_run_label),
                    "observation_id": _observation_id(spec, candidate.index, observation.variant),
                    "discovery_scope_hash": discovery_scope_hash,
                    "discovery_state": "known",
                    "hit_at": historical_at,
                    "snapshot": historical,
                }


def seed_dataset(engine: Engine, spec: DatasetSpec, *, chunk_size: int, statement_timeout_ms: int) -> dict[str, Any]:
    ensure_namespace(spec)
    manifest = build_manifest(spec)
    manifest["state"] = "seeding"
    write_json(manifest_path(spec), manifest)
    _verify_unshared_selection_rows(engine, spec)
    base = _base_rows(spec)
    _verify_existing_namespace_anchors(engine, base)
    for table, key in (
        (Team.__table__, "teams"),
        (User.__table__, "users"),
        (Shop.__table__, "shops"),
        (TeamMembership.__table__, "memberships"),
        (TeamModuleAccess.__table__, "module_access"),
        (TeamShopAccess.__table__, "shop_access"),
        (Strategy.__table__, "strategies"),
    ):
        _insert_chunks(
            engine,
            table,
            base[key],
            chunk_size=chunk_size,
            statement_timeout_ms=statement_timeout_ms,
        )
    plans = build_run_plans(spec)
    _upsert_run_chunks(
        engine,
        _run_rows(spec, plans),
        chunk_size=chunk_size,
        statement_timeout_ms=statement_timeout_ms,
    )
    for table, rows in (
        (Candidate.__table__, _candidate_rows(spec)),
        (Observation.__table__, _observation_rows(spec)),
        (ResultItem.__table__, _result_rows(spec)),
    ):
        _insert_chunks(
            engine,
            table,
            rows,
            chunk_size=chunk_size,
            statement_timeout_ms=statement_timeout_ms,
        )
    with engine.begin() as connection:
        _set_statement_timeout(connection, statement_timeout_ms)
        for table in (Candidate, Observation, SelectionRun, ResultItem, Strategy):
            connection.execute(text(f"ANALYZE {table.__tablename__}"))
    actual = dataset_counts(engine, spec)
    expected = manifest["counts"]
    for key in (
        "users",
        "teams",
        "memberships",
        "module_access",
        "shop_access",
        "shops",
        "strategies",
        "candidates",
        "observations",
        "runs",
        "result_items",
    ):
        if actual[key] != expected[key]:
            raise CapacityToolError(f"seed verification failed for {key}: {actual[key]} != {expected[key]}")
    manifest["state"] = "seeded"
    manifest["verified_counts"] = actual
    manifest["seeded_at"] = datetime.now(UTC).isoformat()
    write_json(manifest_path(spec), manifest)
    return manifest


def dataset_counts(engine: Engine, spec: DatasetSpec) -> dict[str, int]:
    team_ids = [_team_id(spec, index) for index in range(TEAM_COUNT)]
    user_ids = [_user_id(spec, index) for index in range(TEAM_COUNT)] + [
        stable_id(spec.run_id, "user:super"),
    ]
    candidate_ids = select(Candidate.candidate_id).where(Candidate.team_id.in_(team_ids))
    run_ids = select(SelectionRun.run_id).where(SelectionRun.team_id.in_(team_ids))
    with engine.connect() as connection:
        return {
            "users": connection.scalar(select(func.count()).select_from(User).where(
                User.user_id.in_(user_ids),
            )) or 0,
            "teams": connection.scalar(select(func.count()).select_from(Team).where(Team.team_id.in_(team_ids))) or 0,
            "memberships": connection.scalar(select(func.count()).select_from(TeamMembership).where(
                TeamMembership.team_id.in_(team_ids),
            )) or 0,
            "module_access": connection.scalar(select(func.count()).select_from(TeamModuleAccess).where(
                TeamModuleAccess.team_id.in_(team_ids),
            )) or 0,
            "shop_access": connection.scalar(select(func.count()).select_from(TeamShopAccess).where(
                TeamShopAccess.team_id.in_(team_ids),
            )) or 0,
            "shops": connection.scalar(select(func.count()).select_from(Shop).where(Shop.shop_id.in_([
                _shop_id(spec, team, shop) for team in range(TEAM_COUNT) for shop in range(SHOPS_PER_TEAM)
            ]))) or 0,
            "strategies": connection.scalar(select(func.count()).select_from(Strategy).where(Strategy.team_id.in_(team_ids))) or 0,
            "candidates": connection.scalar(select(func.count()).select_from(Candidate).where(Candidate.team_id.in_(team_ids))) or 0,
            "observations": connection.scalar(select(func.count()).select_from(Observation).where(Observation.candidate_id.in_(candidate_ids))) or 0,
            "runs": connection.scalar(select(func.count()).select_from(SelectionRun).where(SelectionRun.team_id.in_(team_ids))) or 0,
            "result_items": connection.scalar(select(func.count()).select_from(ResultItem).where(ResultItem.execution_run_id.in_(run_ids))) or 0,
        }


def _actor(engine: Engine, spec: DatasetSpec, team_index: int | None) -> ActorContext:
    user_id = stable_id(spec.run_id, "user:super") if team_index is None else _user_id(spec, team_index)
    with Session(engine) as session:
        return ActorContextService(session).resolve(
            user_id=user_id,
            requested_team_id=None if team_index is None else _team_id(spec, team_index),
        )


def _percentile(values: Sequence[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = max(0, math.ceil(quantile * len(ordered)) - 1)
    return ordered[position]


def _sql_category(statement: str) -> str:
    normalized = " ".join(statement.lower().split())
    if "count(" in normalized:
        return "count"
    if normalized.startswith("select") and "product_selection" in normalized:
        return "selection_read"
    if normalized.startswith(("insert", "update", "delete")):
        return "write"
    return normalized.split(" ", 1)[0] if normalized else "unknown"


def install_sql_probe(engine: Engine) -> None:
    if getattr(engine, "_selection_capacity_probe", False):
        return

    @event.listens_for(engine, "before_cursor_execute")
    def before_cursor_execute(_connection, _cursor, _statement, _parameters, context, _many):
        if _sql_samples.get() is not None:
            context._selection_capacity_started = monotonic_time.perf_counter()

    @event.listens_for(engine, "after_cursor_execute")
    def after_cursor_execute(_connection, _cursor, statement, parameters, context, _many):
        samples = _sql_samples.get()
        started = getattr(context, "_selection_capacity_started", None)
        if samples is None or started is None:
            return
        samples.append(SqlSample(
            category=_sql_category(statement),
            duration_ms=(monotonic_time.perf_counter() - started) * 1_000,
            statement_hash=sha256(" ".join(statement.split()).encode()).hexdigest(),
            statement=statement,
            parameters=parameters,
        ))

    setattr(engine, "_selection_capacity_probe", True)


@contextmanager
def collect_sql() -> Iterator[list[SqlSample]]:
    samples: list[SqlSample] = []
    token = _sql_samples.set(samples)
    try:
        yield samples
    finally:
        _sql_samples.reset(token)


def _first_run_for(engine: Engine, spec: DatasetSpec, *, team_index: int = 0) -> tuple[UUID, UUID]:
    strategy_id = _strategy_id(spec, team_index, 0)
    with Session(engine) as session:
        row = session.scalar(select(SelectionRun).where(
            SelectionRun.team_id == _team_id(spec, team_index),
            SelectionRun.strategy_id == strategy_id,
            SelectionRun.reused_run_id.is_(None),
        ).order_by(SelectionRun.created_at.desc(), SelectionRun.run_id).limit(1))
        if row is None:
            raise CapacityToolError("seeded strategy run is missing")
        return strategy_id, row.run_id


def measurement_cases(engine: Engine, spec: DatasetSpec) -> list[dict[str, Any]]:
    manifest = build_manifest(spec)
    strategy_id, receipt_id = _first_run_for(engine, spec)
    expected = manifest["query_contract"]["expected_totals"]
    team_total = manifest["distribution"]["normal_team_visible_unblocked"][0]
    small_team_total = manifest["distribution"]["normal_team_visible_unblocked"][7]
    super_total = manifest["counts"]["super_default_visible_unblocked"]
    team_last = max(1, math.ceil(team_total / 20))
    super_last = max(1, math.ceil(super_total / 20))
    return [
        {"name": "team-default-first", "team": 0, "params": {"page": 1, "page_size": 20}, "expected": team_total},
        {"name": "team-default-middle", "team": 0, "params": {"page": max(1, math.ceil(team_last / 2)), "page_size": 20}, "expected": team_total},
        {"name": "team-default-deep", "team": 0, "params": {"page": max(1, math.ceil(team_last * 0.9)), "page_size": 20}, "expected": team_total},
        {"name": "team-default-last", "team": 0, "params": {"page": team_last, "page_size": 20}, "expected": team_total},
        {"name": "small-team-default", "team": 7, "params": {"page": 1, "page_size": 20}, "expected": small_team_total},
        {"name": "super-default-first", "team": None, "params": {"page": 1, "page_size": 20}, "expected": super_total},
        {"name": "super-default-middle", "team": None, "params": {"page": max(1, math.ceil(super_last / 2)), "page_size": 20}, "expected": super_total},
        {"name": "super-default-deep", "team": None, "params": {"page": max(1, math.ceil(super_last * 0.9)), "page_size": 20}, "expected": super_total},
        {"name": "super-default-last", "team": None, "params": {"page": super_last, "page_size": 20}, "expected": super_total},
        {"name": "search-common", "team": None, "params": {"page": 1, "page_size": 20, "search": "容量常见商品"}, "expected": expected["search-common"]},
        {"name": "search-rare", "team": None, "params": {"page": 1, "page_size": 20, "search": "容量稀有关键词 ZXQ"}, "expected": expected["search-rare"]},
        {"name": "search-none", "team": None, "params": {"page": 1, "page_size": 20, "search": "容量绝不匹配 QQQ-NO-RESULT"}, "expected": 0},
        {"name": "team-shop", "team": 0, "params": {"page": 1, "page_size": 20, "shop_id": str(_shop_id(spec, 0, 0))}, "expected": expected["team-shop0"]},
        {"name": "team-revoked-shop", "team": 0, "params": {"page": 1, "page_size": 20, "shop_id": str(_shop_id(spec, 0, 3))}, "expected": 0},
        {"name": "team-source-scope", "team": 0, "params": {"page": 1, "page_size": 20, "source_scope_hash": _scope(spec, 0).fingerprint()}, "expected": expected["team-scope0"]},
        {"name": "team-blocked", "team": 0, "params": {"page": 1, "page_size": 20, "blocked": True}, "expected": manifest["distribution"]["normal_team_visible_blocked"][0]},
        {"name": "strategy", "team": 0, "params": {"page": 1, "page_size": 20, "strategy_id": str(strategy_id)}, "expected": expected["team-strategy0"]},
        {"name": "receipt", "team": 0, "params": {"page": 1, "page_size": 20, "receipt_id": str(receipt_id)}, "expected": expected["team-receipt"]},
        {"name": "today-all", "team": 0, "params": {"page": 1, "page_size": 20, "result_scope": "today"}, "expected": expected["team-today-all"]},
        {"name": "today-new-rank", "team": 0, "params": {"page": 1, "page_size": 20, "result_scope": "today_new", "sort_field": "rank", "sort_direction": "asc"}, "expected": expected["team-today-new"]},
        {"name": "today-known", "team": 0, "params": {"page": 1, "page_size": 20, "result_scope": "today_known"}, "expected": expected["team-today-known"]},
        {"name": "checked-at-asc", "team": 0, "params": {"page": 1, "page_size": 20, "sort_field": "checked_at", "sort_direction": "asc"}, "expected": team_total},
        {"name": "shelf-date-asc", "team": 0, "params": {"page": 1, "page_size": 20, "sort_field": "first_on_shelf_date", "sort_direction": "asc"}, "expected": team_total},
        {"name": "shelf-date-desc", "team": 0, "params": {"page": 1, "page_size": 20, "sort_field": "first_on_shelf_date", "sort_direction": "desc"}, "expected": team_total},
        {"name": "rank-asc", "team": 0, "params": {"page": 1, "page_size": 20, "sort_field": "rank", "sort_direction": "asc"}, "expected": team_total},
        {"name": "rank-desc", "team": 0, "params": {"page": 1, "page_size": 20, "sort_field": "rank", "sort_direction": "desc"}, "expected": team_total},
        {"name": "shop-blocked-rank", "team": 0, "params": {"page": 1, "page_size": 20, "shop_id": str(_shop_id(spec, 0, 1)), "blocked": True, "sort_field": "rank", "sort_direction": "desc"}, "expected": expected["team-shop1-blocked"]},
    ]


def _service_params(params: Mapping[str, Any]) -> dict[str, Any]:
    page = int(params.get("page", 1))
    page_size = int(params.get("page_size", 20))
    return {
        "shop_id": UUID(params["shop_id"]) if params.get("shop_id") else None,
        "blocked": bool(params.get("blocked", False)),
        "result_scope": params.get("result_scope", "all"),
        "strategy_id": UUID(params["strategy_id"]) if params.get("strategy_id") else None,
        "receipt_id": UUID(params["receipt_id"]) if params.get("receipt_id") else None,
        "scope_hash": params.get("source_scope_hash"),
        "search": params.get("search"),
        "offset": (page - 1) * page_size,
        "limit": page_size,
        "sort": params.get("sort_field", "checked_at"),
        "descending": params.get("sort_direction", "desc") == "desc",
    }


def run_repository_case(engine: Engine, actor: ActorContext, case: Mapping[str, Any]) -> dict[str, Any]:
    with collect_sql() as sql:
        started = monotonic_time.perf_counter()
        with Session(engine) as session:
            rows, total, _context = SelectionResultService(session).list(
                actor,
                **_service_params(case["params"]),
            )
        duration_ms = (monotonic_time.perf_counter() - started) * 1_000
    expected = case.get("expected")
    if expected is not None and total != expected:
        raise CapacityToolError(f"{case['name']} total mismatch: {total} != {expected}")
    return {
        "duration_ms": duration_ms,
        "total": total,
        "observation_ids": [str(row.observation_id) for row in rows],
        "sql": [asdict(item) | {"statement": None, "parameters": None} for item in sql],
        "_raw_sql": sql,
    }


def _api_client(engine: Engine, spec: DatasetSpec, team_index: int | None) -> TestClient:
    from fastapi.testclient import TestClient
    from app.core.database import get_database_session
    from app.main import create_app
    from app.modules.access.auth import get_human_principal

    application = create_app()
    user_id = stable_id(spec.run_id, "user:super") if team_index is None else _user_id(spec, team_index)

    def session_dependency():
        with Session(engine) as session:
            yield session

    application.dependency_overrides[get_database_session] = session_dependency
    application.dependency_overrides[get_human_principal] = lambda: HumanPrincipal(
        user_id=user_id,
        display_name="capacity-api-user",
    )
    # Deliberately do not enter TestClient as a context manager: Starlette only
    # runs lifespan in that form, and capacity reads must not start schedulers,
    # collectors, or executors. Requests still traverse the formal ASGI route.
    return TestClient(application)


def run_api_case(
    engine: Engine,
    spec: DatasetSpec,
    case: Mapping[str, Any],
    *,
    client: TestClient | None = None,
) -> dict[str, Any]:
    owned_client = client is None
    client = client or _api_client(engine, spec, case["team"])
    headers = {}
    if case["team"] is not None:
        headers["X-Team-ID"] = str(_team_id(spec, int(case["team"])))
    try:
        started = monotonic_time.perf_counter()
        response = client.get(
            "/api/v1/product-selection/candidates",
            params=case["params"],
            headers=headers,
        )
        duration_ms = (monotonic_time.perf_counter() - started) * 1_000
    finally:
        if owned_client:
            client.close()
    if response.status_code != 200:
        raise CapacityToolError(f"{case['name']} API returned HTTP {response.status_code}")
    payload = response.json()
    expected = case.get("expected")
    if expected is not None and payload["total"] != expected:
        raise CapacityToolError(f"{case['name']} API total mismatch: {payload['total']} != {expected}")
    return {
        "duration_ms": duration_ms,
        "total": payload["total"],
        "observation_ids": [item["observation_id"] for item in payload["items"]],
        "http_status": response.status_code,
    }


def validate_observation_scope(
    engine: Engine,
    spec: DatasetSpec,
    case: Mapping[str, Any],
    observation_ids: Sequence[str],
) -> None:
    if not observation_ids:
        return
    ids = [UUID(value) for value in observation_ids]
    with Session(engine) as session:
        rows = session.execute(select(
            Observation.observation_id,
            Candidate.team_id,
            Observation.request_shop_id,
        ).join(Candidate, Candidate.candidate_id == Observation.candidate_id).where(
            Observation.observation_id.in_(ids),
        )).all()
    if len(rows) != len(set(ids)):
        raise CapacityToolError(f"{case['name']} returned an observation outside this dataset")
    owned_teams = {_team_id(spec, index) for index in range(TEAM_COUNT)}
    if any(team_id not in owned_teams for _, team_id, _ in rows):
        raise CapacityToolError(f"{case['name']} leaked a foreign Team")
    if case["team"] is not None:
        team_index = int(case["team"])
        allowed_shops = {
            _shop_id(spec, team_index, shop_slot)
            for shop_slot in range(AUTHORIZED_SHOPS_PER_TEAM)
        }
        if any(
            team_id != _team_id(spec, team_index) or shop_id not in allowed_shops
            for _, team_id, shop_id in rows
        ):
            raise CapacityToolError(f"{case['name']} violated Team or Shop authorization")
    requested_shop = case["params"].get("shop_id")
    if requested_shop is not None and any(str(shop_id) != requested_shop for _, _, shop_id in rows):
        raise CapacityToolError(f"{case['name']} returned a different Shop")


def resource_snapshot(engine: Engine) -> dict[str, Any]:
    with engine.connect() as connection:
        database = connection.execute(text(
            "SELECT pg_database_size(current_database()), xact_commit, blks_read, blks_hit, "
            "tup_returned, tup_fetched FROM pg_stat_database WHERE datname = current_database()",
        )).one()
        relations = dict(connection.execute(text(
            "SELECT relname, pg_total_relation_size(relid) "
            "FROM pg_stat_user_tables WHERE relname LIKE 'product_selection_%' ORDER BY relname",
        )).all())
        connections = connection.scalar(text(
            "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()",
        ))
    return {
        "database_bytes": database[0],
        "xact_commit": database[1],
        "blocks_read": database[2],
        "blocks_hit": database[3],
        "tuples_returned": database[4],
        "tuples_fetched": database[5],
        "connections": connections,
        "relation_bytes": relations,
    }


def _writer_indices(spec: DatasetSpec) -> list[int]:
    result: list[int] = []
    for candidate in iter_candidate_plans(spec):
        primary = candidate.observations[0]
        if candidate.team_index == 0 and primary.shop_slot == 0 and primary.scope_index == 0:
            result.append(candidate.index)
            if len(result) == 10:
                return result
    raise CapacityToolError("writer fixture could not find ten target rows")


def run_synthetic_writer(engine: Engine, spec: DatasetSpec, stop: threading.Event, interval_seconds: float) -> dict[str, int]:
    indices = _writer_indices(spec)
    actor = _actor(engine, spec, 0)
    shop_id = _shop_id(spec, 0, 0)
    scope = _scope(spec, 0)
    writes = 0
    failures = 0
    zero = FieldObservation("available", CompassMetricRange((
        CompassRangeEndpoint(Decimal(0), "int", "count"),
        CompassRangeEndpoint(Decimal(0), "int", "count"),
    )))
    while not stop.is_set():
        at = datetime.now(UTC)
        products = tuple(CompassRankProduct(
            product_id=_product_id(index),
            title=_title_for_index(spec, index),
            image_url=CAPACITY_IMAGE_DATA_URL,
            rank=index % 200 + 1,
            price_band=f"{index % 100}-{index % 100 + 50}",
            merchants=(CompassMerchant(f"writer-{index}", "容量写入商家"),),
            leaf_category_id=SCOPE_SPECS[0][1][-1],
            newly_on_ranking=False,
            pay_amt=zero,
            pay_combo_cnt=zero,
            product_click_cnt=zero,
            video_cnt=zero,
        ) for index in indices)
        try:
            with Session(engine) as session:
                ProductSelectionFactService(session).persist_rank_page(
                    actor=actor,
                    shop_id=shop_id,
                    scope=scope,
                    page=CompassRankPage(products, 1, 10, spec.candidate_count),
                    started_at=at,
                    retrieved_at=at + timedelta(milliseconds=1),
                )
            writes += 1
        except Exception:
            failures += 1
        stop.wait(interval_seconds)
    return {"writes": writes, "failures": failures}


def run_concurrency(
    engine: Engine,
    spec: DatasetSpec,
    cases: Sequence[dict[str, Any]],
    *,
    readers: int,
    duration_seconds: int,
    with_writer: bool,
    writer_interval_seconds: float,
) -> dict[str, Any]:
    stop = threading.Event()
    durations: list[float] = []
    errors: Counter[str] = Counter()
    lock = threading.Lock()

    def reader(worker_index: int) -> None:
        index = worker_index
        clients = {
            team: _api_client(engine, spec, team)
            for team in {case["team"] for case in cases}
        }
        try:
            while not stop.is_set():
                case = cases[index % len(cases)]
                index += readers
                try:
                    result = run_api_case(engine, spec, case, client=clients[case["team"]])
                    with lock:
                        durations.append(result["duration_ms"])
                except Exception as error:
                    with lock:
                        errors[type(error).__name__] += 1
        finally:
            for client in clients.values():
                client.close()

    writer_result: dict[str, int] | None = None
    started = monotonic_time.perf_counter()
    with ThreadPoolExecutor(max_workers=readers + (1 if with_writer else 0)) as pool:
        futures = [pool.submit(reader, index) for index in range(readers)]
        writer_future = pool.submit(
            run_synthetic_writer,
            engine,
            spec,
            stop,
            writer_interval_seconds,
        ) if with_writer else None
        while monotonic_time.perf_counter() - started < duration_seconds:
            monotonic_time.sleep(0.1)
        stop.set()
        for future in futures:
            future.result()
        if writer_future is not None:
            writer_result = writer_future.result()
    elapsed = monotonic_time.perf_counter() - started
    return {
        "readers": readers,
        "duration_seconds": elapsed,
        "requests": len(durations),
        "errors": dict(errors),
        "p50_ms": _percentile(durations, 0.50),
        "p95_ms": _percentile(durations, 0.95),
        "max_ms": max(durations, default=0.0),
        "requests_per_second": len(durations) / elapsed if elapsed else 0.0,
        "writer": writer_result,
    }


def run_explain(engine: Engine, sample: SqlSample, statement_timeout_ms: int) -> Any:
    if not sample.statement.lstrip().lower().startswith("select"):
        raise CapacityToolError("only a captured SELECT can be explained")
    token = _sql_samples.set(None)
    try:
        with engine.begin() as connection:
            _set_statement_timeout(connection, statement_timeout_ms)
            row = connection.exec_driver_sql(
                "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + sample.statement,
                sample.parameters,
            ).scalar_one()
            return row
    finally:
        _sql_samples.reset(token)


def measure_dataset(
    engine: Engine,
    spec: DatasetSpec,
    *,
    samples: int,
    readers: int,
    duration_seconds: int,
    with_writer: bool,
    writer_interval_seconds: float,
    explain_case: str | None,
    statement_timeout_ms: int,
    profile: Literal["smoke", "formal"],
) -> dict[str, Any]:
    shanghai_today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    if spec.as_of != shanghai_today:
        raise CapacityToolError(
            "measure --as-of must equal the current Asia/Shanghai date for today filters",
        )
    install_sql_probe(engine)
    expected = build_manifest(spec)["counts"]
    actual = dataset_counts(engine, spec)
    for key in ("candidates", "observations", "runs", "result_items"):
        if actual[key] != expected[key]:
            raise CapacityToolError(f"dataset count mismatch before measure: {key}")
    cases = measurement_cases(engine, spec)
    before = resource_snapshot(engine)
    results: list[dict[str, Any]] = []
    case_errors: list[dict[str, str]] = []
    explain: dict[str, Any] | None = None
    with ExitStack() as stack:
        clients: dict[int | None, TestClient] = {}
        for team in {case["team"] for case in cases}:
            client = _api_client(engine, spec, team)
            stack.callback(client.close)
            clients[team] = client
        first_api_request = True
        for case in cases:
            try:
                api_first = run_api_case(engine, spec, case, client=clients[case["team"]])
                process_cold = first_api_request
                first_api_request = False
                actor = _actor(engine, spec, case["team"])
                repository_first = run_repository_case(engine, actor, case)
                warm_api = [
                    run_api_case(engine, spec, case, client=clients[case["team"]])
                    for _ in range(samples)
                ]
                validate_observation_scope(engine, spec, case, api_first["observation_ids"])
                stable = api_first["observation_ids"] == warm_api[-1]["observation_ids"]
                totals = {api_first["total"], *(item["total"] for item in warm_api)}
                if repository_first["observation_ids"] != api_first["observation_ids"]:
                    raise CapacityToolError(f"{case['name']} repository and API pages differ")
                if not stable or len(totals) != 1:
                    raise CapacityToolError(f"{case['name']} pagination/order changed between identical reads")
                adjacent_ids: list[str] = []
                page = int(case["params"].get("page", 1))
                page_size = int(case["params"].get("page_size", 20))
                if page * page_size < api_first["total"]:
                    adjacent_case = dict(case)
                    adjacent_case["expected"] = case.get("expected")
                    adjacent_case["params"] = dict(case["params"], page=page + 1)
                    adjacent = run_api_case(
                        engine,
                        spec,
                        adjacent_case,
                        client=clients[case["team"]],
                    )
                    adjacent_ids = adjacent["observation_ids"]
                    if set(api_first["observation_ids"]) & set(adjacent_ids):
                        raise CapacityToolError(f"{case['name']} overlaps its adjacent page")
                    validate_observation_scope(engine, spec, adjacent_case, adjacent_ids)
                result = {
                    "name": case["name"],
                    "params": case["params"],
                    "team": case["team"],
                    "total": api_first["total"],
                    "repository_first_ms": repository_first["duration_ms"],
                    "api_first_sample_ms": api_first["duration_ms"],
                    "api_process_cold": process_cold,
                    "api_warm_p50_ms": _percentile([item["duration_ms"] for item in warm_api], 0.50),
                    "api_warm_p95_ms": _percentile([item["duration_ms"] for item in warm_api], 0.95),
                    "api_warm_max_ms": max(item["duration_ms"] for item in warm_api),
                    "stable": stable,
                    "adjacent_page_checked": bool(adjacent_ids),
                    "sql": repository_first["sql"],
                }
                if explain_case == case["name"]:
                    raw = [
                        item for item in repository_first["_raw_sql"]
                        if item.category in {"count", "selection_read"}
                    ]
                    if not raw:
                        raise CapacityToolError("selected explain case captured no selection SQL")
                    slowest = max(raw, key=lambda item: item.duration_ms)
                    explain = {
                        "case": case["name"],
                        "statement_hash": slowest.statement_hash,
                        "captured_duration_ms": slowest.duration_ms,
                        "plan": run_explain(engine, slowest, statement_timeout_ms),
                    }
                results.append(result)
            except Exception as error:
                first_api_request = False
                case_errors.append({
                    "name": str(case["name"]),
                    "error_type": type(error).__name__,
                    "message": _safe_error(error),
                })
    concurrency = None
    if readers:
        concurrency = run_concurrency(
            engine,
            spec,
            cases,
            readers=readers,
            duration_seconds=duration_seconds,
            with_writer=with_writer,
            writer_interval_seconds=writer_interval_seconds,
        )
    after = resource_snapshot(engine)
    serial_checks = []
    for result in results:
        extended = any(
            marker in result["name"]
            for marker in ("search", "middle", "deep", "last")
        )
        threshold = 3_000 if extended else 1_500
        serial_checks.append({
            "name": result["name"],
            "threshold_ms": threshold,
            "actual_p95_ms": result["api_warm_p95_ms"],
            "passed": result["api_warm_p95_ms"] <= threshold,
        })
    concurrency_check = None
    if concurrency is not None:
        concurrency_check = {
            "threshold_ms": 4_000,
            "actual_p95_ms": concurrency["p95_ms"],
            "errors": concurrency["errors"],
            "passed": concurrency["p95_ms"] <= 4_000 and not concurrency["errors"],
        }
    acceptance_passed = (
        not case_errors
        and len(results) == len(cases)
        and all(item["passed"] for item in serial_checks)
        and (concurrency_check is None or concurrency_check["passed"])
    )
    formal_protocol_complete = (
        samples == 30
        and readers == 8
        and duration_seconds >= 60
        and with_writer
    )
    payload = {
        "schema_version": 1,
        "run_id": str(spec.run_id),
        "tier": spec.candidate_count,
        "as_of": spec.as_of.isoformat(),
        "measured_at": datetime.now(UTC).isoformat(),
        "profile": profile,
        "samples_per_case": samples,
        "cold_definition": (
            "only the first API request is process-cold; PostgreSQL buffers were not flushed; "
            "later per-case first samples are not labeled cold"
        ),
        "database": {"before": before, "after": after},
        "cases": results,
        "case_errors": case_errors,
        "concurrency": concurrency,
        "explain": explain,
        "acceptance": {
            "passed": acceptance_passed,
            "formal_protocol_complete": formal_protocol_complete,
            "serial": serial_checks,
            "concurrency": concurrency_check,
        },
        "browser_render": {"state": "not_measured_by_this_command"},
        "platform_requests": 0,
    }
    path = evidence_path(spec)
    write_json(path, payload)
    payload["evidence_path"] = str(path)
    return payload


def _delete_owned_chunks(
    engine: Engine,
    model: Any,
    primary_key: Any,
    condition: Any,
    *,
    chunk_size: int,
    statement_timeout_ms: int,
) -> int:
    removed = 0
    while True:
        batch = select(primary_key).where(condition).limit(chunk_size)
        with engine.begin() as connection:
            _set_statement_timeout(connection, statement_timeout_ms)
            result = connection.execute(delete(model).where(primary_key.in_(batch)))
            count = max(result.rowcount or 0, 0)
        removed += count
        if count == 0:
            return removed


def cleanup_dataset(engine: Engine, spec: DatasetSpec, *, statement_timeout_ms: int) -> dict[str, int]:
    team_ids = [_team_id(spec, index) for index in range(TEAM_COUNT)]
    user_ids = [_user_id(spec, index) for index in range(TEAM_COUNT)] + [stable_id(spec.run_id, "user:super")]
    shop_ids = [
        _shop_id(spec, team, shop)
        for team in range(TEAM_COUNT)
        for shop in range(SHOPS_PER_TEAM)
    ]
    candidate_ids = select(Candidate.candidate_id).where(Candidate.team_id.in_(team_ids))
    observation_ids = select(Observation.observation_id).where(Observation.candidate_id.in_(candidate_ids))
    run_ids = select(SelectionRun.run_id).where(SelectionRun.team_id.in_(team_ids))
    with engine.connect() as connection:
        foreign_items = connection.scalar(select(func.count()).select_from(ResultItem).where(
            ResultItem.observation_id.in_(observation_ids),
            ResultItem.execution_run_id.not_in(run_ids),
        )) or 0
        foreign_run_items = connection.scalar(select(func.count()).select_from(ResultItem).where(
            ResultItem.execution_run_id.in_(run_ids),
            ResultItem.observation_id.not_in(observation_ids),
        )) or 0
        foreign_reuse = connection.scalar(select(func.count()).select_from(SelectionRun).where(
            SelectionRun.reused_run_id.in_(run_ids),
            SelectionRun.run_id.not_in(run_ids),
        )) or 0
        foreign_observations = connection.scalar(select(func.count()).select_from(Observation).where(
            Observation.last_run_id.in_(run_ids),
            Observation.candidate_id.not_in(candidate_ids),
        )) or 0
    if any((foreign_items, foreign_run_items, foreign_reuse, foreign_observations)):
        raise CapacityToolError("cleanup refused: foreign rows reference this run namespace")
    chunk_size = 1_000
    removed: dict[str, int] = {
        "result_items": _delete_owned_chunks(
            engine,
            ResultItem,
            ResultItem.item_id,
            ResultItem.execution_run_id.in_(run_ids),
            chunk_size=chunk_size,
            statement_timeout_ms=statement_timeout_ms,
        ),
        "observations": _delete_owned_chunks(
            engine,
            Observation,
            Observation.observation_id,
            Observation.candidate_id.in_(candidate_ids),
            chunk_size=chunk_size,
            statement_timeout_ms=statement_timeout_ms,
        ),
        "runs": _delete_owned_chunks(
            engine,
            SelectionRun,
            SelectionRun.run_id,
            SelectionRun.team_id.in_(team_ids),
            chunk_size=chunk_size,
            statement_timeout_ms=statement_timeout_ms,
        ),
        "candidates": _delete_owned_chunks(
            engine,
            Candidate,
            Candidate.candidate_id,
            Candidate.team_id.in_(team_ids),
            chunk_size=chunk_size,
            statement_timeout_ms=statement_timeout_ms,
        ),
    }
    with engine.begin() as connection:
        _set_statement_timeout(connection, statement_timeout_ms)
        for name, statement in (
            ("strategies", delete(Strategy).where(Strategy.team_id.in_(team_ids))),
            ("shop_access", delete(TeamShopAccess).where(TeamShopAccess.team_id.in_(team_ids))),
            ("module_access", delete(TeamModuleAccess).where(TeamModuleAccess.team_id.in_(team_ids))),
            ("memberships", delete(TeamMembership).where(TeamMembership.team_id.in_(team_ids))),
            ("shops", delete(Shop).where(Shop.shop_id.in_(shop_ids))),
            ("teams", delete(Team).where(Team.team_id.in_(team_ids))),
            ("users", delete(User).where(User.user_id.in_(user_ids))),
        ):
            result = connection.execute(statement)
            removed[name] = max(result.rowcount or 0, 0)
    remaining = dataset_counts(engine, spec)
    if any(remaining.values()):
        raise CapacityToolError(f"cleanup left owned rows: {remaining}")
    return removed


def _bounded_int(minimum: int, maximum: int):
    def parse(value: str) -> int:
        parsed = int(value)
        if not minimum <= parsed <= maximum:
            raise argparse.ArgumentTypeError(f"must be between {minimum} and {maximum}")
        return parsed

    return parse


def _common_parser(parser: argparse.ArgumentParser, *, database: bool) -> None:
    parser.add_argument("--run-id", required=True, type=UUID)
    parser.add_argument("--tier", required=True, type=int, choices=TIERS)
    parser.add_argument("--as-of", required=True, type=date.fromisoformat)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    if database:
        parser.add_argument("--allow-capacity-test", action="store_true")
        parser.add_argument("--expected-database", required=True)
        parser.add_argument("--expected-endpoint", required=True)
        parser.add_argument("--expected-head", required=True)
        parser.add_argument("--statement-timeout-ms", type=_bounded_int(1_000, 30_000), default=8_000)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Guarded product-selection capacity tool")
    commands = root.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan", help="offline deterministic manifest only")
    _common_parser(plan, database=False)
    seed = commands.add_parser("seed", help="seed or extend one guarded synthetic namespace")
    _common_parser(seed, database=True)
    # Observation rows currently have 34 bound columns.  1,500 rows remain
    # below PostgreSQL's 65,535 bind-parameter limit with headroom.
    seed.add_argument("--chunk-size", type=_bounded_int(100, 1_500), default=1_000)
    measure = commands.add_parser("measure", help="measure real repository and ASGI API paths")
    _common_parser(measure, database=True)
    measure.add_argument("--api-target", required=True, choices=(API_TARGET,))
    measure.add_argument("--profile", choices=("smoke", "formal"), default="smoke")
    measure.add_argument("--samples", type=_bounded_int(1, 30), default=30)
    measure.add_argument("--readers", type=_bounded_int(0, 16), default=0)
    measure.add_argument("--duration-seconds", type=_bounded_int(5, 300), default=60)
    measure.add_argument("--with-writer", action="store_true")
    measure.add_argument("--writer-interval-seconds", type=float, default=1.0)
    measure.add_argument("--explain-case")
    cleanup = commands.add_parser("cleanup", help="delete only this deterministic run namespace")
    _common_parser(cleanup, database=True)
    return root


def validate_measure_arguments(args: argparse.Namespace) -> None:
    if args.with_writer and args.readers == 0:
        raise CapacityToolError("--with-writer requires concurrent readers")
    if not 0.5 <= args.writer_interval_seconds <= 10:
        raise CapacityToolError("writer interval must be between 0.5 and 10 seconds")
    if args.profile == "formal" and not (
        args.samples == 30
        and args.readers == 8
        and args.duration_seconds >= 60
        and args.with_writer
    ):
        raise CapacityToolError(
            "formal profile requires 30 samples, 8 readers, one writer, and at least 60 seconds",
        )


def _safe_error(error: Exception) -> str:
    value = str(error)
    value = re.sub(r"(?i)(password|token|cookie|secret)=([^\s&;]+)", r"\1=<redacted>", value)
    value = re.sub(
        r"(?i)(postgres(?:ql)?(?:\+[^:]+)?://[^:/\s]+:)[^@\s]+(@)",
        r"\1<redacted>\2",
        value,
    )
    value = re.sub(r"(?i)(authorization|cookie):\s*[^\r\n]+", r"\1: <redacted>", value)
    return value[:500]


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    spec = DatasetSpec(args.run_id, args.tier, args.as_of, args.seed)
    try:
        if args.command == "plan":
            ensure_namespace(spec)
            manifest = build_manifest(spec)
            write_json(manifest_path(spec), manifest)
            print(json.dumps({
                "state": "planned",
                "manifest": str(manifest_path(spec)),
                "counts": manifest["counts"],
            }, ensure_ascii=False))
            return 0
        if args.command == "seed":
            ensure_namespace(spec)
        else:
            require_namespace(spec)
        if args.command == "measure":
            validate_measure_arguments(args)
        engine = guarded_engine(args)
        exit_code = 0
        run_lock: tuple[Any, int] | None = None
        try:
            install_statement_timeout(engine, args.statement_timeout_ms)
            bind_target(spec, args, create=args.command == "seed")
            run_lock = acquire_database_run_lock(engine, spec)
            if args.command == "seed":
                result = seed_dataset(
                    engine,
                    spec,
                    chunk_size=args.chunk_size,
                    statement_timeout_ms=args.statement_timeout_ms,
                )
                print(json.dumps({"state": result["state"], "counts": result["verified_counts"]}, ensure_ascii=False))
            elif args.command == "measure":
                result = measure_dataset(
                    engine,
                    spec,
                    samples=args.samples,
                    readers=args.readers,
                    duration_seconds=args.duration_seconds,
                    with_writer=args.with_writer,
                    writer_interval_seconds=args.writer_interval_seconds,
                    explain_case=args.explain_case,
                    statement_timeout_ms=args.statement_timeout_ms,
                    profile=args.profile,
                )
                print(json.dumps({
                    "state": "measured",
                    "evidence_path": result["evidence_path"],
                    "case_count": len(result["cases"]),
                    "profile": result["profile"],
                    "concurrency": result["concurrency"],
                    "acceptance_passed": result["acceptance"]["passed"],
                }, ensure_ascii=False))
                if not result["acceptance"]["passed"]:
                    exit_code = 3
            elif args.command == "cleanup":
                removed = cleanup_dataset(engine, spec, statement_timeout_ms=args.statement_timeout_ms)
                for path in namespace_path(spec).parent.glob("manifest-*.json"):
                    manifest = json.loads(path.read_text(encoding="utf-8"))
                    manifest.update(
                        state="cleaned",
                        removed=removed,
                        cleaned_at=datetime.now(UTC).isoformat(),
                    )
                    write_json(path, manifest)
                print(json.dumps({"state": "cleaned", "removed": removed}, ensure_ascii=False))
            else:
                raise AssertionError(args.command)
        finally:
            if run_lock is not None:
                release_database_run_lock(*run_lock)
            engine.dispose()
        return exit_code
    except Exception as error:
        print(json.dumps({
            "state": "refused" if isinstance(error, CapacityToolError) else "failed",
            "error_type": type(error).__name__,
            "message": _safe_error(error),
        }, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
