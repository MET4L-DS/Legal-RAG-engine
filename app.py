"""
Hugging Face Spaces Entry Point for Legal RAG Engine.
This file is required by HF Spaces to launch the FastAPI application.
"""
import os
import sys

# Set HuggingFace cache to local directory
os.environ["HF_HOME"] = os.path.join(os.getcwd(), ".hf_cache")
os.environ["TRANSFORMERS_CACHE"] = os.path.join(os.getcwd(), ".hf_cache")

# HF Spaces uses port 7860 by default
os.environ["PORT"] = "7860"

# Import and run the FastAPI app
from src.server.app import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)
