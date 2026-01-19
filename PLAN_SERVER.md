Perfect timing. Your **CLI-based RAG is now mature enough to be wrapped as a service**. Based on the **current implementation details in README.md** , here is a **clean, low-risk, production-grade plan to design the FastAPI server** without breaking anything you’ve built.

I’ll structure this as:

1️⃣ Design goals
2️⃣ What stays unchanged (important)
3️⃣ Server architecture (FastAPI)
4️⃣ API design (endpoints + schemas)
5️⃣ How to integrate with your existing code
6️⃣ Concurrency, performance, and deployment
7️⃣ What _not_ to do

---

# 1️⃣ Design Goals (Non-Negotiable)

Your FastAPI server must:

- ✅ Expose the **existing RAG engine**, not rewrite it
- ✅ Remain **stateless** (no chat memory inside server)
- ✅ Preserve **Tier-1 / Tier-2 / Tier-3 determinism**
- ✅ Reuse **exact same retrieval logic as CLI**
- ✅ Be easy to test against CLI outputs

Think of the server as:

> **A thin HTTP wrapper around `LegalRAG`**

---

# 2️⃣ What Must Stay UNCHANGED

From your README , the following are already correct and must not be disturbed:

### ❌ Do NOT modify

- `src/retrieval/rag.py`
- `src/retrieval/retriever.py`
- Tier routing logic (`intent.py`)
- Index format (`data/indices`)
- Embedding strategy
- SOP / Evidence / Compensation parsers

### ✅ The server should _call_ these, not replicate them.

---

# 3️⃣ Recommended FastAPI Architecture

## 📁 New Server Layer (Additive)

Add a **new folder**, do not mix with CLI:

```
src/server/
├── __init__.py
├── main.py          # FastAPI app entry
├── api.py           # Route definitions
├── schemas.py       # Request/response models
├── dependencies.py  # RAG engine loader (singleton)
└── config.py        # Env & settings
```

Your existing structure remains untouched.

---

## Why this works

- CLI continues to work independently
- Server uses the **same code paths**
- Easy to diff CLI vs API outputs
- Clean separation of concerns

---

# 4️⃣ Core Server Design (Important)

## 🔹 Singleton RAG Engine (Critical)

You **must load indices once**, not per request.

### `dependencies.py`

```python
from src.retrieval.rag import LegalRAG

_rag_instance = None

def get_rag():
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = LegalRAG(
            index_dir="./data/indices",
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
    return _rag_instance
```

This mirrors how your CLI works .

---

# 5️⃣ API Design (Minimal & Explicit)

## 🔹 Primary Endpoint (This is enough)

### `POST /rag/query`

### Request schema (`schemas.py`)

```python
from pydantic import BaseModel
from typing import Optional, Dict

class RAGQuery(BaseModel):
    query: str
    context: Optional[Dict[str, str]] = None
    no_llm: bool = False
    verbose: bool = False
```

### Response schema

```python
class RAGResponse(BaseModel):
    answer: str
    tier: str
    case_type: Optional[str]
    stage: Optional[str]
    citations: list[str]
    clarification_needed: Optional[Dict]
    confidence: str
```

---

## 🔹 API Handler (`api.py`)

```python
from fastapi import APIRouter, Depends
from src.server.schemas import RAGQuery, RAGResponse
from src.server.dependencies import get_rag

router = APIRouter()

@router.post("/query", response_model=RAGResponse)
def query_rag(payload: RAGQuery, rag=Depends(get_rag)):
    result = rag.query(
        payload.query,
        context=payload.context,
        no_llm=payload.no_llm,
        verbose=payload.verbose
    )
    return result
```

This directly maps to your existing `cli.py query` logic .

---

# 6️⃣ FastAPI App Entry Point

### `main.py`

```python
from fastapi import FastAPI
from src.server.api import router

app = FastAPI(
    title="Legal RAG API",
    version="1.0.0",
    description="Tiered Legal Procedural RAG Engine"
)

app.include_router(router, prefix="/rag")
```

Run with:

```bash
uvicorn src.server.main:app --host 0.0.0.0 --port 8000
```

---

# 7️⃣ Mapping CLI → API (Sanity Check)

| CLI                           | API               |
| ----------------------------- | ----------------- |
| `cli.py query`                | `POST /rag/query` |
| `--no-llm`                    | `no_llm: true`    |
| `--verbose`                   | `verbose: true`   |
| Tier routing                  | Automatic         |
| SOP / Evidence / Compensation | Automatic         |

You should be able to diff outputs **line-by-line**.

---

# 8️⃣ Performance & Concurrency

FastAPI + Uvicorn works well because:

- Indices are loaded once
- Retrieval is CPU-bound but fast
- Gemini calls are async-safe
- Stateless requests scale horizontally

### Recommended run config

```bash
uvicorn src.server.main:app --workers 2
```

Scale workers, not threads.

---

# 9️⃣ Security & Frontend Integration

- Enable **CORS** only for your frontend origin
- Do NOT expose index paths
- Do NOT log raw SOP text
- Do NOT accept file uploads

Frontend (Next.js / React) simply calls:

```ts
POST / rag / query;
```

---

# 🔴 What You MUST NOT Do

🚫 Do not embed FastAPI logic inside `cli.py`
🚫 Do not add chat memory to server
🚫 Do not add LangChain abstractions
🚫 Do not “simplify” tier routing
🚫 Do not expose retrieval internals

Your test guarantees depend on this discipline.

---

# 🧠 Final Verdict

### Yes — you are ready to build the server.

The **correct approach** is:

- FastAPI
- Thin wrapper
- Singleton RAG engine
- One main endpoint
- CLI remains source of truth

This gives you:

- API
- CLI
- Testability
- Frontend readiness
