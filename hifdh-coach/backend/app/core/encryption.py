"""
Field-level encryption for sensitive data (student PII, audio metadata).
Uses Fernet symmetric encryption (AES-128-CBC under the hood).
"""

import base64
import hashlib

from cryptography.fernet import Fernet

from app.core.config import get_settings

settings = get_settings()


def _derive_key(secret: str) -> bytes:
    """Derive a 32-byte Fernet-compatible key from the config secret."""
    digest = hashlib.sha256(secret.encode()).digest()
    return base64.urlsafe_b64encode(digest)


_fernet = Fernet(_derive_key(settings.field_encryption_key))


def encrypt_field(value: str) -> str:
    """Encrypt a string value. Returns base64-encoded ciphertext."""
    return _fernet.encrypt(value.encode()).decode()


def decrypt_field(token: str) -> str:
    """Decrypt a previously encrypted value."""
    return _fernet.decrypt(token.encode()).decode()


class EncryptedString:
    """
    SQLAlchemy TypeDecorator-compatible helper.
    Use with `mapped_column(EncryptedType)` for transparent encrypt/decrypt.
    """

    @staticmethod
    def process_bind_param(value: str | None) -> str | None:
        if value is None:
            return None
        return encrypt_field(value)

    @staticmethod
    def process_result_value(value: str | None) -> str | None:
        if value is None:
            return None
        return decrypt_field(value)
