import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.config import settings
from app.database import engine, get_db

# Setup logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Asynchronous context manager for app startup and shutdown events.
    Verifies connection to PostgreSQL database, initializes DB schemas,
    validates the google-genai (Gemini) client at launch, and sets up LangGraph.
    """
    logger.info("Initializing application startup sequence...")

    # 1. Verify and initialize Database Schema
    try:
        from app.models import Base
        async with engine.begin() as conn:
            # Executes Base.metadata.create_all synchronously in a worker thread
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables initialized/verified successfully.")
    except Exception as e:
        logger.critical(f"Failed to initialize database schemas on startup: {e}")

    # 2. Verify google-genai (Gemini) client is ready
    try:
        from google import genai  # noqa: F401 — confirms package is installed
        from app.services.gemini import gemini_service
        if gemini_service.client is not None:
            logger.info(
                f"Gemini client initialized successfully "
                f"(model: {gemini_service.model_name}, SDK: google-genai)."
            )
        else:
            logger.warning(
                "Gemini client is NOT initialized — GEMINI_API_KEY may be missing. "
                "LLM endpoints will return errors until the key is configured."
            )
    except Exception as e:
        logger.error(f"Failed to verify Gemini client on startup: {e}")

    # 3. Initialize HITL Checkpointer and build Graph
    try:
        from app.graph.checkpointer import init_checkpointer, get_checkpointer
        from app.graph.graph import build_graph
        from app.graph import graph as graph_module
        
        await init_checkpointer()
        checkpointer = get_checkpointer()
        graph_module.graph_app = build_graph(checkpointer=checkpointer)
        logger.info(f"LangGraph initialized. HITL_ENABLED={settings.HITL_ENABLED}")
    except Exception as e:
        logger.error(f"Failed to initialize LangGraph checkpointer: {e}")

    yield

    logger.info("Initiating application shutdown sequence...")
    
    # Close Checkpointer
    try:
        from app.graph.checkpointer import close_checkpointer
        await close_checkpointer()
    except Exception as e:
        logger.error(f"Failed to close checkpointer: {e}")

    # Dispose connection pools properly
    await engine.dispose()
    logger.info("Database connection pool disposed. Shutdown complete.")

# Initialize production-grade FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    description="Scalable, asynchronous backend orchestrator for production-grade AI chatbot platform",
    version="1.0.0",
    lifespan=lifespan
)

# Standard Security/CORS Configuration
from app.api import api_router

app.include_router(api_router, prefix=settings.API_V1_STR)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict this to frontend domains in production environment
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi import Request, Response
from fastapi.responses import JSONResponse
import time
import uuid
import traceback

@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    """
    HTTP Logging and Exception Isolation Middleware.
    Traces incoming queries with scoped Request IDs, handles execution times,
    and isolates unhandled backend crashes under user-friendly 500 responses.
    """
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    
    start_time = time.time()
    logger.info(f"[{request_id}] Incoming: {request.method} {request.url.path} (IP: {request.client.host if request.client else 'unknown'})")
    
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{process_time:.4f}s"
        
        logger.info(f"[{request_id}] Complete: status={response.status_code} duration={process_time:.4f}s")
        return response
    except Exception as exc:
        process_time = time.time() - start_time
        logger.error(f"[{request_id}] Request crash: {request.method} {request.url.path} after {process_time:.4f}s. Exception: {exc}")
        logger.error(traceback.format_exc())
        
        return JSONResponse(
            status_code=500,
            content={
                "detail": "An unexpected server error occurred. Our engineers are investigating.",
                "request_id": request_id
            }
        )

# Root/Health check endpoints
@app.get("/", tags=["Health Check"])
async def root():
    return {
        "status": "online",
        "app_name": settings.APP_NAME,
        "environment": settings.APP_ENV
    }

@app.get("/health", tags=["Health Check"])
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    E2E healthcheck endpoint validating app running status and live DB connectivity.
    """
    try:
        # Validate live connection using raw query
        await db.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "database": "connected",
            "app": "running"
        }
    except Exception as e:
        logger.error(f"Healthcheck failed: {e}")
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e)
        }

if __name__ == "__main__":
    import uvicorn
    # In development, auto-reload enables quick iteration
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=(settings.APP_ENV == "development")
    )
