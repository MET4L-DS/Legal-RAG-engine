import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# 1. Setup Logging FIRST (do this before any other imports that might log)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()  # Only stream to stdout for Render
    ]
)
logger = logging.getLogger("LegalRAG-Server")

# 2. Load Environment
load_dotenv()

# 3. Pydantic Models for API Contract
class QueryRequest(BaseModel):
    query: str = Field(..., example="What is the procedure for zero FIR?")
    stream: bool = Field(default=False)

class LegalSourceInfo(BaseModel):
    law: str
    section: str
    citation: str
    text: str

class LegalResponseModel(BaseModel):
    answer: str
    safety_alert: Optional[str] = None
    immediate_action_plan: List[str] = []
    legal_basis: str
    procedure_steps: List[str]
    important_notes: List[str]
    sources: List[LegalSourceInfo]
    metadata: Dict[str, Any]

# 4. Global State
engine = None
engine_loading = False
engine_error = None

def load_engine_sync():
    """Synchronously load the engine. Called from background task."""
    global engine, engine_loading, engine_error
    try:
        logger.info("Background: Starting Legal Engine load...")
        from ..retrieval.engine import LegalEngine
        engine = LegalEngine()
        logger.info("Background: Legal Engine loaded successfully!")
    except Exception as e:
        logger.error(f"Background: Failed to load engine: {e}", exc_info=True)
        engine_error = str(e)
    finally:
        engine_loading = False

async def load_engine_background():
    """Run engine loading in a thread pool to not block the event loop."""
    global engine_loading
    engine_loading = True
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, load_engine_sync)

# 5. Lifespan Context Manager (Modern FastAPI approach)
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Schedule engine loading but don't await it
    logger.info("Server starting up. Scheduling engine load in background...")
    asyncio.create_task(load_engine_background())
    yield
    # Shutdown
    logger.info("Server shutting down.")

# 6. Initialize FastAPI with lifespan
app = FastAPI(
    title="Legal RAG Engine API",
    description="Backend for high-precision Indian Legal Retrieval and Answer Generation",
    version="1.0.0",
    lifespan=lifespan
)

# 7. Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 8. Endpoints
@app.get("/health")
async def health_check():
    status = "loading" if engine_loading else ("ready" if engine else "error")
    return {
        "status": "ok" if engine else "starting",
        "engine_status": status,
        "error": engine_error
    }

@app.post("/api/v1/query", response_model=LegalResponseModel)
async def process_query(request: QueryRequest):
    if engine_loading:
        raise HTTPException(status_code=503, detail="Legal Engine is still loading. Please wait.")
    if not engine:
        raise HTTPException(status_code=503, detail=f"Legal Engine failed to load: {engine_error}")
    
    start_time = time.time()
    logger.info(f"Received query: {request.query}")
    
    try:
        result = engine.query(request.query)
        raw_response = result["response"]
        
        sources = []
        for s in raw_response.get("sources", []):
            sources.append(LegalSourceInfo(
                law=s.get("law", "Unknown"),
                section=s.get("section", "Unknown"),
                citation=s.get("citation", "Unknown"),
                text=s.get("content", "")
            ))
            
        response = LegalResponseModel(
            answer=raw_response.get("answer", ""),
            safety_alert=raw_response.get("safety_alert"),
            immediate_action_plan=raw_response.get("immediate_action_plan", []),
            legal_basis=raw_response.get("legal_basis", ""),
            procedure_steps=raw_response.get("procedure_steps", []),
            important_notes=raw_response.get("important_notes", []),
            sources=sources,
            metadata=result.get("intent", {})
        )
        
        elapsed_time = time.time() - start_time
        logger.info(f"Query processed in {elapsed_time:.2f}s")
        
        return response

    except Exception as e:
        logger.error(f"Error processing query '{request.query}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    logger.info(f"Starting server on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)
