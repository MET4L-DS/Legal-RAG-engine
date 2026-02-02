#!/bin/bash
echo "Starting Legal RAG Engine Pre-flight..."
echo "Current Directory: $(pwd)"
echo "Listing data directory..."
ls -R data/

if [ -z "$PORT" ]; then
    echo "PORT not set, defaulting to 10000"
    PORT=10000
fi

echo "Binding to PORT: $PORT"

# Run Uvicorn with explicit shell expansion
uvicorn src.server.app:app --host 0.0.0.0 --port "$PORT"
