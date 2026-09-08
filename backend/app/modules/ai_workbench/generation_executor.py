from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import ExitStack
import logging
from typing import ContextManager

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_session_factory
from app.integrations.image_generation import ToApisImageProvider
from app.modules.ai_workbench.exceptions import (
    GenerationItemStateConflictError,
    ProviderCreateOutcomeUnknownError,
)
from app.modules.ai_workbench.generation_service import (
    GenerationExecution,
    GenerationService,
)
from app.modules.ai_workbench.provider import (
    GeneratedProviderImage,
    GenerationProviderInput,
    GenerationProviderRequest,
    ImageGenerationProvider,
    ImageProviderFailure,
)
from app.modules.assets.exceptions import AssetStorageError
from app.modules.assets.service import AssetService
from app.modules.assets.storage import AssetStorage, create_asset_storage


logger = logging.getLogger(__name__)
SessionFactory = Callable[[], ContextManager[Session]]
ServiceFactory = Callable[[Session], GenerationService]


class GenerationExecutor:
    def __init__(
        self,
        *,
        session_factory: SessionFactory,
        service_factory: ServiceFactory,
        provider: ImageGenerationProvider,
        storage: AssetStorage,
    ) -> None:
        self._session_factory = session_factory
        self._service_factory = service_factory
        self._provider = provider
        self._storage = storage

    def execute_next(self) -> bool:
        execution = self._prepare_next()
        if execution is None:
            return False

        if execution.provider_code != self._provider.provider_code:
            self._fail_if_current(
                execution,
                failure_code="GENERATION_PROVIDER_UNSUPPORTED",
                failure_message="当前生成模型暂不支持执行",
            )
            return True

        provider_create_unpersisted = False
        try:
            external_task_id = execution.external_task_id
            if external_task_id is None:
                if not execution.provider_task_create_required:
                    self._fail_if_current(
                        execution,
                        failure_code=ProviderCreateOutcomeUnknownError.code,
                        failure_message=ProviderCreateOutcomeUnknownError.message,
                    )
                    return True
                external_task_id = self._create_provider_task(execution)
                provider_create_unpersisted = True
                self._record_provider_task(execution, external_task_id)
                provider_create_unpersisted = False
            image = self._provider.wait_for_image(external_task_id)
            try:
                self._complete(execution, image)
            finally:
                image.stream.close()
        except GenerationItemStateConflictError:
            logger.info(
                "Ignored stale AI generation provider result",
                extra={
                    "generation_item_id": str(execution.generation_item_id),
                    "attempt_count": execution.attempt_count,
                },
            )
        except ImageProviderFailure as error:
            self._fail_if_current(
                execution,
                failure_code=error.failure_code,
                failure_message=error.safe_message,
            )
        except AssetStorageError:
            self._fail_if_current(
                execution,
                failure_code="INPUT_ASSET_UNAVAILABLE",
                failure_message="生成输入图片不可用",
            )
        except Exception:
            logger.error(
                "AI generation item execution failed",
                extra={
                    "generation_item_id": str(execution.generation_item_id),
                    "attempt_count": execution.attempt_count,
                },
            )
            self._fail_if_current(
                execution,
                failure_code=(
                    ProviderCreateOutcomeUnknownError.code
                    if provider_create_unpersisted
                    else "GENERATION_EXECUTION_FAILED"
                ),
                failure_message=(
                    ProviderCreateOutcomeUnknownError.message
                    if provider_create_unpersisted
                    else "图片生成执行失败"
                ),
            )
        return True

    def _prepare_next(self) -> GenerationExecution | None:
        with self._session_factory() as session:
            return self._service_factory(session).prepare_next_provider_execution()

    def _create_provider_task(self, execution: GenerationExecution) -> str:
        with ExitStack() as stack:
            inputs = tuple(
                GenerationProviderInput(
                    asset_id=input_asset.asset_id,
                    original_filename=input_asset.original_filename,
                    content_type=input_asset.content_type,
                    stream=stack.enter_context(
                        self._storage.open(input_asset.storage_key),
                    ),
                )
                for input_asset in execution.input_assets
            )
            return self._provider.create_task(
                GenerationProviderRequest(
                    generation_item_id=execution.generation_item_id,
                    model_code=execution.model_code,
                    mode=execution.mode,
                    final_prompt=execution.final_prompt,
                    output_role=execution.output_role,
                    output_format=execution.output_format,
                    size=execution.size,
                    input_images=inputs,
                ),
            )

    def _record_provider_task(
        self,
        execution: GenerationExecution,
        external_task_id: str,
    ) -> None:
        with self._session_factory() as session:
            self._service_factory(session).record_provider_execution(
                execution.generation_item_id,
                expected_attempt_count=execution.attempt_count,
                provider_code=execution.provider_code,
                external_task_id=external_task_id,
            )

    def _complete(
        self,
        execution: GenerationExecution,
        image: GeneratedProviderImage,
    ) -> None:
        with self._session_factory() as session:
            self._service_factory(session).complete_item(
                execution.generation_item_id,
                original_filename=image.original_filename,
                content_type=image.content_type,
                stream=image.stream,
                expected_attempt_count=execution.attempt_count,
            )

    def _fail_if_current(
        self,
        execution: GenerationExecution,
        *,
        failure_code: str,
        failure_message: str,
    ) -> None:
        try:
            with self._session_factory() as session:
                self._service_factory(session).fail_item(
                    execution.generation_item_id,
                    failure_code=failure_code,
                    failure_message=failure_message,
                    expected_attempt_count=execution.attempt_count,
                )
        except GenerationItemStateConflictError:
            logger.info(
                "Ignored stale AI generation provider failure",
                extra={
                    "generation_item_id": str(execution.generation_item_id),
                    "attempt_count": execution.attempt_count,
                },
            )


def build_generation_executor(settings: Settings | None = None) -> GenerationExecutor:
    resolved_settings = settings or get_settings()
    if resolved_settings.toapis_api_key is None:
        raise RuntimeError("BACKEND_TOAPIS_API_KEY is required for AI generation")
    storage = create_asset_storage(resolved_settings)

    def service_factory(session: Session) -> GenerationService:
        return GenerationService(
            session,
            asset_service=AssetService(
                session,
                storage=storage,
                settings=resolved_settings,
            ),
        )

    return GenerationExecutor(
        session_factory=get_session_factory(),
        service_factory=service_factory,
        provider=ToApisImageProvider(
            api_key=resolved_settings.toapis_api_key,
            base_url=resolved_settings.toapis_base_url,
            resolution=resolved_settings.toapis_resolution,
            quality=resolved_settings.toapis_quality,
            poll_interval_seconds=resolved_settings.toapis_poll_interval_seconds,
            poll_timeout_seconds=resolved_settings.toapis_poll_timeout_seconds,
            request_timeout_seconds=resolved_settings.toapis_request_timeout_seconds,
            max_output_bytes=resolved_settings.asset_max_upload_bytes,
        ),
        storage=storage,
    )


async def execute_generation_items_forever() -> None:
    settings = get_settings()
    executor = build_generation_executor(settings)
    while True:
        try:
            processed = await asyncio.to_thread(executor.execute_next)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.error("AI generation execution scan failed")
            processed = False
        if not processed:
            await asyncio.sleep(settings.ai_generation_scan_interval_seconds)
