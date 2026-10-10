from app.core.exceptions import AppError


class SelectionShopUnavailableError(AppError):
    code = "PRODUCT_SELECTION_SHOP_UNAVAILABLE"
    message = "请求店铺已停用、已移除或平台尚不支持选品"
    status_code = 409


class SelectionObservationNotFoundError(AppError):
    code = "PRODUCT_SELECTION_OBSERVATION_NOT_FOUND"
    message = "候选来源不存在或不可访问"
    status_code = 404
