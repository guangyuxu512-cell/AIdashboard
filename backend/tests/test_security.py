from cryptography.fernet import Fernet
from pydantic import SecretStr

from app.core.security import SecretCipher, mask_login_identifier


def test_secret_cipher_uses_authenticated_encryption() -> None:
    cipher = SecretCipher(SecretStr(Fernet.generate_key().decode("ascii")))
    plaintext = "stage-3a-password"

    encrypted = cipher.encrypt_text(plaintext)

    assert plaintext.encode() not in encrypted
    assert cipher.decrypt_text(encrypted) == plaintext


def test_login_identifier_masking() -> None:
    assert mask_login_identifier("13812348888") == "138****8888"
    assert mask_login_identifier("abcdef@example.com") == "abc***@example.com"
    assert mask_login_identifier("platform-user") == "pl***er"
