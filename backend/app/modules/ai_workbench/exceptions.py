from app.core.exceptions import AppError
from app.modules.ai_workbench.provider import (
    PROVIDER_CREATE_OUTCOME_UNKNOWN_CODE,
    PROVIDER_CREATE_OUTCOME_UNKNOWN_MESSAGE,
)


class TemplateGroupNotFoundError(AppError):
    code = "TEMPLATE_GROUP_NOT_FOUND"
    message = "模板组不存在"
    status_code = 404


class PromptTemplateNotFoundError(AppError):
    code = "PROMPT_TEMPLATE_NOT_FOUND"
    message = "提示词模板不存在"
    status_code = 404


class ProductMaterialGroupNotFoundError(AppError):
    code = "PRODUCT_MATERIAL_GROUP_NOT_FOUND"
    message = "商品素材组不存在"
    status_code = 404


class TemplateGroupInUseError(AppError):
    code = "TEMPLATE_GROUP_IN_USE"
    message = "模板组仍被商品素材组引用，无法删除"
    status_code = 409


class TemplateSequenceInvalidError(AppError):
    code = "TEMPLATE_SEQUENCE_INVALID"
    message = "模板顺序无效"
    status_code = 422


class TemplateBindingInvalidError(AppError):
    code = "TEMPLATE_BINDING_INVALID"
    message = "模板组绑定关系无效"
    status_code = 422


class MaterialAssetRoleInvalidError(AppError):
    code = "MATERIAL_ASSET_ROLE_INVALID"
    message = "素材角色不允许执行当前变更"
    status_code = 409


class GenerationJobNotFoundError(AppError):
    code = "GENERATION_JOB_NOT_FOUND"
    message = "生成任务不存在"
    status_code = 404


class GenerationItemNotFoundError(AppError):
    code = "GENERATION_ITEM_NOT_FOUND"
    message = "生成项不存在"
    status_code = 404


class GenerationSubmissionConflictError(AppError):
    code = "GENERATION_SUBMISSION_CONFLICT"
    message = "提交键已用于其他生成请求"
    status_code = 409


class GenerationPlanInvalidError(AppError):
    code = "GENERATION_PLAN_INVALID"
    message = "当前配置没有可执行的生成项"
    status_code = 422


class GenerationPlanTooLargeError(AppError):
    code = "GENERATION_PLAN_TOO_LARGE"
    message = "当前生成计划超过单次提交上限"
    status_code = 422


class GenerationRetryConflictError(AppError):
    code = "GENERATION_RETRY_CONFLICT"
    message = "生成项当前状态或尝试次数不允许重试"
    status_code = 409


class GenerationItemStateConflictError(AppError):
    code = "GENERATION_ITEM_STATE_CONFLICT"
    message = "生成项当前状态不允许该操作"
    status_code = 409


class ProviderCreateOutcomeUnknownError(AppError):
    code = PROVIDER_CREATE_OUTCOME_UNKNOWN_CODE
    message = PROVIDER_CREATE_OUTCOME_UNKNOWN_MESSAGE
    status_code = 409


class ProductMaterialGroupHasActiveGenerationJobsError(AppError):
    code = "PRODUCT_MATERIAL_GROUP_HAS_ACTIVE_GENERATION_JOBS"
    message = "商品素材组存在待执行或执行中的生成任务，无法删除"
    status_code = 409
