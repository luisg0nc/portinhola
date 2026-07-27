import base64

from cryptography.fernet import Fernet


def _fernet(app_key: bytes) -> Fernet:
    return Fernet(base64.urlsafe_b64encode(app_key))


def encrypt(app_key: bytes, data: bytes) -> bytes:
    return _fernet(app_key).encrypt(data)


def decrypt(app_key: bytes, token: bytes) -> bytes:
    return _fernet(app_key).decrypt(token)
