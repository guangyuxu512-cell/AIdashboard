from cryptography.fernet import Fernet, InvalidToken
from pydantic import SecretStr


class EncryptionConfigurationError(RuntimeError):
    pass


class EncryptedPayloadError(ValueError):
    pass


class SecretCipher:
    """Authenticated symmetric encryption for server-managed secrets."""

    def __init__(self, key: SecretStr | str) -> None:
        raw_key = key.get_secret_value() if isinstance(key, SecretStr) else key
        try:
            self._fernet = Fernet(raw_key.encode("ascii"))
        except (ValueError, UnicodeEncodeError) as error:
            raise EncryptionConfigurationError(
                "BACKEND_ENCRYPTION_KEY must be a valid Fernet key",
            ) from error

    def encrypt_text(self, value: str) -> bytes:
        return self.encrypt_bytes(value.encode("utf-8"))

    def decrypt_text(self, value: bytes) -> str:
        return self.decrypt_bytes(value).decode("utf-8")

    def encrypt_bytes(self, value: bytes) -> bytes:
        return self._fernet.encrypt(value)

    def decrypt_bytes(self, value: bytes) -> bytes:
        try:
            return self._fernet.decrypt(value)
        except InvalidToken as error:
            raise EncryptedPayloadError("Encrypted payload is invalid") from error
