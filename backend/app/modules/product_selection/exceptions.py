from app.core.exceptions import AppError


class SelectionShopUnavailableError(AppError):
    code = "PRODUCT_SELECTION_SHOP_UNAVAILABLE"
    message = "请求店铺已停用、已移除或平台尚不支持选品"
    status_code = 409


class SelectionObservationNotFoundError(AppError):
    code = "PRODUCT_SELECTION_OBSERVATION_NOT_FOUND"
    message = "候选来源不存在或不可访问"
    status_code = 404


class SelectionRunNotFoundError(AppError):
    code = "PRODUCT_SELECTION_RUN_NOT_FOUND"
    message = "运行记录不存在或不可访问"
    status_code = 404


class SelectionRunConflictError(AppError):
    code = "PRODUCT_SELECTION_SUBMISSION_CONFLICT"
    message = "同一提交标识不能用于不同请求条件"
    status_code = 409


class SelectionSubmissionBusyError(AppError):
    code = "PRODUCT_SELECTION_SUBMISSION_BUSY"
    message = "提交正在处理，请用同一提交标识重试"
    status_code = 409


class SelectionRunLeaseLostError(AppError):
    code = "PRODUCT_SELECTION_RUN_LEASE_LOST"
    message = "执行已中断，旧执行结果不再写入"
    status_code = 409


class SelectionRequestUnconfirmedError(AppError):
    code = "PRODUCT_SELECTION_REQUEST_MAPPING_UNCONFIRMED"
    message = "当前渠道、周期和类目参数映射尚未确认，暂不可执行"
    status_code = 409


class SelectionPriceRangeInvalidError(AppError):
    code = "PRODUCT_SELECTION_PRICE_RANGE_INVALID"
    message = "请填写有效的最低和最高价格（元），最低价格不能大于最高价格"
    status_code = 422


class SelectionExecutionDisabledError(AppError):
    code = "PRODUCT_SELECTION_EXECUTION_DISABLED"
    message = "当前环境未启用手动选品执行"
    status_code = 409


class SelectionStrategyNotFoundError(AppError):
    code = "PRODUCT_SELECTION_STRATEGY_NOT_FOUND"
    message = "选品策略不存在或不可访问"
    status_code = 404


class SelectionStrategyVersionConflictError(AppError):
    code = "PRODUCT_SELECTION_STRATEGY_VERSION_CONFLICT"
    message = "策略已被修改，请刷新已保存内容；当前草稿未覆盖"
    status_code = 409


class SelectionStrategyWriteDisabledError(AppError):
    code = "PRODUCT_SELECTION_STRATEGY_WRITE_DISABLED"
    message = "当前策略为只读，保存及启停暂不可用"
    status_code = 409
