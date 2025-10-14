
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from pathlib import Path
from dotenv import load_dotenv

from .api.hr import router as hr_router
from .api.users import router as users_router
from .config import init_settings, get_settings
from .logging_config import setup_logging
from .middleware import APIKeyMiddleware
from .exceptions import UserOnboardingError
from .dependencies import init_user_store

# Load .env from project root
BASE_DIR = Path(__file__).resolve().parent.parent
env_path = BASE_DIR / ".env"
load_dotenv(dotenv_path=env_path)

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager for startup and shutdown events.
    """
    # Startup
    logger.info("Starting User Onboarding Integration API...")
    
    try:
        # Initialize and validate settings
        settings = init_settings()
        logger.info(
            "Configuration loaded successfully",
            extra={
                "okta_url": settings.okta_org_url,
                "log_level": settings.log_level,
                "log_format": settings.log_format,
                "api_key_configured": bool(settings.api_key),
                "storage_backend": settings.storage_backend
            }
        )
        
        # Initialize storage backend
        store = init_user_store()
        logger.info(
            "Storage backend initialized",
            extra={"storage_type": settings.storage_backend}
        )
        
    except Exception as e:
        logger.critical(
            f"Failed to initialize application: {str(e)}",
            exc_info=True
        )
        raise
    
    logger.info("Application startup complete")
    
    yield
    
    # Shutdown
    logger.info("Shutting down User Onboarding Integration API...")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    
    # Initialize settings first to get configuration
    try:
        settings = init_settings()
    except Exception as e:
        # If settings fail to load, use defaults for logging
        print(f"Warning: Failed to load settings, using defaults: {e}")
        settings = None
    
    # Setup structured logging
    if settings:
        setup_logging(log_level=settings.log_level, log_format=settings.log_format)
    else:
        setup_logging()
    
    # Create FastAPI app with lifespan
    app = FastAPI(
        title="User Onboarding Integration API",
        version="1.0.0",
        description="Webhook-driven HR user onboarding with Okta enrichment",
        lifespan=lifespan
    )
    
    # Add CORS middleware (configure as needed for your environment)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure this appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Add API key authentication middleware
    app.add_middleware(APIKeyMiddleware)
    
    # Global exception handler for custom exceptions
    @app.exception_handler(UserOnboardingError)
    async def user_onboarding_exception_handler(request: Request, exc: UserOnboardingError):
        """Handle custom UserOnboardingError exceptions."""
        logger.error(
            f"UserOnboardingError: {str(exc)}",
            extra={"path": request.url.path, "error": str(exc)},
            exc_info=True
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": str(exc)},
        )
    
    # Global exception handler for unhandled exceptions
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(
            f"Unhandled exception: {str(exc)}",
            extra={"path": request.url.path, "error": str(exc)},
            exc_info=True
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )
    
    # Health endpoint
    @app.get("/v1/healthz", tags=["health"])
    async def healthz():
        """Health check endpoint."""
        try:
            settings = get_settings()
            return {
                "status": "ok",
                "version": "1.0.0",
                "okta_configured": bool(settings.okta_org_url and settings.okta_api_token),
                "storage_backend": settings.storage_backend
            }
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"status": "unhealthy", "error": str(e)}
            )
    
    # Include versioned routers
    app.include_router(hr_router, prefix="/v1")
    app.include_router(users_router, prefix="/v1")
    
    return app


# Create the app instance
app = create_app()


