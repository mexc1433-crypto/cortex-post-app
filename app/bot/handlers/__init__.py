"""Bot handlers for Cortex Post."""
from app.bot.handlers.start import router as start_router
from app.bot.handlers.channels import router as channels_router
from app.bot.handlers.rules import router as rules_router
from app.bot.handlers.templates import router as templates_router
from app.bot.handlers.providers import router as providers_router
from app.bot.handlers.subscription import router as subscription_router

all_routers = [
    start_router,
    channels_router,
    rules_router,
    templates_router,
    providers_router,
    subscription_router,
]

__all__ = ["all_routers"]
