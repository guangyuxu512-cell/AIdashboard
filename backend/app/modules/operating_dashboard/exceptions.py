from app.core.exceptions import AppError


class OperatingDashboardInvalidRequestError(AppError):
    code = "OPERATING_DASHBOARD_INVALID_REQUEST"
    message = "经营数据请求参数无效"
    status_code = 422


class OperatingDashboardShopNotAvailableError(AppError):
    code = "OPERATING_DASHBOARD_SHOP_NOT_AVAILABLE"
    message = "指定店铺不存在或当前不可访问"
    status_code = 404


class OperatingDashboardCollectionNotFoundError(AppError):
    code = "OPERATING_DASHBOARD_COLLECTION_NOT_FOUND"
    message = "经营数据更新任务不存在或当前不可访问"
    status_code = 404


class OperatingDashboardCollectionRetryUnavailableError(AppError):
    code = "OPERATING_DASHBOARD_COLLECTION_RETRY_UNAVAILABLE"
    message = "当前没有可重试的经营数据采集项"
    status_code = 409


class OperatingDashboardCollectionUnavailableError(AppError):
    """The API is deployed, but this environment may not execute platform I/O."""

    code = "OPERATING_DASHBOARD_COLLECTION_UNAVAILABLE"
    message = "当前环境未启用经营数据采集"
    status_code = 503
