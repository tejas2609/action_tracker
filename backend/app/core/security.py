"""Password hashing and optional authenticated encryption of raw content."""

import base64, hashlib, hmac, json, secrets
from cryptography.fernet import Fernet, MultiFernet
from sqlalchemy.types import TypeDecorator, Text, JSON
from app.core.config import settings


def hash_password(password):
    if not 12 <= len(password) <= 200:
        raise ValueError("Password must contain 12–200 characters")
    salt = secrets.token_bytes(16)
    value = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return (
        "scrypt$"
        + base64.b64encode(salt).decode()
        + "$"
        + base64.b64encode(value).decode()
    )


def verify_password(password, encoded):
    try:
        scheme, salt, expected = encoded.split("$")
        if scheme != "scrypt":
            return False
        actual = hashlib.scrypt(
            password.encode(), salt=base64.b64decode(salt), n=16384, r=8, p=1
        )
        return hmac.compare_digest(actual, base64.b64decode(expected))
    except (ValueError, TypeError):
        return False


def data_cipher():
    keys = [
        key.strip() for key in settings.data_encryption_keys.split(",") if key.strip()
    ]
    return MultiFernet([Fernet(key.encode()) for key in keys]) if keys else None


class EncryptedText(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        cipher = data_cipher()
        if not cipher and value is not None and value.startswith("enc:v1:"):
            raise ValueError(
                "Reserved encryption prefix; configure encryption before storing this content"
            )
        return (
            "enc:v1:" + cipher.encrypt(value.encode()).decode()
            if cipher and value is not None
            else value
        )

    def process_result_value(self, value, dialect):
        if value is not None and value.startswith("enc:v1:"):
            cipher = data_cipher()
            if cipher is None:
                raise RuntimeError("Encryption key is required")
            return cipher.decrypt(value[7:].encode()).decode()
        return value


class EncryptedJSON(TypeDecorator):
    impl = JSON
    cache_ok = True

    def process_bind_param(self, value, dialect):
        cipher = data_cipher()
        if cipher and value is not None:
            return {
                "_encrypted_v1": cipher.encrypt(
                    json.dumps(value, default=str).encode()
                ).decode()
            }
        return value

    def process_result_value(self, value, dialect):
        if isinstance(value, dict) and "_encrypted_v1" in value:
            cipher = data_cipher()
            if cipher is None:
                raise RuntimeError("Encryption key is required")
            return json.loads(cipher.decrypt(value["_encrypted_v1"].encode()))
        return value
