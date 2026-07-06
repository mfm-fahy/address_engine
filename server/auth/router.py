from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status

from auth.audit import audit_logger
from auth.dependencies import get_current_user
from auth.jwt import create_access_token, create_refresh_token, decode_token
from auth.models import (
    RefreshRequest,
    Role,
    TokenData,
    TokenRequest,
    TokenResponse,
    UserResponse,
)
from auth.rate_limiter import check_rate_limit
from auth.user_store import authenticate_user, get_user, load_users, user_count

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.on_event("startup")
async def load_auth_users():
    load_users()


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("/login", response_model=TokenResponse)
async def login(request: Request, body: TokenRequest):
    ip = _client_ip(request)

    allowed, remaining, _ = check_rate_limit(f"login:{ip}")
    if not allowed:
        audit_logger.log("rate_limit_exceeded", body.username, ip, success=False)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Try again later.",
        )

    user = authenticate_user(body.username, body.password)
    if user is None:
        audit_logger.log("login_failed", body.username, ip, success=False)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_data = {"sub": user.username, "role": user.role.value}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    audit_logger.log("login_success", user.username, ip, success=True)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=1800,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(request: Request, body: RefreshRequest):
    ip = _client_ip(request)
    token_data = decode_token(body.refresh_token)
    if token_data is None or token_data.type != "refresh":
        audit_logger.log("refresh_failed", "unknown", ip, success=False, details={"reason": "invalid_token"})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    user = get_user(token_data.sub)
    if user is None or not user.is_active:
        audit_logger.log("refresh_failed", token_data.sub, ip, success=False, details={"reason": "user_inactive"})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    new_data = {"sub": user.username, "role": user.role.value}
    new_access = create_access_token(new_data)
    new_refresh = create_refresh_token(new_data)

    audit_logger.log("refresh_success", user.username, ip, success=True)

    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        expires_in=1800,
    )


@router.get("/me", response_model=UserResponse)
async def me(current_user: Optional[TokenData] = Depends(get_current_user)):
    if current_user is None or current_user.sub == "anonymous":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    user = get_user(current_user.sub)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    from auth.models import ROLE_PERMISSIONS
    permissions = list(ROLE_PERMISSIONS.get(user.role, set()))
    return UserResponse(
        username=user.username,
        email=user.email,
        role=user.role,
        display_name=user.display_name,
        permissions=permissions,
        is_active=user.is_active,
    )


@router.get("/status")
async def auth_status():
    return {
        "enabled": True,
        "users_configured": user_count(),
    }
