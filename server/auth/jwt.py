from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from auth.models import Role, TokenData

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Will be set from settings at startup
_SECRET_KEY: str = ""
_ALGORITHM = "HS256"
_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
_REFRESH_TOKEN_EXPIRE_DAYS: int = 7


def configure_jwt(secret_key: str, access_expire_minutes: int = 30, refresh_expire_days: int = 7):
    global _SECRET_KEY, _ACCESS_TOKEN_EXPIRE_MINUTES, _REFRESH_TOKEN_EXPIRE_DAYS
    _SECRET_KEY = secret_key
    _ACCESS_TOKEN_EXPIRE_MINUTES = access_expire_minutes
    _REFRESH_TOKEN_EXPIRE_DAYS = refresh_expire_days


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=_ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"iat": int(now.timestamp()), "exp": int(expire.timestamp()), "type": "access"})
    return jwt.encode(to_encode, _SECRET_KEY, algorithm=_ALGORITHM)


def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(days=_REFRESH_TOKEN_EXPIRE_DAYS))
    to_encode.update({"iat": int(now.timestamp()), "exp": int(expire.timestamp()), "type": "refresh"})
    return jwt.encode(to_encode, _SECRET_KEY, algorithm=_ALGORITHM)


def decode_token(token: str) -> Optional[TokenData]:
    try:
        payload = jwt.decode(token, _SECRET_KEY, algorithms=[_ALGORITHM])
        return TokenData(
            sub=payload.get("sub", ""),
            role=Role(payload.get("role", Role.READ_ONLY.value)),
            exp=payload.get("exp", 0),
            iat=payload.get("iat", 0),
            type=payload.get("type", "access"),
        )
    except (JWTError, ValueError, KeyError):
        return None
