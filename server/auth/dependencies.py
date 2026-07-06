import os
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from auth.jwt import decode_token
from auth.models import Permission, Role, TokenData
from auth.user_store import get_user

_security = HTTPBearer(auto_error=False)
_AUTH_ENABLED: bool = False


def configure_auth(enabled: bool):
    global _AUTH_ENABLED
    _AUTH_ENABLED = enabled


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_security),
) -> Optional[TokenData]:
    if not _AUTH_ENABLED:
        return TokenData(sub="anonymous", role=Role.READ_ONLY, exp=0, iat=0, type="access")

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_data = decode_token(credentials.credentials)
    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return token_data


async def require_permission(required: Permission):
    def _checker(current_user: Optional[TokenData] = Depends(get_current_user)) -> TokenData:
        if not _AUTH_ENABLED:
            return current_user
        user = get_user(current_user.sub)
        if user is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not found")
        from auth.models import ROLE_PERMISSIONS
        permissions = ROLE_PERMISSIONS.get(user.role, set())
        if required not in permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permission: {required.value}",
            )
        return current_user
    return _checker


async def require_role(minimum_role: Role):
    role_hierarchy = {
        Role.READ_ONLY: 0,
        Role.MARKETING: 1,
        Role.SUPPORT: 2,
        Role.SALES: 3,
        Role.MANAGER: 4,
        Role.BUSINESS_OWNER: 5,
        Role.SUPER_ADMIN: 6,
    }

    def _checker(current_user: Optional[TokenData] = Depends(get_current_user)) -> TokenData:
        if not _AUTH_ENABLED:
            return current_user
        user = get_user(current_user.sub)
        if user is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not found")
        if role_hierarchy.get(user.role, -1) < role_hierarchy.get(minimum_role, 0):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role.value}' insufficient, requires '{minimum_role.value}'",
            )
        return current_user
    return _checker
