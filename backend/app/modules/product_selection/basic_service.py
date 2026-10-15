"""Single-product intentions and fenced writes through the existing Run queue."""

from datetime import UTC, datetime
from uuid import uuid4

from app.core.config import get_settings
from app.modules.product_selection.basic_contract import (
    BasicInfoStatus, BasicFieldState, SelectionBasicRequest,
)
from app.modules.product_selection.candidate_context import existing_source_context
from app.modules.product_selection.exceptions import (
    SelectionExecutionDisabledError, SelectionRunConflictError,
    SelectionRunLeaseLostError, SelectionRunNotFoundError,
)
from app.modules.product_selection.models import ProductSelectionRun as Run
from app.modules.product_selection.run_contract import SelectionRunReceipt
from app.modules.product_selection.run_repository import SelectionRunRepository
from app.modules.product_selection.run_service import SelectionRunService, safe_run_error
from app.modules.product_selection.service import ProductSelectionFactService
from app.platforms.douyin.product_selection import CompassSelectionIdentityError


def basic_values_and_status(row, *, basic, error, started_at, at):
    """Missing/invalid/failure retain facts; status is latest attempt, not value age."""
    previous = BasicInfoStatus.model_validate(row.basic_info_status) if row.basic_info_status else None
    values, fields = {}, {}
    for name in ("category_path", "first_on_shelf_date", "bad_comment_rate"):
        field = getattr(basic, name) if basic is not None else None
        state = field.state if field is not None else "unknown"
        # Legacy whole-response time cannot prove each field's latest value age
        # after earlier partial updates. Preserve the scalar, do not invent per-field time.
        success = getattr(previous, name).last_success_at if previous else None
        if state == "available":
            if field.value is None:
                raise ValueError("Available basic fact requires a value")
            success = at
            if name == "category_path":
                values[name] = list(field.value)
            elif name == "bad_comment_rate":
                values.update(bad_comment_rate_raw=field.value.value, bad_comment_rate_unit=field.value.unit)
            else:
                values[name] = field.value
        fields[name] = BasicFieldState(last_attempt_state=state, last_success_at=success)
    partial = any(field.last_attempt_state != "available" for field in fields.values())
    code, stage, business = safe_run_error(error) if error is not None else (
        ("PRODUCT_SELECTION_BASIC_INFO_PARTIAL", "basic_info_parse", None) if partial else (None, None, None))
    status = BasicInfoStatus(attempted_at=at, request_started_at=started_at,
        state="failed" if error is not None else "partial" if partial else "succeeded",
        error_code=code, error_stage=stage, platform_business_code=business, **fields)
    return values, partial, status


class SelectionBasicService:
    def __init__(self, session, *, settings=None):
        self.session = session
        self.settings = settings or get_settings()
        self.facts = ProductSelectionFactService(session)
        self.runs = SelectionRunRepository(session)

    def submit(self, actor, command, *, now=None):
        at = now or datetime.now(UTC)
        try:
            current, source, identity = existing_source_context(self.facts, actor, command.observation_id, execution=True)
            if not self.settings.product_selection_execution_enabled:
                raise SelectionExecutionDisabledError()
            request = SelectionBasicRequest(observation_id=source.observation_id,
                candidate_id=identity.candidate_id, product_id=identity.platform_product_id,
                shop_id=source.request_shop_id, source_scope_hash=source.source_scope_hash)
            self.runs.lock_execution_decision(wait=True)
            current, source, identity = existing_source_context(self.facts, current, command.observation_id, execution=True)
            self.runs.recover_expired(at)
            row = self.runs.find_submission(team_id=current.require_team_id(), user_id=current.user_id, key=command.submission_key)
            if row is not None:
                if row.operation_kind != "basic_info" or self.runs.validated_request(row).fingerprint() != request.fingerprint():
                    raise SelectionRunConflictError()
            else:
                active = self.runs.find_active(team_id=current.require_team_id(), shop_id=source.request_shop_id, fingerprint=request.fingerprint())
                row = Run(run_id=uuid4(), team_id=current.require_team_id(), created_by_user_id=current.user_id,
                    request_shop_id=source.request_shop_id, submission_key=command.submission_key,
                    operation_kind="basic_info", target_observation_id=source.observation_id,
                    request_fingerprint=request.fingerprint(), request_conditions=request.model_dump(mode="json"),
                    reused_run_id=active.run_id if active else None, status="reused" if active else "pending",
                    stage="queued", result_count=None, saved_count=0, supplemented_count=0, supplement_failed_count=0,
                    created_at=at, updated_at=at)
                self.session.add(row)
                self.session.flush()
            receipt = SelectionRunReceipt(receipt_id=row.run_id, submission_key=row.submission_key,
                execution_run_id=row.reused_run_id or row.run_id, reused=row.reused_run_id is not None,
                execution=SelectionRunService(self.session)._read(current, row))
            self.session.commit()
            return receipt
        except Exception:
            self.session.rollback()
            raise

    def get(self, actor, run_id):
        read = SelectionRunService(self.session).get(actor, run_id)
        if read.operation_kind != "basic_info":
            raise SelectionRunNotFoundError()
        return read

    def latest(self, actor, observation_id):
        current, _, _ = existing_source_context(self.facts, actor, observation_id)
        row = self.runs.latest_basic_for_actor(current, observation_id)
        return SelectionRunService(self.session)._read(current, row) if row else None

    def persist(self, actor, claim, *, basic=None, error=None, at=None):
        at = at or datetime.now(UTC)
        request = claim.request
        if not isinstance(request, SelectionBasicRequest) or request.execution is None:
            raise SelectionRunLeaseLostError()
        try:
            run = self.runs.fence(claim, at)
            current, source, identity = existing_source_context(self.facts, actor, request.observation_id, execution=True, lock=True)
            if (current.require_team_id() != claim.team_id or current.user_id != claim.user_id
                or source.request_shop_id != claim.shop_id or identity.candidate_id != request.candidate_id
                or identity.platform_product_id != request.product_id or source.source_scope_hash != request.source_scope_hash
                or source.last_successful_request_started_at != request.execution.rank_started_at
                or source.basic_info_version != request.execution.basic_version):
                raise SelectionRunLeaseLostError()
            if run.result_count is not None or run.supplemented_count or run.supplement_failed_count:
                self.session.rollback()
                return False
            if basic is not None and basic.product_id != request.product_id:
                raise CompassSelectionIdentityError()
            values, partial, status = basic_values_and_status(source, basic=basic, error=error,
                started_at=claim.started_at, at=at)
            for key, value in values.items():
                setattr(source, key, value)
            source.basic_info_status = status.model_dump(mode="json")
            source.last_attempt_at = source.updated_at = at
            source.last_error_code, source.last_error_stage = status.error_code, status.error_stage
            if not partial and error is None:
                source.basic_info_retrieved_at = at
            run.result_count = 1 if basic is not None else None
            run.supplemented_count = 0 if partial else 1
            run.supplement_failed_count = 1 if partial else 0
            run.error_code, run.error_stage, run.platform_business_code = status.error_code, status.error_stage, status.platform_business_code
            run.updated_at = at
            self.session.commit()
            return True
        except Exception:
            self.session.rollback()
            raise
