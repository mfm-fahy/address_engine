import os

from auth.jwt import (
    configure_jwt,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from auth.models import Permission, Role, ROLE_PERMISSIONS
from auth.rate_limiter import InMemoryRateLimiter, configure_rate_limiter, check_rate_limit


class TestAuthJWT:

    def setup_method(self):
        configure_jwt("test-secret-key-for-unit-tests", 30, 7)

    def test_password_hashing(self):
        hashed = get_password_hash("my_password")
        assert verify_password("my_password", hashed)
        assert not verify_password("wrong_password", hashed)

    def test_create_and_decode_access_token(self):
        token = create_access_token({"sub": "admin", "role": "super_admin"})
        assert token is not None
        decoded = decode_token(token)
        assert decoded is not None
        assert decoded.sub == "admin"
        assert decoded.role == Role.SUPER_ADMIN
        assert decoded.type == "access"

    def test_create_and_decode_refresh_token(self):
        token = create_refresh_token({"sub": "admin", "role": "super_admin"})
        assert token is not None
        decoded = decode_token(token)
        assert decoded is not None
        assert decoded.type == "refresh"

    def test_decode_invalid_token(self):
        assert decode_token("invalid.token.here") is None
        assert decode_token("") is None

    def test_decode_wrong_key(self):
        token = create_access_token({"sub": "user", "role": "read_only"})
        configure_jwt("different-secret-key")
        assert decode_token(token) is None


class TestAuthRBAC:

    def test_super_admin_has_admin_permission(self):
        perms = ROLE_PERMISSIONS[Role.SUPER_ADMIN]
        assert Permission.ADMIN in perms

    def test_read_only_has_only_read(self):
        perms = ROLE_PERMISSIONS[Role.READ_ONLY]
        assert Permission.READ in perms
        assert Permission.WRITE not in perms
        assert Permission.DELETE not in perms
        assert Permission.ADMIN not in perms

    def test_business_owner_has_admin(self):
        perms = ROLE_PERMISSIONS[Role.BUSINESS_OWNER]
        assert Permission.ADMIN in perms

    def test_sales_has_read_write(self):
        perms = ROLE_PERMISSIONS[Role.SALES]
        assert Permission.READ in perms
        assert Permission.WRITE in perms
        assert Permission.DELETE not in perms

    def test_support_has_read_write(self):
        perms = ROLE_PERMISSIONS[Role.SUPPORT]
        assert Permission.READ in perms
        assert Permission.WRITE in perms

    def test_marketing_has_read_only(self):
        perms = ROLE_PERMISSIONS[Role.MARKETING]
        assert Permission.READ in perms
        assert Permission.WRITE not in perms

    def test_all_roles_have_read(self):
        for role in Role:
            assert Permission.READ in ROLE_PERMISSIONS[role]


class TestRateLimiter:

    def test_allows_requests_within_limit(self):
        limiter = InMemoryRateLimiter()
        assert limiter.check("ip1", 5, 60) is True
        assert limiter.check("ip1", 5, 60) is True

    def test_blocks_when_limit_exceeded(self):
        limiter = InMemoryRateLimiter()
        for i in range(5):
            limiter.check("ip2", 5, 60)
        assert limiter.check("ip2", 5, 60) is False

    def test_remaining_count(self):
        limiter = InMemoryRateLimiter()
        assert limiter.remaining("ip3", 10, 60) == 10
        limiter.check("ip3", 10, 60)
        assert limiter.remaining("ip3", 10, 60) == 9

    def test_reset(self):
        limiter = InMemoryRateLimiter()
        for i in range(5):
            limiter.check("ip4", 5, 60)
        assert limiter.check("ip4", 5, 60) is False
        limiter.reset("ip4")
        assert limiter.check("ip4", 5, 60) is True

    def test_disabled_rate_limiter(self):
        configure_rate_limiter(False)
        allowed, remaining, window = check_rate_limit("any_key")
        assert allowed is True
        assert remaining == 100
