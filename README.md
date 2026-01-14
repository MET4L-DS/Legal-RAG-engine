# Legal RAG CLI

A hierarchical Retrieval-Augmented Generation (RAG) system for Indian legal documents. This system implements a 4-stage retrieval pipeline (Document → Chapter → Section → Subsection) for accurate legal information retrieval.

## Features

-   ✅ **Hierarchical Document Parsing**: Extracts structure from legal PDFs (Chapters, Sections, Subsections)
-   ✅ **Multi-Level Embeddings**: Creates embeddings at all hierarchy levels with type-based weighting
-   ✅ **Hybrid Search**: Combines vector similarity (40%) with keyword matching (60% BM25)
-   ✅ **Intelligent Query Processing**: Detects explicit section references and topic keywords
-   ✅ **4-Stage Retrieval**: Document routing → Chapter search → Section search → Subsection search
-   ✅ **Citation Support**: Generates proper legal citations for all results
-   ✅ **LLM Integration**: Google Gemini integration with retry logic and model fallback

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

### Retrieval Pipeline

```
Query Processing
   ↓ extract hints (section numbers, topics)
Document Level (Acts / Laws)
   ↓ route to relevant law (BNS/BNSS/BSA)
Chapter Level (Topics)
   ↓ find relevant chapters
Section Level (Legal rules)
   ↓ retrieve applicable sections
Subsection / Clause Level (Exact law text)
   ↓ extract precise provisions
LLM Answer Generation (Gemini)
   ↓ synthesize with citations
Final Answer with Legal References
```

### Current Index Statistics

-   **Total Documents**: 3 (BNS, BNSS, BSA)
-   **Total Chapters**: 80
-   **Total Sections**: 1,240
-   **Total Subsections**: 3,919
-   **Embedding Dimension**: 384 (all-MiniLM-L6-v2)

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

### Hybrid Search Strategy

The system uses a weighted combination of two search methods at each hierarchy level:

**Vector Search (40%)**

-   Uses FAISS IndexFlatIP for cosine similarity
-   Captures semantic meaning and context
-   Handles paraphrased or conceptual queries
-   Best for: "What protections exist for assault victims?"

**Keyword Search (60%)**

-   Uses BM25Okapi algorithm for term matching
-   Captures exact legal terminology and phrases
-   Handles specific section references
-   Best for: "Section 64 BNSS" or "rape victim medical examination"

**Final Score**: `0.4 × vector_similarity + 0.6 × min(bm25_score/10, 1.0)`

The higher BM25 weight ensures precise legal terminology matching, critical for legal search accuracy.

### Query Processing Intelligence

The system automatically detects and processes:

1. **Explicit Section References**

    - Pattern: "Section 103", "Sec 184 BNSS", "Section 64 of BNSS"
    - Action: Direct lookup bypassing full retrieval pipeline
    - Example: "Section 184 BNSS" → instantly returns medical examination provisions

2. **Topic Keywords Expansion**

    - Maps common terms to legal terminology
    - Example: "rape survivor" expands to [rape, victim, sexual, woman, examination, medical, complaint, fir, investigation, accused]
    - Improves recall for non-legal queries

3. **Document Hints**
    - Detects document abbreviations (BNS, BNSS, BSA)
    - Routes query to specific law for faster search

## LLM Integration (Google Gemini)

The system uses Google's Gemini API for generating natural language answers:

**Primary Model**: `gemini-2.5-flash-lite`

-   Fast, cost-effective for legal Q&A
-   Fallback to `gemini-2.0-flash` on failure

**Features**:

-   **Automatic Retry**: 3 attempts per model with exponential backoff
-   **Rate Limit Handling**: Waits 10s, 20s, 30s between retries
-   **Context-Aware**: Receives retrieved sections with full legal text
-   **Citation Grounding**: Answers reference specific sections

**Prompt Structure**:

```
Context: [Retrieved legal sections with titles and text]

Question: [User's query]

Instructions: Provide accurate answer based on context.
Cite sections using format: "Section X of [Act]".
```

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

# Victim rights queries
python cli.py query "What can a woman do if she is assaulted?"
python cli.py query "How can a rape survivor fight back legally?"

# Direct section lookup
python cli.py query "Section 103 BNS"
python cli.py query "Section 184 of BNSS"
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

## Performance & Troubleshooting

### Query Best Practices

**For Best Results:**

-   Use specific legal terminology when known
-   Include act abbreviation (BNS/BNSS/BSA) to narrow scope
-   For section lookups, use format: "Section [number] [act]"
-   For topic queries, be descriptive: "medical examination of assault victims"

**Examples:**

-   ✅ Good: "What is the punishment for murder under BNS?"
-   ✅ Good: "Section 184 BNSS medical examination"
-   ❌ Less effective: "murder" (too broad)

### Common Issues

**Empty Results:**

-   Try broader terms or synonyms
-   Remove act abbreviation to search all documents
-   Use `--verbose` to see retrieval stages

**Irrelevant Results:**

-   Add more specific keywords
-   Include section number if known
-   Specify the act (BNS/BNSS/BSA)

**LLM Errors:**

-   Ensure `GEMINI_API_KEY` is set in `.env`
-   Check internet connectivity
-   Use `--no-llm` flag to skip LLM and see raw results
-   Rate limits: System auto-retries, wait 30-60 seconds

### Index Rebuilding

If you modify the PDFs or update the parsing logic:

```bash
# Re-parse documents
python cli.py parse

# Rebuild indices
python cli.py index

# Verify with stats
python cli.py stats
```

## License

This project is for educational purposes.
