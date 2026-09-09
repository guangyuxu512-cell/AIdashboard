from app.core.exceptions import AppError


class AssetNotFoundError(AppError):
    code = "ASSET_NOT_FOUND"
    message = "资产不存在"
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
    message = "资产正在被业务记录引用，无法删除"
    status_code = 409


class AssetStorageError(AppError):
    code = "ASSET_STORAGE_FAILED"
    message = "资产文件存储失败"
    status_code = 500


class AssetStorageUnavailableError(AssetStorageError):
    code = "ASSET_STORAGE_UNAVAILABLE"
    message = "资产存储挂载不可用"
    status_code = 503


class AssetThumbnailUnavailableError(AppError):
    code = "ASSET_THUMBNAIL_UNAVAILABLE"
    message = "图片缩略图暂不可用"
    status_code = 503
