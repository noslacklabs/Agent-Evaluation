from __future__ import annotations

import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from config import DATA_DIR, ensure_directories


KEY_FILE = DATA_DIR / ".evaluator.key"


def _load_key() -> bytes:
    configured = os.getenv("EVALUATOR_ENCRYPTION_KEY")
    if configured:
        return configured.encode("utf-8")
    ensure_directories()
    if KEY_FILE.exists():
        return KEY_FILE.read_bytes().strip()
    key = Fernet.generate_key()
    KEY_FILE.write_bytes(key)
    try:
        KEY_FILE.chmod(0o600)
    except OSError:
        pass
    return key


def encrypt_secret(value: str | None) -> str | None:
    if not value:
        return None
    return Fernet(_load_key()).encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return Fernet(_load_key()).decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Stored evaluator credential cannot be decrypted") from exc

