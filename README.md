# Legal RAG CLI

A hierarchical Retrieval-Augmented Generation (RAG) system for Indian legal documents. This system implements a 4-stage retrieval pipeline (Document → Chapter → Section → Subsection) for accurate legal information retrieval.

## Features

-   ✅ **Hierarchical Document Parsing**: Extracts structure from legal PDFs (Chapters, Sections, Subsections)
-   ✅ **SOP Document Support**: Parses procedural documents into actionable blocks with stage classification
-   ✅ **Procedural Query Intelligence**: Detects victim-centric queries and provides step-by-step guidance
-   ✅ **Multi-Level Embeddings**: Creates embeddings at all hierarchy levels with type-based weighting
-   ✅ **Hybrid Search**: Combines vector similarity (40%) with keyword matching (60% BM25)
-   ✅ **Intelligent Query Processing**: Detects explicit section references, procedural intent, and topic keywords
-   ✅ **4-Stage Retrieval**: Document routing → Chapter search → Section search → Subsection search
-   ✅ **SOP Block Retrieval**: Stage-aware search for procedural guidance (FIR, Medical Examination, etc.)
-   ✅ **Citation Support**: Generates proper legal citations with source labels (📘 SOP, ⚖️ BNSS, 📕 BNS)
-   ✅ **LLM Integration**: Google Gemini with procedural prompts for victim-centric responses

## Supported Documents

### Legal Acts

-   Bharatiya Nyaya Sanhita (BNS) 2023
-   Bharatiya Nagarik Suraksha Sanhita (BNSS) 2023
-   Bharatiya Sakshya Adhiniyam (BSA) 2023

### Standard Operating Procedures (SOPs)

-   MHA/BPR&D SOP for Investigation and Prosecution of Rape against Women (29 procedural blocks)

**Procedural Coverage**: FIR filing, medical examination, statement recording, evidence collection, investigation, victim rights, police duties, and rehabilitation

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
   ↓ detect procedural intent + extract hints (section numbers, topics)
   ↓
   ├─→ Procedural Query Path (NEW - Tier 1)
   │      ↓ detect case type (rape/assault) + stages (FIR/medical/etc.)
   │   SOP Block Level (Procedural guidance)
   │      ↓ retrieve stage-specific blocks with time limits
   │   Document/Section Level (Supporting legal provisions)
   │      ↓ retrieve relevant BNSS/BNS sections
   │   LLM Answer Generation (Gemini - Procedural Prompt)
   │      ↓ generate step-by-step victim-centric guidance
   │   Final Answer: 🚨 Immediate Steps + 👮 Police Duties + ⚖️ Legal Rights
   │
   └─→ Traditional Legal Query Path
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

-   **Total Documents**: 5 (BNS, BNSS, BSA + 2 SOP documents)
-   **Total Chapters**: 55
-   **Total Sections**: 882
-   **Total Subsections**: 3,112
-   **Total SOP Blocks**: 29 (procedural guidance blocks)
-   **Embedding Dimension**: 384 (all-MiniLM-L6-v2)
-   **SOP Support**: ✅ Enabled

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

## SOP (Standard Operating Procedure) Support

### Procedural Query Detection

The system automatically detects victim-centric procedural queries and provides actionable step-by-step guidance:

**Detected Patterns**:

-   "What can a woman do if..."
-   "How to file FIR..."
-   "What are my rights as a victim..."
-   "What should police do when..."
-   Keywords: assault, rape, victim, survivor, FIR, medical examination

**Case Type Detection**: rape, sexual_assault, POCSO

**Procedural Stages** (13 stages):

1. `PRE_FIR` - Actions before filing FIR
2. `FIR` - FIR filing process (⏱️ 72 hours)
3. `STATEMENT_RECORDING` - Statement recording procedures
4. `MEDICAL_EXAMINATION` - Medical examination (⏱️ 24 hours)
5. `EVIDENCE_COLLECTION` - Evidence collection procedures
6. `INVESTIGATION` - Investigation process
7. `ARREST` - Arrest procedures
8. `CHARGE_SHEET` - Charge sheet filing
9. `TRIAL` - Trial procedures
10. `APPEAL` - Appeal procedures
11. `COMPENSATION` - Victim compensation
12. `VICTIM_RIGHTS` - Victim rights and entitlements
13. `POLICE_DUTIES` - Police obligations

### SOP Block Structure

Each SOP block contains:

-   **Title**: Brief description (e.g., "FIR", "Medical examination of victim")
-   **Procedural Stage**: Which stage it applies to
-   **Stakeholders**: Who it applies to (victim, police, IO, magistrate, doctor)
-   **Action Type**: duty, right, timeline, procedure, escalation, guideline
-   **Time Limit**: Deadlines (e.g., "24 hours", "72 hours", "immediately")
-   **Legal References**: Cited BNSS/BNS sections
-   **Priority**: Importance weighting for retrieval

### Procedural Answer Format

When a procedural query is detected, the LLM generates victim-centric guidance in this format:

```
🚨 Immediate Steps
  1. Seek safety and medical attention
  2. Preserve evidence
  3. Contact police

👮 Police Duties
  • Record FIR promptly (within 72 hours)
  • Arrange medical examination (within 24 hours)
  • Record statement at victim's home
  • Provide rehabilitation support

⚖️ Legal Rights
  • Right to lodge FIR at any police station
  • Right to free copy of FIR
  • Right to medical examination by lady doctor
  • Right to compensation

⏱️ Important Time Limits
  • Medical examination: 24 hours
  • FIR recording: 72 hours
  • Statement recording: Promptly

🚩 If Police Refuse
  • Contact senior officer
  • Approach Magistrate
  • File complaint with Human Rights Commission
```

### Source Labels

Results are labeled by source type:

-   📘 **SOP** - MHA/BPR&D procedural guidance
-   ⚖️ **BNSS** - Bharatiya Nagarik Suraksha Sanhita (procedural law)
-   📕 **BNS** - Bharatiya Nyaya Sanhita (penal law)
-   📖 **BSA** - Bharatiya Sakshya Adhiniyam (evidence law)

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

# Legal procedural queries
python cli.py query "What is the procedure for arrest?"
python cli.py query "How is evidence recorded?"

# ✨ NEW: Victim-centric procedural queries (SOP-backed)
python cli.py query "What can a woman do if she is assaulted?"
python cli.py query "How can a rape survivor fight back legally?"
python cli.py query "How to file FIR for rape case?"
python cli.py query "What are my rights as a sexual assault victim?"
python cli.py query "What is the medical examination process for rape victims?"
python cli.py query "What should police do when I report assault?"

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
    ├── models.py         # Data models (legal + SOP)
    ├── pdf_parser.py     # Legal document PDF parser
    ├── sop_parser.py     # SOP procedural block parser (NEW)
    ├── embedder.py       # Hierarchical embedding generator (legal + SOP)
    ├── vector_store.py   # Multi-level FAISS indices (legal + SOP blocks)
    └── retriever.py      # Retrieval pipeline with procedural intent detection
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
