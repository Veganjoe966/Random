"""
Authentication and authorization utilities.
JWT token creation, password hashing, permission checks.
"""

from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── Roles ────────────────────────────────────────────────────────────────

class Role(str, Enum):
    SUPER_ADMIN = "super_admin"
    MASJID_ADMIN = "masjid_admin"
    TEACHER = "teacher"
    STUDENT = "student"
    PARENT = "parent"


# Role hierarchy: higher index = more privilege
ROLE_HIERARCHY: dict[Role, int] = {
    Role.STUDENT: 0,
    Role.PARENT: 1,
    Role.TEACHER: 2,
    Role.MASJID_ADMIN: 3,
    Role.SUPER_ADMIN: 4,
}


# Permission matrix: role → allowed actions
ROLE_PERMISSIONS: dict[Role, set[str]] = {
    Role.SUPER_ADMIN: {
        "manage_tenants", "manage_billing", "view_global_analytics",
        "manage_users", "manage_teachers", "manage_students",
        "view_recitations", "override_scores", "manage_settings",
        "export_data", "view_audit_logs",
    },
    Role.MASJID_ADMIN: {
        "manage_users", "manage_teachers", "manage_students",
        "view_recitations", "override_scores", "manage_settings",
        "view_analytics", "export_data", "view_audit_logs",
        "manage_billing",
    },
    Role.TEACHER: {
        "manage_students", "view_recitations", "override_scores",
        "view_analytics", "create_assignments", "view_schedules",
        "add_notes",
    },
    Role.STUDENT: {
        "upload_recitation", "view_own_progress", "view_own_schedule",
        "view_own_scores",
    },
    Role.PARENT: {
        "view_child_progress", "view_child_schedule", "view_child_scores",
    },
}


def has_permission(role: Role, permission: str) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, set())


def has_minimum_role(user_role: Role, required_role: Role) -> bool:
    return ROLE_HIERARCHY.get(user_role, -1) >= ROLE_HIERARCHY.get(required_role, 99)


# ── Password Hashing ────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# ── JWT Tokens ───────────────────────────────────────────────────────────

def create_access_token(
    user_id: UUID,
    tenant_id: UUID | None,
    role: Role,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(UTC)
    claims = {
        "sub": str(user_id),
        "tid": str(tenant_id) if tenant_id else None,
        "role": role.value,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    if extra_claims:
        # Prevent extra_claims from overriding core JWT fields
        protected_keys = {"sub", "tid", "role", "type", "iat", "exp"}
        safe_claims = {k: v for k, v in extra_claims.items() if k not in protected_keys}
        claims.update(safe_claims)
    return jwt.encode(claims, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: UUID, tenant_id: UUID | None) -> str:
    now = datetime.now(UTC)
    claims = {
        "sub": str(user_id),
        "tid": str(tenant_id) if tenant_id else None,
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=settings.refresh_token_expire_days),
    }
    return jwt.encode(claims, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT token. Raises JWTError on failure."""
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])


def decode_token_safe(token: str) -> dict[str, Any] | None:
    """Decode token, return None on failure instead of raising."""
    try:
        return decode_token(token)
    except JWTError:
        return None
