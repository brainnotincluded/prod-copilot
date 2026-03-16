from fastapi import APIRouter, Depends

from app.api.auth import router as auth_router, require_auth
from app.api.swagger import router as swagger_router
from app.api.query import router as query_router
from app.api.endpoints import router as endpoints_router
from app.api.confirmations import router as confirmations_router
from app.api.relations import router as relations_router
from app.api.scenarios import router as scenarios_router
from app.api.widgets import router as widgets_router
from app.api.history import router as history_router

api_router = APIRouter()

# Auth routes are public (login, register)
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])

# All other routes require authentication
_auth = [Depends(require_auth)]
api_router.include_router(swagger_router, prefix="/swagger", tags=["swagger"], dependencies=_auth)
api_router.include_router(endpoints_router, prefix="/endpoints", tags=["endpoints"], dependencies=_auth)
api_router.include_router(query_router, tags=["query"])  # WS auth handled separately
api_router.include_router(confirmations_router, tags=["confirmations"], dependencies=_auth)
api_router.include_router(relations_router, prefix="/relations", tags=["relations"], dependencies=_auth)
api_router.include_router(scenarios_router, tags=["scenarios"], dependencies=_auth)
api_router.include_router(widgets_router, tags=["widgets"], dependencies=_auth)
api_router.include_router(history_router, prefix="/history", tags=["history"], dependencies=_auth)
