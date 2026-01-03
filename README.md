# Legal RAG CLI

A hierarchical Retrieval-Augmented Generation (RAG) system for Indian legal documents. This system implements a 4-stage retrieval pipeline (Document → Chapter → Section → Subsection) for accurate legal information retrieval.

## Features

-   ✅ **Hierarchical Document Parsing**: Extracts structure from legal PDFs (Chapters, Sections, Subsections)
-   ✅ **Multi-Level Embeddings**: Creates embeddings at all hierarchy levels with type-based weighting
-   ✅ **Hybrid Search**: Combines vector similarity (FAISS) with keyword matching (BM25)
-   ✅ **4-Stage Retrieval**: Document routing → Chapter search → Section search → Subsection search
-   ✅ **Citation Support**: Generates proper legal citations for all results
-   ✅ **LLM Integration**: Optional OpenAI integration for natural language answers

## Supported Documents

-   Bharatiya Nyaya Sanhita (BNS) 2023
-   Bharatiya Nagarik Suraksha Sanhita (BNSS) 2023
-   Bharatiya Sakshya Adhiniyam (BSA) 2023

## Installation

1. Create and activate a virtual environment:

```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. (Optional) Set up Google Gemini for LLM-generated answers:

```bash
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY
# Get your free API key at: https://aistudio.google.com/apikey
```

## Quick Start

### Step 1: Parse PDF Documents

```bash
python cli.py parse
```

This extracts the hierarchical structure from PDFs in `./documents/` and saves JSON files to `./data/parsed/`.

### Step 2: Build Vector Indices

```bash
python cli.py index
```

This generates embeddings and builds FAISS indices at all hierarchy levels.

### Step 3: Query the System

```bash
# Single query
python cli.py query "What is the punishment for murder?"

# With verbose output (shows all retrieval stages)
python cli.py query "What is theft?" --verbose

# Without LLM answer
python cli.py query "Define abetment" --no-llm
```

### Step 4: Interactive Chat

```bash
python cli.py chat
```

## CLI Commands

### `parse`

Parse PDF documents into structured JSON.

```bash
python cli.py parse [OPTIONS]

Options:
  -d, --documents-dir PATH  Directory containing PDFs [default: ./documents]
  -o, --output-dir PATH     Output directory for JSON [default: ./data/parsed]
```

### `index`

Generate embeddings and build vector indices.

```bash
python cli.py index [OPTIONS]

Options:
  -p, --parsed-dir PATH  Directory with parsed JSON [default: ./data/parsed]
  -i, --index-dir PATH   Output directory for indices [default: ./data/indices]
  -m, --model TEXT       Embedding model [default: sentence-transformers/all-MiniLM-L6-v2]
```

### `query`

Search the legal database.

```bash
python cli.py query QUESTION [OPTIONS]

Options:
  -i, --index-dir PATH  Index directory [default: ./data/indices]
  -m, --model TEXT      Embedding model
  -k, --top-k INT       Number of results [default: 5]
  --no-llm              Skip LLM answer generation
  -v, --verbose         Show detailed retrieval stages
```

### `chat`

Start an interactive chat session.

```bash
python cli.py chat [OPTIONS]

Options:
  -i, --index-dir PATH  Index directory [default: ./data/indices]
  -m, --model TEXT      Embedding model
```

### `stats`

Show index statistics.

```bash
python cli.py stats [OPTIONS]

Options:
  -i, --index-dir PATH  Index directory [default: ./data/indices]
```

## Architecture

```
Document Level (Acts / Laws)
   ↓ coarse routing
Chapter Level (Topics)
   ↓ topic narrowing
Section Level (Legal rules)
   ↓ legal targeting
Subsection / Clause Level (Exact law text)
   ↓ final answer grounding
LLM Answer with Citation
```

### Embedding Strategy

| Level      | Input for Embedding                 |
| ---------- | ----------------------------------- |
| Document   | Summary of all chapters             |
| Chapter    | Weighted mean of section embeddings |
| Section    | Title + full section text           |
| Subsection | Contextual clause text              |

### Subsection Type Weights

For section-level embeddings, subsections are weighted by legal importance:

| Type         | Weight |
| ------------ | ------ |
| Punishment   | 0.35   |
| Definition   | 0.25   |
| Provision    | 0.20   |
| Explanation  | 0.10   |
| Exception    | 0.05   |
| Illustration | 0.03   |
| General      | 0.02   |

## Example Queries

```bash
# Punishment queries
python cli.py query "What is the punishment for murder?"
python cli.py query "What are the penalties for theft?"

# Definition queries
python cli.py query "Define abetment"
python cli.py query "What is the definition of culpable homicide?"

# Procedural queries
python cli.py query "What is the procedure for arrest?"
python cli.py query "How is evidence recorded?"
```

## Project Structure

```
.
├── cli.py                 # Main CLI entry point
├── requirements.txt       # Python dependencies
├── .env.example          # Environment variables template
├── PLAN.md               # Architecture plan
├── README.md             # This file
├── documents/            # PDF legal documents
│   ├── BNS.pdf
│   ├── BNSS.pdf
│   └── BSA.pdf
├── data/                 # Generated data (gitignored)
│   ├── parsed/           # Parsed JSON documents
│   └── indices/          # FAISS vector indices
└── src/
    ├── __init__.py
    ├── models.py         # Data models
    ├── pdf_parser.py     # PDF parsing logic
    ├── embedder.py       # Hierarchical embedding generator
    ├── vector_store.py   # Multi-level FAISS indices
    └── retriever.py      # 4-stage retrieval pipeline
```

## Embedding Models

You can use different sentence transformer models:

| Model                                     | Dimension | Quality | Speed  |
| ----------------------------------------- | --------- | ------- | ------ |
| `sentence-transformers/all-MiniLM-L6-v2`  | 384       | Good    | Fast   |
| `sentence-transformers/all-mpnet-base-v2` | 768       | Better  | Medium |
| `BAAI/bge-base-en-v1.5`                   | 768       | Best    | Medium |

Change the model with:

```bash
python cli.py index --model BAAI/bge-base-en-v1.5
python cli.py query "your question" --model BAAI/bge-base-en-v1.5
```

## License

This project is for educational purposes.
