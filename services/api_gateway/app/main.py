"""
API Gateway Application Entry Point.

Main FastAPI application that orchestrates all API routes,
WebSocket connections, and initializes core services.
"""

import signal
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import settings
from app.db.session import init_db, close_db
from app.api.v1.endpoints.stream import startup_websocket, shutdown_websocket
from app.api.v1.endpoints.health import router as health_router

# Import for Prometheus metrics
from prometheus_client import make_wsgi_app
from werkzeug.middleware.dispatcher import DispatcherMiddleware


# Custom exception handler
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan management.

    Handles startup and shutdown sequences for all services,
    ensuring proper initialization and cleanup of resources.
    """
    # Startup
    print(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    print(f"Environment: {settings.ENVIRONMENT}")

    # Initialize database
    await init_db()

    # Initialize WebSocket manager
    await startup_websocket()

    print(f"Application started successfully on {settings.HOST}:{settings.PORT}")

    yield

    # Shutdown
    print("Shutting down application...")

    # Cleanup WebSocket manager
    await shutdown_websocket()

    # Close database connections
    await close_db()

    print("Application shutdown complete")


# Create main FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    description="Distributed Real-Time Video Analytics Pipeline",
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)

# Add Prometheus metrics endpoint if enabled
if settings.METRICS_ENABLED:
    metrics_app = make_wsgi_app()
    app = DispatcherMiddleware(app, {
        settings.METRICS_PATH: metrics_app
    })

# Include API routes
app.include_router(api_router, prefix=settings.API_V1_PREFIX)
app.include_router(health_router, prefix="/health")


# Error handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler for consistent error responses.
    """
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "type": "internal_server_error",
                "message": "An unexpected error occurred",
                "detail": str(exc) if settings.DEBUG else None,
            },
            "request_id": request.headers.get("X-Request-ID"),
        },
    )


# Root endpoint
@app.get("/")
async def root() -> dict:
    """Root endpoint with API information."""
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "description": "Distributed Real-Time Video Analytics Pipeline",
        "docs": "/docs",
        "health": "/health/live",
        "api_prefix": settings.API_V1_PREFIX,
    }


# Health check endpoint
app.include_router(health_router)


if __name__ == "__main__":
    import uvicorn

    # Handle graceful shutdown
    def signal_handler(signum, frame):
        print(f"Received signal {signum}, shutting down gracefully...")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start server
    uvicorn.run(
        app,
        host=settings.HOST,
        port=settings.PORT,
        workers=settings.WORKERS if settings.ENVIRONMENT == "production" else 1,
        log_level=settings.LOG_LEVEL.lower(),
    )