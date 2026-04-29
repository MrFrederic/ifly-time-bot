from pathlib import Path
import logging
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from .routes import router

# Holds the telegram Application instance, set by create_app()
_application = None
logger = logging.getLogger(__name__)


def create_app(application):
    global _application
    _application = application

    app = FastAPI(docs_url=None, redoc_url=None)
    app.include_router(router, prefix="/api")

    static_dir = Path(__file__).parent / "static"
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

    @app.on_event("startup")
    async def startup_log():
        logger.info("FastAPI startup complete")
        logger.info("Static directory: %s (exists=%s)", static_dir, static_dir.exists())
        route_summaries = []
        for route in app.routes:
            methods = sorted(getattr(route, "methods", []) or [])
            route_summaries.append(f"{','.join(methods) or 'N/A'} {route.path}")
        logger.info("Registered routes (%s): %s", len(route_summaries), " | ".join(route_summaries))

    return app
