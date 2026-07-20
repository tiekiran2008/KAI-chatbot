from fastapi import APIRouter
from app.api.endpoints import auth, chat, document, hitl

api_router = APIRouter()

# Include authentication endpoints
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])

# Include chat endpoints
api_router.include_router(chat.router, prefix="/chat", tags=["Chat"])

# Include document endpoints
api_router.include_router(document.router, prefix="/documents", tags=["Documents"])

# Include Human-in-the-Loop approval endpoints
api_router.include_router(hitl.router, prefix="/hitl", tags=["Human-in-the-Loop"])
