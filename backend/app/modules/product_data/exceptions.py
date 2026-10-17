from app.core.exceptions import AppError


class ProductDataUnsupportedError(AppError):
    code = "PRODUCT_DATA_SCOPE_UNSUPPORTED"
    message = "当前商品数据仅支持抖店基准切片和近1/7/30天，不会替换为其他范围"
    status_code = 422


class ProductDataUnitUnconfirmedError(AppError):
    code = "PRODUCT_DATA_UNIT_UNCONFIRMED"
    message = "该指标显示单位尚未核定，暂不能按金额或百分比筛选排序"
    status_code = 422


class ProductDataCollectionUnavailableError(AppError):
    code = "PRODUCT_DATA_COLLECTION_UNAVAILABLE"
    message = "当前环境未启用商品数据手动采集"
    status_code = 503


class ProductDataCollectionBusyError(AppError):
    code = "PRODUCT_DATA_COLLECTION_BUSY"
    message = "该采集范围当前繁忙，请稍后再试"
    status_code = 409


class ProductDataIdempotencyConflictError(AppError):
    code = "PRODUCT_DATA_IDEMPOTENCY_CONFLICT"
    message = "此请求键已用于不同的商品数据请求或团队上下文"
    status_code = 409


class ProductDataGenerationNotFoundError(AppError):
    code = "PRODUCT_DATA_GENERATION_NOT_FOUND"
    message = "采集回执不存在或当前不可访问"
    status_code = 404


class ProductDataPublicationRejectedError(AppError):
    code = "PRODUCT_DATA_PUBLICATION_REJECTED"
    message = "采集代或租约已失效，已有成功数据保持不变"
    status_code = 409


class ProductDataSourceInvalidError(AppError):
    code = "PRODUCT_DATA_SOURCE_CONTRACT_INVALID"
    message = "商品数据来源契约不匹配，未发起请求"
    status_code = 409


class ProductDataQueryInvalidError(AppError):
    code = "PRODUCT_DATA_QUERY_INVALID"
    message = "商品数据查询参数无效，请检查日期、排序和筛选区间"
    status_code = 422


class ProductDataSessionValidationRequiredError(AppError):
    code = "PRODUCT_DATA_SESSION_VALIDATION_REQUIRED"
    message = "本次采集需要已验证且仍新鲜的店铺会话，请先使用现有会话验证入口"
    status_code = 409
