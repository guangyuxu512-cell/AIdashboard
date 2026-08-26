from app.core.exceptions import AppError


class AssetNotFoundError(AppError):
    code = "ASSET_NOT_FOUND"
    message = "图片不存在"
    status_code = 404


class AssetTypeUnsupportedError(AppError):
    code = "ASSET_TYPE_UNSUPPORTED"
    message = "仅支持 JPG、PNG 和 WebP 图片"
    status_code = 422


class AssetTooLargeError(AppError):
    code = "ASSET_TOO_LARGE"
    message = "图片超过单文件大小限制"
    status_code = 413


class AssetInUseError(AppError):
    code = "ASSET_IN_USE"
    message = "图片已被任务引用，无法删除"
    status_code = 409


class AssetStorageError(AppError):
    code = "ASSET_STORAGE_FAILED"
    message = "图片文件存储失败"
    status_code = 500
