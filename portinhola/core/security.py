import base64
from datetime import UTC, datetime

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from itsdangerous import BadSignature, URLSafeTimedSerializer

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def _serializer(key: bytes) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(base64.urlsafe_b64encode(key), salt="portinhola-session")


def create_session_token(key: bytes) -> str:
    return _serializer(key).dumps("session")


def session_age(key: bytes, token: str) -> int | None:
    try:
        _, issued_at = _serializer(key).loads(token, return_timestamp=True)
    except BadSignature:
        return None
    return int((datetime.now(UTC) - issued_at).total_seconds())
