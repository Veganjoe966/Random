"""
V1 API router — aggregates all endpoint routers.
"""

from fastapi import APIRouter

from app.api.v1.endpoints.analytics import router as analytics_router
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.billing import router as billing_router
from app.api.v1.endpoints.recitations import router as recitations_router
from app.api.v1.endpoints.students import router as students_router
from app.api.v1.endpoints.tenants import router as tenants_router

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(tenants_router)
api_router.include_router(recitations_router)
api_router.include_router(students_router)
api_router.include_router(analytics_router)
api_router.include_router(billing_router)
