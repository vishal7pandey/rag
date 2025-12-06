"""
RAG Application Backend
FastAPI Entry Point
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.endpoints import router as api_router
from backend.api.error_handler import register_exception_handlers
from backend.api.middleware import LoggingMiddleware
from backend.config.settings import settings
from backend.core.logging import setup_logging


# Configure structured logging before creating the app
setup_logging(environment=settings.ENVIRONMENT)

app = FastAPI(
    title="RAG Application API",
    description="Production-grade RAG system backend",
    version=settings.VERSION,
)


# Logging + CORS configuration for local development
app.add_middleware(LoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


register_exception_handlers(app)
app.include_router(api_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
