import logging
import os
import time
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from ..retrieval.engine import LegalEngine

# 1. Setup Logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("server_debug.log"),
        logging.StreamHandler()
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
    legal_basis: str
    procedure_steps: List[str]
    important_notes: List[str]
    sources: List[LegalSourceInfo]
    metadata: Dict[str, Any]

# 4. Initialize FastAPI
app = FastAPI(
    title="Legal RAG Engine API",
    description="Backend for high-precision Indian Legal Retrieval and Answer Generation",
    version="1.0.0"
)

# 5. Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 6. Global State (Legal Engine)
engine: Optional[LegalEngine] = None

@app.on_event("startup")
async def startup_event():
    global engine
    logger.info("Starting up Legal RAG Engine...")
    try:
        engine = LegalEngine()
        logger.info("Legal Engine initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize Legal Engine: {e}", exc_info=True)
        raise e

# 7. Endpoints
@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "components": {
            "vector_store": "ready" if engine else "not_ready",
            "llm": "ready"
        }
    }

@app.post("/api/v1/query", response_model=LegalResponseModel)
async def process_query(request: QueryRequest):
    if not engine:
        logger.error("Query received but Engine is not initialized.")
        raise HTTPException(status_code=503, detail="Legal Engine is not ready.")
    
    start_time = time.time()
    logger.debug(f"Received query: {request.query}")
    
    try:
        # Execute Full RAG cycle
        result = engine.query(request.query)
        
        # Prepare response
        # Note: final_output mapped into LegalResponseModel
        raw_response = result["response"]
        
        # Map sources
        sources = []
        # Result context_used has citations, but we want full Source details from response sources
        for s in raw_response.get("sources", []):
            sources.append(LegalSourceInfo(
                law=s.get("law", "Unknown"),
                section=s.get("section", "Unknown"),
                citation=s.get("citation", "Unknown"),
                text=s.get("content", "")
            ))
            
        response = LegalResponseModel(
            answer=raw_response.get("answer", ""),
            legal_basis=raw_response.get("legal_basis", ""),
            procedure_steps=raw_response.get("procedure_steps", []),
            important_notes=raw_response.get("important_notes", []),
            sources=sources,
            metadata=result.get("intent", {})
        )
        
        elapsed_time = time.time() - start_time
        logger.info(f"Query processed in {elapsed_time:.2f}s")
        logger.debug(f"Intent detected: {result['intent'].get('category')}")
        
        return response

    except Exception as e:
        logger.error(f"Error processing query '{request.query}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    # Use environment port or default to 8000
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
