from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.swagger import router as swagger_router
from app.api.query import router as query_router
from app.api.endpoints import router as endpoints_router
from app.api.confirmations import router as confirmations_router
from app.api.relations import router as relations_router
from app.api.scenarios import router as scenarios_router
from app.api.widgets import router as widgets_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(swagger_router, prefix="/swagger", tags=["swagger"])
api_router.include_router(endpoints_router, prefix="/endpoints", tags=["endpoints"])
api_router.include_router(query_router, tags=["query"])
api_router.include_router(confirmations_router, tags=["confirmations"])
api_router.include_router(relations_router, prefix="/relations", tags=["relations"])
api_router.include_router(scenarios_router, tags=["scenarios"])
api_router.include_router(widgets_router, tags=["widgets"])
