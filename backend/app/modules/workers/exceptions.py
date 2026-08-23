from app.core.exceptions import AppError


class WorkerAuthenticationError(AppError):
    code = "WORKER_AUTHENTICATION_FAILED"
    message = "Worker 身份验证失败"
    status_code = 401


class WorkerCredentialNotFoundError(AppError):
    code = "WORKER_CREDENTIAL_NOT_FOUND"
    message = "设备尚未签发 Worker Token"
    status_code = 404


class WorkerCredentialStateConflictError(AppError):
    code = "WORKER_CREDENTIAL_STATE_CONFLICT"
    message = "Worker 凭证状态不允许执行当前操作"
    status_code = 409
