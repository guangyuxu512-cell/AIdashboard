"""Gateway attempt registration and durable complete-package acceptance."""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.product_collection.contracts import (
    ControlIngestV1,
    GatewayAttemptRegistrationV1,
    GatewayCredentialRefreshV1,
    UploadAcceptedV1,
    UploadReceiptV1,
    canonical_sha256,
)
from app.modules.product_collection.exceptions import (
    ProductCollectionAttemptNotFoundError,
    ProductCollectionBatchConflictError,
    ProductCollectionIngestCredentialError,
    ProductCollectionPayloadInvalidError,
    ProductCollectionStateConflictError,
    ProductCollectionUploadConflictError,
)
from app.modules.product_collection.models import (
    ProductCollectionCaptureAttempt as CaptureAttempt,
    ProductCollectionDispatch as Dispatch,
    ProductCollectionItem as Item,
    ProductCollectionRequest as CollectionRequest,
    ProductCollectionUploadReceipt as UploadReceipt,
)
from app.modules.product_collection.payload import parse_complete_package
from app.modules.product_collection.repository import ProductCollectionRepository
from app.modules.product_collection.security import (
    CredentialBinding,
    issue_credential,
    verify_credential_hash,
)
from app.shared.identifiers import generate_id


class ProductCollectionIngestService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = ProductCollectionRepository(session)

    def register_attempt(
        self,
        registration: GatewayAttemptRegistrationV1,
        *,
        secret: bytes,
        key_id: str,
        public_base_url: str,
        token_ttl_seconds: int,
        accept_grace_seconds: int,
    ) -> ControlIngestV1:
        if token_ttl_seconds < 1 or accept_grace_seconds < 0:
            raise ValueError("Ingest credential timing is invalid")
        try:
            dispatch = self.session.scalar(
                select(Dispatch)
                .where(Dispatch.dispatch_id == registration.dispatch_id)
                .with_for_update()
                .execution_options(populate_existing=True),
            )
            if dispatch is None:
                raise ProductCollectionAttemptNotFoundError()
            item = self.repository.lock_item(dispatch.item_id, dispatch.team_id)
            if item is None:
                raise ProductCollectionAttemptNotFoundError()
            self._validate_registration(dispatch, item, registration)

            existing = self.session.scalar(
                select(CaptureAttempt).where(
                    CaptureAttempt.gateway_id == registration.gateway_id,
                    CaptureAttempt.gateway_job_id == registration.gateway_job_id,
                    CaptureAttempt.capture_batch_id == registration.capture_batch_id,
                ),
            )
            now = self.repository.now()
            if registration.lease_expires_at <= now:
                raise ProductCollectionStateConflictError("采集批次租约已失效")
            if existing is not None:
                if (
                    existing.dispatch_id != dispatch.dispatch_id
                    or existing.gateway_device_id != registration.device_id
                    or existing.team_id != dispatch.team_id
                    or existing.state not in {"registered", "running", "received", "processing"}
                ):
                    raise ProductCollectionBatchConflictError()
                issued = self._reissue_existing(existing, item, secret)
                self.session.rollback()
                return _control_ingest(existing, issued.token, public_base_url)

            self._supersede_previous_attempt(dispatch=dispatch, at=now)
            item.attempt_count += 1
            binding = CredentialBinding(
                attempt_id=generate_id(),
                gateway_id=registration.gateway_id,
                device_id=registration.device_id,
                gateway_job_id=registration.gateway_job_id,
                capture_batch_id=registration.capture_batch_id,
                source_platform=registration.source_platform.value,
                source_product_id=registration.source_product_id,
            )
            issued = issue_credential(secret=secret, binding=binding, version=1)
            expires_at = min(
                registration.lease_expires_at,
                now + timedelta(seconds=token_ttl_seconds),
            )
            accept_until = registration.lease_expires_at + timedelta(
                seconds=accept_grace_seconds,
            )
            attempt = CaptureAttempt(
                attempt_id=binding.attempt_id,
                dispatch_id=dispatch.dispatch_id,
                gateway_id=registration.gateway_id,
                team_id=dispatch.team_id,
                gateway_device_id=registration.device_id,
                gateway_job_id=registration.gateway_job_id,
                capture_batch_id=registration.capture_batch_id,
                attempt_no=item.attempt_count,
                ingest_credential_id=issued.credential_id,
                ingest_credential_version=issued.version,
                ingest_token_key_id=key_id,
                ingest_token_salt=issued.salt_hex,
                ingest_token_hash=issued.token_sha256,
                token_issued_at=now,
                token_expires_at=expires_at,
                accept_until=accept_until,
                state="running",
                lease_expires_at=registration.lease_expires_at,
                last_heartbeat_at=now,
                registered_at=now,
            )
            self.session.add(attempt)
            dispatch.state = "running"
            dispatch.gateway_job_id = registration.gateway_job_id
            dispatch.lease_id = None
            dispatch.lease_expires_at = None
            dispatch.last_heartbeat_at = now
            item.state = "running"
            item.finished_at = None
            request = self.repository.lock_request(item.request_id, item.team_id)
            if request is None:
                raise ProductCollectionAttemptNotFoundError()
            request.status = "running"
            request.finished_at = None
            self.session.commit()
            return _control_ingest(attempt, issued.token, public_base_url)
        except Exception:
            self.session.rollback()
            raise

    def accept_complete_package(
        self,
        *,
        attempt_id: UUID,
        credential: str,
        raw_body: bytes,
    ) -> UploadAcceptedV1:
        try:
            package = parse_complete_package(raw_body)
        except (ValueError, ValidationError) as error:
            raise ProductCollectionPayloadInvalidError() from error
        normalized = package.model_dump(mode="json", by_alias=True)
        content_hash = canonical_sha256(normalized)
        try:
            attempt = self.session.scalar(
                select(CaptureAttempt)
                .where(CaptureAttempt.attempt_id == attempt_id)
                .with_for_update()
                .execution_options(populate_existing=True),
            )
            if attempt is None:
                raise ProductCollectionAttemptNotFoundError()
            now = self.repository.now()
            if (
                now >= attempt.token_expires_at
                or now > attempt.accept_until
                or not verify_credential_hash(credential, attempt.ingest_token_hash)
            ):
                raise ProductCollectionIngestCredentialError()

            existing = self.session.scalar(
                select(UploadReceipt).where(UploadReceipt.attempt_id == attempt.attempt_id),
            )
            if existing is not None:
                if existing.content_sha256 != content_hash:
                    raise ProductCollectionUploadConflictError()
                if attempt.state not in {"received", "processing"}:
                    raise ProductCollectionStateConflictError()
                self.session.rollback()
                return UploadAcceptedV1(
                    receipt=UploadReceiptV1(
                        status="duplicate",
                        receiptId=existing.upload_receipt_id,
                        attemptId=attempt.attempt_id,
                        captureBatchId=attempt.capture_batch_id,
                        receivedAt=existing.received_at,
                    ),
                )

            if attempt.state not in {"registered", "running"}:
                raise ProductCollectionStateConflictError()
            dispatch = self.repository.lock_dispatch(attempt.dispatch_id, attempt.team_id)
            if dispatch is None:
                raise ProductCollectionBatchConflictError()
            item = self.repository.lock_item(dispatch.item_id, attempt.team_id)
            if item is None or item.current_dispatch_id != dispatch.dispatch_id:
                raise ProductCollectionBatchConflictError()
            context = package.task_context
            if (
                context.job_id != attempt.gateway_job_id
                or context.capture_batch_id != attempt.capture_batch_id
                or context.source_platform.value != item.platform
                or context.source_product_id != item.source_product_id
            ):
                raise ProductCollectionBatchConflictError()
            active_attempt = self.session.scalar(
                select(CaptureAttempt.attempt_id).where(
                    CaptureAttempt.dispatch_id == dispatch.dispatch_id,
                    CaptureAttempt.state.in_(("registered", "running", "received", "processing")),
                ),
            )
            if active_attempt != attempt.attempt_id:
                raise ProductCollectionBatchConflictError()

            receipt = UploadReceipt(
                upload_receipt_id=generate_id(),
                team_id=attempt.team_id,
                attempt_id=attempt.attempt_id,
                upload_key=f"pci_upload_v1_{attempt.attempt_id.hex}",
                content_sha256=content_hash,
                raw_payload=normalized,
                raw_format_version=1,
                state="received",
                received_at=now,
            )
            self.session.add(receipt)
            attempt.token_consumed_at = now
            attempt.accepted_content_sha256 = content_hash
            attempt.state = "received"
            attempt.last_heartbeat_at = now
            dispatch.state = "running"
            dispatch.last_heartbeat_at = now
            item.state = "received"
            item.finished_at = None
            self.session.commit()
            return UploadAcceptedV1(
                receipt=UploadReceiptV1(
                    status="received",
                    receiptId=receipt.upload_receipt_id,
                    attemptId=attempt.attempt_id,
                    captureBatchId=attempt.capture_batch_id,
                    receivedAt=now,
                ),
            )
        except Exception:
            self.session.rollback()
            raise

    def refresh_credential(
        self,
        *,
        attempt_id: UUID,
        command: GatewayCredentialRefreshV1,
        secret: bytes,
        public_base_url: str,
        token_ttl_seconds: int,
    ) -> ControlIngestV1:
        try:
            attempt = self.session.scalar(
                select(CaptureAttempt)
                .where(CaptureAttempt.attempt_id == attempt_id)
                .with_for_update()
                .execution_options(populate_existing=True),
            )
            if attempt is None:
                raise ProductCollectionAttemptNotFoundError()
            now = self.repository.now()
            if (
                attempt.gateway_id != command.gateway_id
                or attempt.gateway_job_id != command.gateway_job_id
                or attempt.gateway_device_id != command.device_id
                or attempt.capture_batch_id != command.capture_batch_id
                or attempt.ingest_credential_id != command.credential_id
                or attempt.state not in {"registered", "running"}
                or attempt.token_consumed_at is not None
                or now >= attempt.accept_until
            ):
                raise ProductCollectionBatchConflictError()
            dispatch = self.repository.lock_dispatch(attempt.dispatch_id, attempt.team_id)
            item = (
                self.repository.lock_item(dispatch.item_id, attempt.team_id)
                if dispatch is not None
                else None
            )
            if (
                dispatch is None
                or item is None
                or item.current_dispatch_id != dispatch.dispatch_id
                or dispatch.state != "running"
                or item.state != "running"
            ):
                raise ProductCollectionBatchConflictError()
            binding = CredentialBinding(
                attempt_id=attempt.attempt_id,
                gateway_id=attempt.gateway_id,
                device_id=attempt.gateway_device_id,
                gateway_job_id=attempt.gateway_job_id,
                capture_batch_id=attempt.capture_batch_id,
                source_platform=item.platform,
                source_product_id=item.source_product_id,
            )
            issued = issue_credential(
                secret=secret,
                binding=binding,
                version=attempt.ingest_credential_version + 1,
            )
            attempt.ingest_credential_id = issued.credential_id
            attempt.ingest_credential_version = issued.version
            attempt.ingest_token_salt = issued.salt_hex
            attempt.ingest_token_hash = issued.token_sha256
            attempt.token_issued_at = now
            attempt.token_expires_at = min(
                attempt.accept_until,
                now + timedelta(seconds=token_ttl_seconds),
            )
            attempt.last_heartbeat_at = now
            self.session.commit()
            return _control_ingest(attempt, issued.token, public_base_url)
        except Exception:
            self.session.rollback()
            raise

    @staticmethod
    def _validate_registration(
        dispatch: Dispatch,
        item: Item,
        registration: GatewayAttemptRegistrationV1,
    ) -> None:
        if (
            dispatch.gateway_id != registration.gateway_id
            or dispatch.external_job_id != registration.external_job_id
            or dispatch.gateway_job_id != registration.gateway_job_id
            or dispatch.state not in {"dispatched", "running"}
            or item.current_dispatch_id != dispatch.dispatch_id
            or item.platform != registration.source_platform.value
            or item.source_product_id != registration.source_product_id
        ):
            raise ProductCollectionBatchConflictError()

    @staticmethod
    def _reissue_existing(
        attempt: CaptureAttempt,
        item: Item,
        secret: bytes,
    ):
        binding = CredentialBinding(
            attempt_id=attempt.attempt_id,
            gateway_id=attempt.gateway_id,
            device_id=attempt.gateway_device_id,
            gateway_job_id=attempt.gateway_job_id,
            capture_batch_id=attempt.capture_batch_id,
            source_platform=item.platform,
            source_product_id=item.source_product_id,
        )
        return issue_credential(
            secret=secret,
            binding=binding,
            version=attempt.ingest_credential_version,
            credential_id=attempt.ingest_credential_id,
            salt=bytes.fromhex(attempt.ingest_token_salt),
        )

    def _supersede_previous_attempt(self, *, dispatch: Dispatch, at) -> None:
        previous = self.session.scalar(
            select(CaptureAttempt)
            .where(
                CaptureAttempt.dispatch_id == dispatch.dispatch_id,
                CaptureAttempt.state.in_(("registered", "running", "received", "processing")),
            )
            .with_for_update(),
        )
        if previous is None:
            return
        previous.state = "superseded"
        previous.finished_at = at
        previous.last_error_code = "PRODUCT_COLLECTION_CAPTURE_SUPERSEDED"
        previous.last_error_stage = "attempt_registration"
        previous.last_error_message = "采集批次已被网关的新批次替代"
        upload = self.session.scalar(
            select(UploadReceipt)
            .where(UploadReceipt.attempt_id == previous.attempt_id)
            .with_for_update(),
        )
        if upload is not None and upload.state in {"received", "processing"}:
            upload.state = "superseded"
            upload.processed_at = at
            upload.lease_id = None
            upload.lease_expires_at = None
            upload.processing_next_attempt_at = None
            upload.last_error_code = previous.last_error_code
            upload.last_error_stage = previous.last_error_stage
            upload.last_error_message = previous.last_error_message
            upload.gateway_settlement_state = "pending"
            upload.next_attempt_at = None


def _control_ingest(
    attempt: CaptureAttempt,
    token: str,
    public_base_url: str,
) -> ControlIngestV1:
    return ControlIngestV1(
        protocol="central_ingest_v1",
        attemptId=attempt.attempt_id,
        uploadUrl=(
            f"{public_base_url}/api/v1/mobile-collection/ingest/{attempt.attempt_id}"
        ),
        credential=token,
        credentialId=attempt.ingest_credential_id,
        expiresAt=attempt.token_expires_at,
    )
