from app.core.exceptions import AppError


class ProductCollectionRequestNotFoundError(AppError):
    code = "PRODUCT_COLLECTION_REQUEST_NOT_FOUND"
    message = "采集请求不存在或当前不可访问"
    status_code = 404


class ProductCollectionItemNotFoundError(AppError):
    code = "PRODUCT_COLLECTION_ITEM_NOT_FOUND"
    message = "采集项目不存在或当前不可访问"
    status_code = 404


class ProductCollectionGroupNotFoundError(AppError):
    code = "PRODUCT_LIBRARY_GROUP_NOT_FOUND"
    message = "商品分组不存在或当前不可访问"
    status_code = 404


class ProductCollectionCandidateNotFoundError(AppError):
    code = "PRODUCT_COLLECTION_CANDIDATE_NOT_FOUND"
    message = "候选商品不存在或当前不可访问"
    status_code = 404


class ProductCollectionSubmissionConflictError(AppError):
    code = "PRODUCT_COLLECTION_SUBMISSION_CONFLICT"
    message = "同一提交标识不能用于不同的采集请求"
    status_code = 409


class ProductCollectionTargetUnsupportedError(AppError):
    code = "PRODUCT_COLLECTION_TARGET_UNSUPPORTED"
    message = "商品标识或链接尚不在当前支持范围"
    status_code = 422


class ProductCollectionPlatformUnsupportedError(AppError):
    code = "PRODUCT_COLLECTION_PLATFORM_UNSUPPORTED"
    message = "当前平台尚不支持该采集方式"
    status_code = 422


class ProductCollectionStateConflictError(AppError):
    code = "PRODUCT_COLLECTION_STATE_CONFLICT"
    message = "采集状态已变化，请刷新后重试"
    status_code = 409


class ProductCollectionGatewayUnavailableError(AppError):
    code = "PRODUCT_COLLECTION_GATEWAY_UNAVAILABLE"
    message = "手机采集网关暂不可用，任务已安全保留"
    status_code = 503


class ProductCollectionAttemptNotFoundError(AppError):
    code = "PRODUCT_COLLECTION_ATTEMPT_NOT_FOUND"
    message = "采集批次不存在或已失效"
    status_code = 404


class ProductCollectionIngestCredentialError(AppError):
    code = "PRODUCT_COLLECTION_INGEST_CREDENTIAL_INVALID"
    message = "采集包凭据无效或已失效"
    status_code = 401


class ProductCollectionBatchConflictError(AppError):
    code = "PRODUCT_COLLECTION_BATCH_CONFLICT"
    message = "采集包与当前任务批次不匹配"
    status_code = 409


class ProductCollectionUploadConflictError(AppError):
    code = "PRODUCT_COLLECTION_UPLOAD_CONFLICT"
    message = "同一采集凭据不能提交不同内容"
    status_code = 409


class ProductCollectionLeaseLostError(AppError):
    code = "PRODUCT_COLLECTION_LEASE_LOST"
    message = "处理租约已失效，迟到结果不会覆盖当前数据"
    status_code = 409


class ProductLibraryProductNotFoundError(AppError):
    code = "PRODUCT_LIBRARY_PRODUCT_NOT_FOUND"
    message = "商品不存在或当前不可访问"
    status_code = 404


class ProductLibraryFilterConflictError(AppError):
    code = "PRODUCT_LIBRARY_FILTER_CONFLICT"
    message = "商品分组与未分组筛选不能同时使用"
    status_code = 422


class ProductCollectionServiceAuthenticationError(AppError):
    code = "PRODUCT_COLLECTION_SERVICE_AUTHENTICATION_FAILED"
    message = "商品采集服务认证失败"
    status_code = 401


class ProductCollectionConfigurationError(AppError):
    code = "PRODUCT_COLLECTION_CONFIGURATION_UNAVAILABLE"
    message = "商品采集服务尚未配置完成"
    status_code = 503


class ProductCollectionPayloadInvalidError(AppError):
    code = "PRODUCT_COLLECTION_PAYLOAD_INVALID"
    message = "商品完整包格式无效"
    status_code = 422


class ProductCollectionPayloadTooLargeError(AppError):
    code = "PRODUCT_COLLECTION_PAYLOAD_TOO_LARGE"
    message = "商品完整包超过大小限制"
    status_code = 413
