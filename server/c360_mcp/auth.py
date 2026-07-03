import os
import secrets
import hashlib
from pathlib import Path

API_KEY_ENV_VAR = "C360_TRAINING_API_KEY"
_API_KEY_HASH_ENV_VAR = "C360_API_KEY_HASH"

ALL_PERMISSIONS = {
    "customers:read",
    "customers:list",
    "customers:export",
    "alerts:read",
    "alerts:list",
    "stats:read",
    "training:export",
    "training:full",
}

_loaded = False


def _ensure_loaded():
    global _loaded
    if _loaded:
        return
    _loaded = True
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())
    raw = os.environ.get(API_KEY_ENV_VAR, "")
    if raw:
        store_key_hash(raw)


def generate_api_key() -> str:
    raw = f"c360_tr_{secrets.token_hex(32)}"
    store_key_hash(raw)
    return raw


def store_key_hash(raw_key: str):
    h = hashlib.sha256(raw_key.encode()).hexdigest()
    os.environ[_API_KEY_HASH_ENV_VAR] = h


def hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


def set_key_from_env():
    _ensure_loaded()
    existing = os.environ.get(API_KEY_ENV_VAR, "")
    if existing:
        store_key_hash(existing)
        return existing
    return ""


def validate_api_key(raw_key: str):
    _ensure_loaded()
    if not raw_key:
        return None
    stored_hash = os.environ.get(_API_KEY_HASH_ENV_VAR, "")
    if not stored_hash:
        raw = os.environ.get(API_KEY_ENV_VAR, "")
        if raw:
            stored_hash = hash_key(raw)
        else:
            return None
    if hash_key(raw_key) != stored_hash:
        return None
    return {"permissions": list(ALL_PERMISSIONS), "scope": "training"}


def get_training_api_key() -> str:
    _ensure_loaded()
    return os.environ.get(API_KEY_ENV_VAR, "")
