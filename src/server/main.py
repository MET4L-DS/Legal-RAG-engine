"""
FastAPI Application Entry Point.

Legal RAG API - Tiered Legal Procedural RAG Engine

Run with:
    uvicorn src.server.main:app --host 0.0.0.0 --port 8000
    
Or for development:
    uvicorn src.server.main:app --reload
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .api import router
from .dependencies import startup_load

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.
    
    Pre-loads the RAG engine on startup to avoid cold start delays.
    """
    logger.info("Starting Legal RAG API Server...")
    
    # Pre-load RAG engine (loads indices, embedder, etc.)
    startup_load()
    
    yield
    
    # Cleanup on shutdown
    logger.info("Shutting down Legal RAG API Server...")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    
    settings = get_settings()
    
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="""
## Legal RAG API

A hierarchical Retrieval-Augmented Generation (RAG) system for Indian legal documents.

### Features

- **3-Tier Routing**: Automatically routes queries to appropriate context
  - Tier-1: Sexual offence procedures (SOP-backed)
  - Tier-2: Evidence & Compensation guidance
  - Tier-3: General citizen procedures for all crimes
  
- **Hybrid Search**: Combines vector similarity (40%) with BM25 keyword matching (60%)

- **LLM Integration**: Google Gemini for answer generation

### Supported Documents

- BNS (Bharatiya Nyaya Sanhita) 2023
- BNSS (Bharatiya Nagarik Suraksha Sanhita) 2023
- BSA (Bharatiya Sakshya Adhiniyam) 2023
- MHA/BPR&D SOPs and Manuals
""",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    
    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    
    # Include API routes
    app.include_router(router, prefix="/rag", tags=["RAG"])
    
    # Root endpoint
    @app.get("/", tags=["Root"])
    async def root():
        """Root endpoint with API information."""
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs",
            "health": "/rag/health",
            "query": "/rag/query",
            "stats": "/rag/stats",
        }
    
    return app


# Create the app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    settings = get_settings()
    
    uvicorn.run(
        "src.server.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
    )
