from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class Role(str, Enum):
    SUPER_ADMIN = "super_admin"
    BUSINESS_OWNER = "business_owner"
    MANAGER = "manager"
    SALES = "sales"
    SUPPORT = "support"
    MARKETING = "marketing"
    READ_ONLY = "read_only"


class Permission(str, Enum):
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"


ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.SUPER_ADMIN: {Permission.READ, Permission.WRITE, Permission.DELETE, Permission.ADMIN},
    Role.BUSINESS_OWNER: {Permission.READ, Permission.WRITE, Permission.DELETE, Permission.ADMIN},
    Role.MANAGER: {Permission.READ, Permission.WRITE, Permission.DELETE},
    Role.SALES: {Permission.READ, Permission.WRITE},
    Role.SUPPORT: {Permission.READ, Permission.WRITE},
    Role.MARKETING: {Permission.READ},
    Role.READ_ONLY: {Permission.READ},
}


class TokenRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str


class UserCreate(BaseModel):
    username: str
    password: str
    email: str
    role: Role = Role.READ_ONLY
    display_name: str = ""


class UserResponse(BaseModel):
    username: str
    email: str
    role: Role
    display_name: str
    permissions: list[Permission]
    is_active: bool


class UserInDB(BaseModel):
    username: str
    email: str
    hashed_password: str
    role: Role = Role.READ_ONLY
    display_name: str = ""
    is_active: bool = True


class TokenData(BaseModel):
    sub: str
    role: Role
    exp: int
    iat: int
    type: str = "access"
