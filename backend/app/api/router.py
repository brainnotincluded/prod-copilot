from fastapi import APIRouter

from app.api.swagger import router as swagger_router
from app.api.query import router as query_router
from app.api.endpoints import router as endpoints_router

api_router = APIRouter()

api_router.include_router(swagger_router, prefix="/swagger", tags=["swagger"])
api_router.include_router(endpoints_router, prefix="/endpoints", tags=["endpoints"])
api_router.include_router(query_router, tags=["query"])
