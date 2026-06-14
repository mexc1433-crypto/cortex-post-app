"""API Routes for Cortex Post."""
from fastapi import APIRouter

from app.api.routes.channels import router as channels_router
from app.api.routes.rules import router as rules_router
from app.api.routes.templates import router as templates_router
from app.api.routes.providers import router as providers_router
from app.api.routes.posts import router as posts_router, webhook_router
from app.api.routes.subscription import router as subscription_router, admin_router

api_router = APIRouter(prefix="/api")

api_router.include_router(channels_router)
api_router.include_router(rules_router)
api_router.include_router(templates_router)
api_router.include_router(providers_router)
api_router.include_router(posts_router)
api_router.include_router(webhook_router)
api_router.include_router(subscription_router)
api_router.include_router(admin_router)

__all__ = ["api_router"]
