import json
import os
from typing import Optional

from auth.jwt import get_password_hash, verify_password
from auth.models import Role, UserInDB


def _load_users_from_env() -> dict[str, UserInDB]:
    users: dict[str, UserInDB] = {}

    admin_username = os.getenv("AUTH_ADMIN_USERNAME", "admin")
    admin_password = os.getenv("AUTH_ADMIN_PASSWORD", "")
    if admin_password:
        hashed = get_password_hash(admin_password)
        users[admin_username] = UserInDB(
            username=admin_username,
            email=os.getenv("AUTH_ADMIN_EMAIL", f"{admin_username}@localhost"),
            hashed_password=hashed,
            role=Role.SUPER_ADMIN,
            display_name=os.getenv("AUTH_ADMIN_DISPLAY_NAME", "Administrator"),
            is_active=True,
        )

    users_json = os.getenv("AUTH_USERS_JSON", "[]")
    try:
        extra_users = json.loads(users_json)
        for u in extra_users:
            username = u.get("username", "")
            password = u.get("password", "")
            if username and password:
                hashed = get_password_hash(password)
                users[username] = UserInDB(
                    username=username,
                    email=u.get("email", f"{username}@localhost"),
                    hashed_password=hashed,
                    role=Role(u.get("role", Role.READ_ONLY.value)),
                    display_name=u.get("display_name", username),
                    is_active=u.get("is_active", True),
                )
    except (json.JSONDecodeError, ValueError, KeyError):
        pass

    return users


_users: dict[str, UserInDB] = {}


def load_users():
    global _users
    _users = _load_users_from_env()


def get_user(username: str) -> Optional[UserInDB]:
    return _users.get(username)


def authenticate_user(username: str, password: str) -> Optional[UserInDB]:
    user = get_user(username)
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def user_count() -> int:
    return len(_users)
