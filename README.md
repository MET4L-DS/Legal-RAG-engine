# Indian Legal RAG Engine (V3)

> **A Victim-Centric Legal Intelligence System** bridging the gap between complex statutes and immediate human needs.

![Status](https://img.shields.io/badge/Status-Active-success)
![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Stack](https://img.shields.io/badge/Stack-FastAPI%20%7C%20LangChain%20%7C%20Gemini-orange)

## 🎯 Project Mission

Traditional legal AI answers "What is the law?". This engine answers **"What should I do right now?"**.

By implementing a **Victim Response Layer (VRL)**, this system dynamically detects distress and prioritizes **safety, immediate action plans, and procedural rights** over abstract legal definitions. It supports the new Indian Criminal Laws (BNS, BNSS, BSA, 2023).

---

## 🚀 Key Innovations

### 1. Victim-Centric Response Layer (VRL)

The system employs a "User Lens" classifier to detect if the user is a victim, accused, or professional. For victims:

- **Prioritizes Safety**: Injecting "Call 112" or medical advice immediately.
- **Action Plans**: Generates structured, chronological steps (e.g., "File Zero FIR -> Get Medical Report").
- **Empathetic Tone**: Uses Grade 8 readability for distress responses.

### 2. "Concept Expansion" Retrieval

Solves the "vocabulary gap" between laymen and law.

- _User says_: "I was beaten up"
- _System searches_: "Section 115 BNS" (Voluntarily causing hurt) **AND** "Section 173 BNSS" (Procedure for FIR).
- _Result_: Retrieves both the offence definition AND the reporting procedure automatically.

### 3. Hybrid Retrieval Pipeline

- **Semantic Search**: `all-MiniLM-L6-v2` (FAISS) for understanding intent.
- **Keyword Search**: `BM25` for precise Section/Act matching.
- **RRF (Reciprocal Rank Fusion)**: Combines results to ensure high precision.

---

## 🛠️ Tech Stack

### AI & Machine Learning

- **Orchestrator**: Google **Gemini 2.0 Flash Lite** (High-speed Intent Classification)
- **Responder**: Google **Gemma 3 27B IT** (Complex Legal Reasoning)
- **Embeddings**: `sentence-transformers/all-MiniLM-L6-v2` (384d)
- **Vector DB**: **FAISS** (CPU optimized)

### Backend Engineering

- **Framework**: **FastAPI** (Async, High-perf)
- **Search**: `rank_bm25` (Sparse retrieval)
- **Processing**: `PyMuPDF` & `pdfplumber` for complex legal text parsing
- **Validation**: Pydantic V2

### Infrastructure

- **Container**: Docker support
- **Deployment**: Configured for **Render** / Railway

---

## 🏗️ Architecture

```mermaid
graph TD
    User[User Query] --> Classifier{Intent & Lens<br/>(Gemini 2.0)}

    Classifier -- "Victim/Distress" --> Expander[Concept Expander]
    Classifier -- "General" --> Search

    Expander -->|Injects Procedure Terms| Search[Hybrid Search]

    subgraph Retrieval
    Search --> FAISS[Semantic Store]
    Search --> BM25[Keyword Index]
    end

    FAISS & BM25 --> RRF[RRF Fusion]
    RRF --> Context[Context Assembly]

    Context --> Responder[Legal Responder<br/>(Gemma 3 27B)]
    Responder --> |"Action Plan + Rights"| Final[Structured Response]
```

---

## 📚 Data Corpus

The engine is trained on authoritative texts, chunked with **hierarchical context preservation**:

| Document          | Description                        | Role                             |
| ----------------- | ---------------------------------- | -------------------------------- |
| **BNS 2023**      | Bharatiya Nyaya Sanhita            | Defines Offences & Punishments   |
| **BNSS 2023**     | Bharatiya Nagarik Suraksha Sanhita | Defines Procedures (FIR, Arrest) |
| **BSA 2023**      | Bharatiya Sakshya Adhiniyam        | Rules of Evidence                |
| **NALSA Schemes** | Compensation Scheme 2018           | Victim Compensation details      |
| **Police SOPs**   | Standard Operating Procedures      | Practical enforcement steps      |

---

## ⚡ Setup & Usage

### 1. Installation

```bash
# Clone
git clone <repo>
cd Embedding-Test-Py

# Virtual Env
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install
pip install -r requirements.txt
```

### 1. Environment Variables

Create a `.env` file in the root directory:

```env
GEMINI_API_KEY=your_google_api_key
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

# Highly recommended for performance:
CLASSIFIER_MODELS=gemma-3-1b-it,gemma-3-2b-it,gemma-3-4b-it
RESPONDER_MODELS=gemma-3-4b-it,gemini-2.5-flash-lite,gemma-3-12b-it
```

### 3. Ingest Data (First Run)

Parses PDFs/MDs and builds the Vector Store + BM25 Index.

```bash
python ingest_legal_docs.py
python create_vector_store.py
```

### 4. Run Server

```bash
python -m src.server.app
# API docs at http://localhost:8000/docs
```

---

## ⚖️ Disclaimer

This tool uses Artificial Intelligence to provide legal information. It is **not** a substitute for professional legal counsel. In emergencies, always contact local authorities (Dial 112 in India).
