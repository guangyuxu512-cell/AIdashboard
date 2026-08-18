from functools import lru_cache

from app.core.config import get_settings
from app.core.security.encryption import (
    EncryptedPayloadError,
    EncryptionConfigurationError,
    SecretCipher,
)
from app.core.security.masking import mask_login_identifier
from app.core.security.redaction import REDACTED_VALUE, redact_validation_errors


@lru_cache
def get_secret_cipher() -> SecretCipher:
    encryption_key = get_settings().encryption_key
    if encryption_key is None:
        raise EncryptionConfigurationError(
            "BACKEND_ENCRYPTION_KEY must be configured before sensitive data access",
        )
    return SecretCipher(encryption_key)


__all__ = [
    "EncryptedPayloadError",
    "EncryptionConfigurationError",
    "REDACTED_VALUE",
    "SecretCipher",
    "get_secret_cipher",
    "mask_login_identifier",
    "redact_validation_errors",
]
