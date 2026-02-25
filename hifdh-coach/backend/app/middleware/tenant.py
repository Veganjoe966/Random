"""
Multi-tenant middleware.
Extracts tenant_id from JWT and sets PostgreSQL RLS context.
"""

from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import Role, decode_token, has_minimum_role, has_permission

security_scheme = HTTPBearer()


class CurrentUser:
    """Authenticated user context extracted from JWT."""

    def __init__(
        self,
        user_id: UUID,
        tenant_id: UUID | None,
        role: Role,
        claims: dict,
    ) -> None:
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.role = role
        self.claims = claims

    @property
    def is_super_admin(self) -> bool:
        return self.role == Role.SUPER_ADMIN


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
) -> CurrentUser:
    """
    FastAPI dependency: decode JWT, return CurrentUser.
    Raises 401 if token is invalid.
    """
    try:
        payload = decode_token(credentials.credentials)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    user_id = UUID(payload["sub"])
    tenant_id = UUID(payload["tid"]) if payload.get("tid") else None
    role = Role(payload["role"])

    return CurrentUser(
        user_id=user_id,
        tenant_id=tenant_id,
        role=role,
        claims=payload,
    )


async def set_tenant_context(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> AsyncSession:
    """
    FastAPI dependency: sets RLS tenant context on the database session.
    Must be used for all tenant-scoped endpoints.
    """
    if user.tenant_id:
        await db.execute(
            text("SET LOCAL app.current_tenant = :tid"),
            {"tid": str(user.tenant_id)},
        )
    return db


def require_role(minimum_role: Role):
    """
    Dependency factory: require user has at least the given role.

    Usage:
        @router.get("/admin", dependencies=[Depends(require_role(Role.MASJID_ADMIN))])
    """
    async def _check(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not has_minimum_role(user.role, minimum_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role: {minimum_role.value} or higher",
            )
        return user

    return _check


def require_permission(permission: str):
    """
    Dependency factory: require user has a specific permission.

    Usage:
        @router.post("/upload", dependencies=[Depends(require_permission("upload_recitation"))])
    """
    async def _check(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not has_permission(user.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permission: {permission}",
            )
        return user

    return _check
