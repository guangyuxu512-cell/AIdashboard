class DouyinSignerError(RuntimeError):
    def __init__(self, safe_message: str, *, retryable: bool) -> None:
        super().__init__(safe_message)
        self.safe_message = safe_message
        self.retryable = retryable


class DouyinSignerConfigurationError(DouyinSignerError):
    def __init__(self) -> None:
        super().__init__("Douyin Signer尚未配置", retryable=False)


class DouyinSignerAuthenticationError(DouyinSignerError):
    def __init__(self) -> None:
        super().__init__("Douyin Signer认证失败", retryable=False)


class DouyinSignerUnavailableError(DouyinSignerError):
    def __init__(self) -> None:
        super().__init__("Douyin Signer暂时不可用", retryable=True)


class DouyinSignerResponseError(DouyinSignerError):
    def __init__(self) -> None:
        super().__init__("Douyin Signer返回无效响应", retryable=False)
