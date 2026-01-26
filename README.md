# Legal RAG CLI

A hierarchical Retrieval-Augmented Generation (RAG) system for Indian legal documents. This system implements a 4-stage retrieval pipeline (Document → Chapter → Section → Subsection) for accurate legal information retrieval.

## Features

- ✅ **Hierarchical Document Parsing**: Extracts structure from legal PDFs (Chapters, Sections, Subsections)
- ✅ **SOP Document Support** (Tier-1): Parses procedural documents into actionable blocks with stage classification
- ✅ **Evidence Manual Support** (Tier-2): Crime scene investigation standards with failure impact tracking
- ✅ **Compensation Scheme Support** (Tier-2): Victim relief and rehabilitation guidance with conviction-not-required tracking
- ✅ **General SOP Support** (Tier-3): Citizen-centric procedural guidance for all crime types (robbery, theft, assault, murder, cybercrime)
- ✅ **Procedural Query Intelligence**: Detects victim-centric queries and provides step-by-step guidance
- ✅ **Multi-Level Embeddings**: Creates embeddings at all hierarchy levels with type-based weighting
- ✅ **Hybrid Search**: Combines vector similarity (40%) with keyword matching (60% BM25)
- ✅ **Intelligent Query Processing**: Detects explicit section references, procedural intent, evidence/compensation intent, and topic keywords
- ✅ **4-Stage Retrieval**: Document routing → Chapter search → Section search → Subsection search
- ✅ **SOP Block Retrieval**: Stage-aware search for procedural guidance (FIR, Medical Examination, etc.)
- ✅ **Evidence Block Retrieval**: Standards for evidence collection/preservation with contamination warnings
- ✅ **Compensation Block Retrieval**: Victim compensation and rehabilitation information
- ✅ **Citation Support**: Generates proper legal citations with source labels (📘 SOP, 🧪 Evidence Manual, 💰 NALSA Scheme, 📋 General SOP, ⚖️ BNSS, 📕 BNS)
- ✅ **LLM Integration**: Google Gemini with multi-model fallback and tier-specific prompts
- ✅ **FastAPI Server**: REST API with frontend-safe response adapter (v2 stable contract)
- ✅ **Timeline Extraction**: Structured procedural timelines with deadlines from SOP/BNSS metadata
- ✅ **Confidence Scoring**: Deterministic confidence levels (high/medium/low) for frontend decisions
- ✅ **Clarification Signals**: Detects ambiguous queries and requests user clarification
- ✅ **Source Viewer with Highlighting**: Fetch verbatim source text with auto-highlight offsets for citations
- ✅ **Sentence-Level Citation Mapping**: Maps each answer sentence to its supporting sources for inline citation dots (Wikipedia-style)
- ✅ **Meta Endpoint**: Exposes supported tiers, case types, stages for frontend validation

## Supported Documents

### Legal Acts

- Bharatiya Nyaya Sanhita (BNS) 2023
- Bharatiya Nagarik Suraksha Sanhita (BNSS) 2023
- Bharatiya Sakshya Adhiniyam (BSA) 2023

### Standard Operating Procedures (SOPs) - Tier-1

- MHA/BPR&D SOP for Investigation and Prosecution of Rape against Women (29 procedural blocks)

**Procedural Coverage**: FIR filing, medical examination, statement recording, evidence collection, investigation, victim rights, police duties, and rehabilitation

### Evidence & Investigation Standards - Tier-2

- DFS/GoI Crime Scene Investigation Manual (82 evidence blocks)

**Evidence Coverage**: Biological evidence, physical evidence, digital evidence, documentary evidence, crime scene preservation, evidence packaging, contamination prevention, chain of custody

### Victim Compensation & Relief - Tier-2

- NALSA Compensation Scheme for Women Victims/Survivors of Sexual Assault/Other Crimes 2018 (108 compensation blocks)

**Compensation Coverage**: Interim relief, final compensation, medical expenses, rehabilitation support, legal aid, application procedures, eligibility criteria, authority contacts

### General Citizen Procedures - Tier-3

- BPR&D General Standard Operating Procedures (105 procedural blocks)

**Procedural Coverage**: FIR filing, Zero-FIR, complaints, non-cognizable cases, preliminary enquiry, witness examination, medical examination, search & seizure, digital evidence, magistrate complaints, public servant complaints, videography, arrest procedures, property attachment, sureties, proclaimed offenders

**Crime Types Covered**: All crimes (robbery, theft, assault, murder, cybercrime, kidnapping, cheating, forgery, corruption, etc.)

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

### Step 5: Start API Server (Optional)

```bash
# Start the FastAPI server
uvicorn src.server.main:app --host 0.0.0.0 --port 8000

# Or with auto-reload for development
uvicorn src.server.main:app --reload
```

API documentation available at: `http://localhost:8000/docs`

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

## FastAPI Server

The system includes a REST API server for integration with web applications.

### Starting the Server

```bash
# Production
uvicorn src.server.main:app --host 0.0.0.0 --port 8000

# With multiple workers
uvicorn src.server.main:app --host 0.0.0.0 --port 8000 --workers 2

# Development with auto-reload
uvicorn src.server.main:app --reload
```

### API Endpoints

| Endpoint      | Method | Description                                    |
| ------------- | ------ | ---------------------------------------------- |
| `/`           | GET    | API information and available endpoints        |
| `/rag/query`  | POST   | Execute a legal query                          |
| `/rag/source` | POST   | Fetch verbatim source content for citations    |
| `/rag/health` | GET    | Health check and status                        |
| `/rag/stats`  | GET    | Index statistics                               |
| `/rag/meta`   | GET    | Metadata (supported tiers, case types, stages) |
| `/docs`       | GET    | Interactive API documentation (Swagger UI)     |
| `/redoc`      | GET    | Alternative API documentation (ReDoc)          |

### Query Endpoint

**POST `/rag/query`**

Request:

```json
{
	"query": "What is the punishment for murder?",
	"no_llm": false,
	"top_k": 5
}
```

**Response (v1 Stable Contract):**

> ⚠️ **Frontend depends on this schema. Changes require version bump.**

> 📋 **API v2.0**: Citations are now structured objects. See [docs/CITATION_API_V2.md](docs/CITATION_API_V2.md) for migration guide.

```json
{
	"answer": "According to BNS Section 103...",
	"tier": "standard | tier1 | tier2_evidence | tier2_compensation | tier3",
	"case_type": "rape | sexual_assault | robbery | theft | murder | null",
	"stage": "pre_fir | fir | investigation | evidence_collection | null",
	"citations": [
		{
			"source_type": "bns",
			"source_id": "103",
			"display": "BNS Section 103",
			"context_snippet": "Whoever commits murder shall be punished...",
			"relevance_score": 0.92
		},
		{
			"source_type": "bnss",
			"source_id": "184",
			"display": "BNSS Section 184",
			"context_snippet": "The investigation officer shall...",
			"relevance_score": 0.88
		}
	],
	"timeline": [
		{
			"stage": "fir_registration",
			"action": "File FIR / Zero FIR",
			"deadline": "immediately",
			"mandatory": true,
			"is_anchor": true,
			"audience": "victim",
			"legal_basis": ["SOP (MHA/BPR&D) - FIR", "BNSS Section 173"]
		},
		{
			"stage": "medical_examination",
			"action": "Medical examination of victim",
			"deadline": "24 hours",
			"mandatory": true,
			"is_anchor": true,
			"audience": "victim",
			"legal_basis": ["BNSS Section 184"]
		}
	],
	"clarification_needed": null,
	"confidence": "high | medium | low",
	"api_version": "2.0",
	"system_notice": null
}
```

**Timeline Field:**

The `timeline` array contains structured procedural steps extracted from SOP/BNSS metadata (NOT from LLM output):

| Field         | Type     | Description                                          |
| ------------- | -------- | ---------------------------------------------------- |
| `stage`       | string   | Procedural stage (fir, medical_examination)          |
| `action`      | string   | Human-readable action to take                        |
| `deadline`    | string?  | Time limit (24 hours, immediately, etc.)             |
| `mandatory`   | boolean  | Whether this is a legal obligation                   |
| `is_anchor`   | boolean  | Whether this is a mandatory anchor for the case type |
| `audience`    | string   | Target audience: `victim`, `police`, or `court`      |
| `legal_basis` | string[] | BNSS/SOP references                                  |

**Audience Classification:**

The `audience` field classifies WHO the timeline is primarily relevant for:

| Audience | Meaning                                          | Frontend Display                 |
| -------- | ------------------------------------------------ | -------------------------------- |
| `victim` | Direct victim action (FIR, medical exam, etc.)   | **Critical Timelines** (primary) |
| `police` | Police/IO duties (investigation, evidence, etc.) | Later Procedural Steps           |
| `court`  | Court/magistrate procedures (attachment, surety) | Later Procedural Steps           |

**Frontend Display Rules:**

- `is_anchor && audience === "victim"` → **Critical Timelines** (show prominently)
- `mandatory && audience !== "victim"` → **Later Procedural Steps** (visually demote)

**Timeline Anchors System:**

The timeline extraction uses a 2-pass anchor system to ensure legally critical stages are always present:

1. **Pass 1 (Anchor Resolution):** For each case type, mandatory "anchor" stages are identified and extracted first. These are stages that MUST exist for legally correct guidance.

2. **Pass 2 (Secondary Timelines):** Additional timelines from retrieved blocks are added as secondary items.

**Anchor Definitions by Case Type:**

| Case Type        | Mandatory Anchors                                                      |
| ---------------- | ---------------------------------------------------------------------- |
| `rape`           | FIR registration, Medical examination, Statement recording, Protection |
| `sexual_assault` | FIR registration, Medical examination, Statement recording, Protection |
| `robbery`        | FIR registration, Investigation commencement                           |
| `theft`          | FIR registration, Investigation commencement                           |

Items with `is_anchor: true` appear first in the timeline and represent victim-critical stages.

**System Notice (Anchor Failures):**

For Tier-1 crimes (rape, sexual assault, POCSO), if mandatory anchors cannot be resolved from retrieved documents, a `system_notice` field is included:

```json
{
	"system_notice": {
		"type": "ANCHOR_INCOMPLETE",
		"stage": "fir_registration",
		"message": "Some mandatory procedural timelines could not be verified from retrieved documents."
	}
}
```

**Clarification Response (when ambiguous):**

```json
{
	"answer": null,
	"tier": null,
	"case_type": null,
	"stage": null,
	"citations": [],
	"timeline": [],
	"clarification_needed": {
		"type": "case_type",
		"options": ["sexual_assault", "physical_assault"],
		"reason": "The term 'assault' has different legal procedures"
	},
	"confidence": "low",
	"api_version": "1.0"
}
```

### Meta Endpoint

**GET `/rag/meta`**

Returns supported enums for frontend dropdowns/validation:

```json
{
  "tiers": ["tier1", "tier2_evidence", "tier2_compensation", "tier3", "standard"],
  "case_types": ["rape", "sexual_assault", "robbery", "theft", "assault", "murder", ...],
  "stages": ["pre_fir", "fir", "investigation", "medical_examination", ...],
  "confidence_levels": ["high", "medium", "low"]
}
```

### Source Endpoint (Citation Viewer)

**POST `/rag/source`**

Fetch verbatim source content for citations with optional highlighting. **No LLM involved** - returns exact parsed text.

Request:

```json
{
	"source_type": "general_sop | sop | bnss | bns | bsa | evidence | compensation",
	"source_id": "GSOP_004 | Section 183 | EVID_001",
	"highlight_snippet": "optional: pass context_snippet for auto-highlighting"
}
```

Response:

```json
{
	"source_type": "general_sop",
	"doc_id": "GENERAL_SOP_BPRD",
	"title": "SOP ON RECEIPT OF COMPLAINT - FIR Issuance & Jurisdiction",
	"section_id": "GSOP_004",
	"content": "The procedure for issuing an FIR depends on where the offense occurred...",
	"legal_references": ["BNSS Section 154"],
	"metadata": {
		"procedural_stage": "pre_fir",
		"stakeholders": ["citizen", "victim"],
		"action_type": "right",
		"time_limit": "immediately"
	},
	"highlights": [
		{
			"start": 0,
			"end": 245,
			"reason": "Referenced in response"
		}
	]
}
```

**Highlighting:**

Pass `highlight_snippet` (typically from `citation.context_snippet`) to receive character offset ranges in the `highlights` array. This enables:

- Auto-scrolling to the referenced paragraph
- Visual highlighting of the exact text used in the response

```typescript
// Frontend example
const fetchSource = async (citation: StructuredCitation) => {
	const res = await fetch("/rag/source", {
		method: "POST",
		body: JSON.stringify({
			source_type: citation.source_type,
			source_id: citation.source_id,
			highlight_snippet: citation.context_snippet, // ← enables highlighting
		}),
	});
	const { content, highlights } = await res.json();
	// Use highlights[0].start/end to render <mark> and scroll
};
```

**Source Types:**

| Type           | Description                      | Example IDs                  |
| -------------- | -------------------------------- | ---------------------------- |
| `general_sop`  | BPR&D General SOP blocks         | GSOP_001, GSOP_004           |
| `sop`          | MHA Rape SOP blocks              | SOP_001, SOP_MEDICAL         |
| `bnss`         | BNSS sections                    | Section 183, 183, BNSS s.183 |
| `bns`          | BNS sections                     | Section 103, 64              |
| `bsa`          | BSA sections                     | Section 45                   |
| `evidence`     | Crime Scene Manual blocks        | EVID_001                     |
| `compensation` | NALSA Compensation Scheme blocks | COMP_001                     |

**Use Case:** When user clicks a citation chip in the chat, fetch the source via this endpoint and display in a modal/drawer.

### Tier Routing

The API automatically routes queries to the appropriate tier:

| Tier                 | Description               | Example Query                          |
| -------------------- | ------------------------- | -------------------------------------- |
| `standard`           | Traditional legal queries | "What is the punishment for murder?"   |
| `tier1`              | Sexual offence procedures | "What can a rape victim do?"           |
| `tier2_evidence`     | Evidence/investigation    | "What evidence should police collect?" |
| `tier2_compensation` | Victim compensation       | "How to apply for compensation?"       |
| `tier3`              | General crime procedures  | "What do I do in case of robbery?"     |

### Frontend Integration Features

The API is designed for frontend compatibility with these features:

#### Response Adapter

All responses use a **flattened, frontend-safe schema** that hides internal implementation details:

- ✅ Exposes: `answer`, `tier`, `case_type`, `stage`, `citations`, `confidence`
- ❌ Hides: `retrieval`, `tier_info`, internal flags, raw context

#### Confidence Scoring

Deterministic confidence levels based on **anchor-based hardened rules**:

| Confidence | Rule                                                                 | Frontend Action          |
| ---------- | -------------------------------------------------------------------- | ------------------------ |
| `high`     | All anchors resolved + citations present + answer generated          | Show answer directly     |
| `medium`   | Anchors resolved, but weak coverage (missing citations OR no answer) | Show with disclaimer     |
| `low`      | Anchor missing OR clarification needed OR system notice              | Prompt for clarification |

**Anchor-Based Logic:**

- System prioritizes **mandatory timeline anchors** per case type
- Missing anchors (detected via `system_notice`) automatically trigger LOW confidence
- Clarification requests always result in LOW confidence
- HIGH confidence requires complete anchor coverage + supporting evidence (citations)

This makes frontend behavior **predictable and legally safe**.

#### Clarification Signals

For ambiguous queries (e.g., "assault"), the API may request clarification:

```json
{
	"clarification_needed": {
		"type": "case_type",
		"options": ["sexual_assault", "physical_assault"],
		"reason": "The term 'assault' has different legal procedures"
	}
}
```

**Ambiguous terms detected**: assault, complaint, violence, harassment

### Configuration

Set environment variables in `.env`:

```bash
# Required for LLM answers
GEMINI_API_KEY=your_api_key

# Optional server settings
CORS_ORIGINS=["http://localhost:3000"]
INDEX_DIR=./data/indices
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

## Architecture

### Retrieval Pipeline

```
Query Processing
   ↓ detect procedural intent + extract hints (section numbers, topics)
   ↓
   ├─→ Procedural Query Path (Tier-1)
   │      ↓ detect case type (rape/assault) + stages (FIR/medical/etc.)
   │   SOP Block Level (Procedural guidance)
   │      ↓ retrieve stage-specific blocks with time limits
   │   Document/Section Level (Supporting legal provisions)
   │      ↓ retrieve relevant BNSS/BNS sections
   │   LLM Answer Generation (Gemini - Procedural Prompt)
   │      ↓ generate step-by-step victim-centric guidance
   │   Final Answer: 🚨 Immediate Steps + 👮 Police Duties + ⚖️ Legal Rights
   │
   ├─→ Evidence/Investigation Query Path (Tier-2)
   │      ↓ detect evidence/forensic/crime scene keywords
   │   Evidence Manual Block Level (Investigation standards)
   │      ↓ retrieve evidence collection/preservation procedures
   │      ↓ include failure impact warnings (contamination/inadmissibility)
   │   SOP + Legal Provisions (Supporting guidance)
   │      ↓ retrieve SOP evidence blocks + BNSS sections
   │   LLM Answer Generation (Gemini - Evidence Prompt)
   │      ↓ explain proper procedures + consequences of violations
   │   Final Answer: 🔬 Required Evidence + 📋 Procedure + ⚠️ If Not Followed
   │
   ├─→ Compensation/Relief Query Path (Tier-2)
   │      ↓ detect compensation/relief/rehabilitation keywords
   │   Compensation Scheme Block Level (Victim relief)
   │      ↓ retrieve NALSA scheme provisions
   │      ↓ highlight conviction-not-required eligibility
   │   Legal Provisions (Legal basis)
   │      ↓ retrieve BNSS §396 + supporting sections
   │   LLM Answer Generation (Gemini - Compensation Prompt)
   │      ↓ explain eligibility + application process + amounts
   │   Final Answer: ✅ Eligibility + 💰 Types + 📝 How to Apply + 🏛️ Where
   │
   ├─→ General Procedural Query Path (Tier-3)
   │      ↓ detect general crime + procedural intent (NOT sexual offence)
   │   General SOP Block Level (Citizen procedural guidance)
   │      ↓ retrieve crime-specific SOP blocks (FIR, complaint, arrest, etc.)
   │      ↓ include escalation paths and time limits
   │   Legal Provisions (Supporting law)
   │      ↓ retrieve relevant BNSS/BNS sections
   │   LLM Answer Generation (Gemini - General SOP Prompt)
   │      ↓ explain citizen steps + police accountability
   │   Final Answer: 🚨 Immediate Steps + 👮 Police Duties + ⚖️ Legal Basis + 🚩 If Police Do Not Act
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

- **Total Documents**: 10 (BNS, BNSS, BSA + specialized documents)
- **Total Chapters**: 55
- **Total Sections**: 882
- **Total Subsections**: 3,112
- **Total SOP Blocks**: 29 (Tier-1 procedural guidance - rape cases)
- **Total Evidence Blocks**: 82 (Tier-2 investigation standards)
- **Total Compensation Blocks**: 108 (Tier-2 victim relief)
- **Total General SOP Blocks**: 105 (Tier-3 citizen procedural guidance - all crimes)
- **Embedding Dimension**: 384 (all-MiniLM-L6-v2)
- **Tier-1 SOP Support**: ✅ Enabled (Sexual Offences)
- **Tier-2 Evidence Support**: ✅ Enabled (Crime Scene Investigation)
- **Tier-2 Compensation Support**: ✅ Enabled (Victim Relief)
- **Tier-3 General SOP Support**: ✅ Enabled (All Crime Types)

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

- Uses FAISS IndexFlatIP for cosine similarity
- Captures semantic meaning and context
- Handles paraphrased or conceptual queries
- Best for: "What protections exist for assault victims?"

**Keyword Search (60%)**

- Uses BM25Okapi algorithm for term matching
- Captures exact legal terminology and phrases
- Handles specific section references
- Best for: "Section 64 BNSS" or "rape victim medical examination"

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

- "What can a woman do if..."
- "How to file FIR..."
- "What are my rights as a victim..."
- "What should police do when..."
- Keywords: assault, rape, victim, survivor, FIR, medical examination

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

- **Title**: Brief description (e.g., "FIR", "Medical examination of victim")
- **Procedural Stage**: Which stage it applies to
- **Stakeholders**: Who it applies to (victim, police, IO, magistrate, doctor)
- **Action Type**: duty, right, timeline, procedure, escalation, guideline
- **Time Limit**: Deadlines (e.g., "24 hours", "72 hours", "immediately")
- **Legal References**: Cited BNSS/BNS sections
- **Priority**: Importance weighting for retrieval

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

**Tier-1: Sexual Offence Procedures**

- 📘 **SOP** - MHA/BPR&D procedural guidance (rape cases)

**Tier-2: Evidence & Compensation**

- 🧪 **Evidence Manual** - DFS/GoI Crime Scene Investigation standards
- 💰 **NALSA Scheme** - Victim compensation and rehabilitation

**Tier-3: General Citizen Procedures**

- 📋 **General SOP** - BPR&D procedural guidance (all crime types)

**Legal Acts**

- ⚖️ **BNSS** - Bharatiya Nagarik Suraksha Sanhita (procedural law)
- 📕 **BNS** - Bharatiya Nyaya Sanhita (penal law)
- 📗 **BSA** - Bharatiya Sakshya Adhiniyam (evidence law)

## LLM Integration (Google Gemini)

The system uses Google's Gemini API for generating natural language answers:

**Model Fallback Chain** (ordered by availability):

1. `gemini-3-flash` - Newest, highest quality
2. `gemini-2.5-flash-lite` - Good fallback
3. `gemma-3-12b` - High quota fallback (30 RPM, 14.4K RPD)

**Features**:

- **Multi-Model Fallback**: Automatically tries next model on rate limit
- **Automatic Retry**: 2 attempts per model with backoff (5s, 10s)
- **Rate Limit Handling**: Graceful degradation across model tiers
- **Context-Aware**: Receives retrieved sections with full legal text
- **Citation Grounding**: Answers reference specific sections
- **Tier-Specific Prompts**: Different prompts for procedural, evidence, compensation queries

**Prompt Types**:

| Query Type    | Prompt Used           | Output Format                                        |
| ------------- | --------------------- | ---------------------------------------------------- |
| Standard      | `SYSTEM_PROMPT`       | Definition, Procedure, Key Points                    |
| Tier-1 (SOP)  | `PROCEDURAL_PROMPT`   | Immediate Steps, Police Duties, Legal Rights         |
| Tier-2 (Evid) | `EVIDENCE_PROMPT`     | Required Evidence, Procedure, If Not Followed        |
| Tier-2 (Comp) | `COMPENSATION_PROMPT` | Eligibility, Types, How to Apply, Where              |
| Tier-3 (Gen)  | `GENERAL_SOP_PROMPT`  | Immediate Steps, Police Duties, If Police Do Not Act |

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

# Victim-centric procedural queries (Tier-1: SOP-backed)
python cli.py query "What can a woman do if she is assaulted?"
python cli.py query "How can a rape survivor fight back legally?"
python cli.py query "How to file FIR for rape case?"
python cli.py query "What are my rights as a sexual assault victim?"
python cli.py query "What is the medical examination process for rape victims?"
python cli.py query "What should police do when I report assault?"

# Evidence & Investigation queries (Tier-2: Crime Scene Manual)
python cli.py query "What evidence should police collect in a rape case?"
python cli.py query "How should biological evidence be preserved?"
python cli.py query "Police did not preserve the crime scene properly. What does law say?"
python cli.py query "What happens if evidence is contaminated?"
python cli.py query "What is the proper chain of custody for evidence?"

# Compensation & Relief queries (Tier-2: NALSA Scheme)
python cli.py query "Can a rape survivor get compensation even if accused is not convicted?"
python cli.py query "What financial help is available for assault victims?"
python cli.py query "How to apply for victim compensation?"
python cli.py query "What documents are needed for compensation claim?"
python cli.py query "Does victim compensation require conviction of accused?"

# General Procedural queries (Tier-3: General SOP - All Crime Types)
python cli.py query "What do I do in case of a robbery?"
python cli.py query "Police refused FIR for theft. What now?"
python cli.py query "What happens after FIR is registered?"
python cli.py query "How to file complaint for cybercrime?"
python cli.py query "What are my rights when arrested?"
python cli.py query "Police asking for surety. Is this allowed?"
python cli.py query "What is Zero-FIR and when to use it?"

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
├── PLAN.md               # Architecture documentation
├── PLAN_TIER_1.md        # Tier-1 implementation plan
├── PLAN_TIER_2.md        # Tier-2 implementation plan
├── PLAN_TIER_3.md        # Tier-3 implementation plan
├── README.md             # This file
├── documents/            # PDF legal documents
│   ├── BNS.pdf
│   ├── BNSS.pdf
│   └── BSA.pdf
├── data/                 # Generated data (gitignored)
│   ├── parsed/           # Parsed JSON documents
│   └── indices/          # FAISS vector indices
└── src/                  # Modular source code (47 exports)
    ├── __init__.py       # Package exports
    ├── models/           # Data models (6 exports)
    │   ├── legal.py      # LegalDocument, Chapter, Section, Subsection
    │   ├── search.py     # SearchResult
    │   └── __init__.py
    ├── parsers/          # Document parsers (26 exports)
    │   ├── pdf.py        # Legal document PDF parser
    │   ├── sop.py        # SOP procedural block parser (Tier-1 - rape cases)
    │   ├── evidence.py   # Evidence manual parser (Tier-2)
    │   ├── compensation.py  # Compensation scheme parser (Tier-2)
    │   ├── general_sop.py   # General SOP parser (Tier-3 - all crime types)
    │   └── __init__.py
    ├── indexing/         # Embedding & vector storage (8 exports)
    │   ├── entries.py    # Index metadata and entry dataclasses
    │   ├── embedder.py   # Hierarchical embedding generator (all tiers)
    │   ├── store.py      # Multi-level FAISS indices (all tiers)
    │   └── __init__.py
    ├── retrieval/        # Retrieval pipeline (9 exports)
    │   ├── intent.py     # Query intent detection (tier routing)
    │   ├── config.py     # Retrieval configuration and results
    │   ├── retriever.py  # Hierarchical retrieval pipeline
    │   ├── rag.py        # LegalRAG with LLM integration
    │   └── __init__.py
    └── server/           # FastAPI server (REST API)
        ├── main.py       # FastAPI application entry point
        ├── api.py        # API route definitions
        ├── schemas.py    # Request/response Pydantic models
        ├── dependencies.py  # RAG engine singleton loader
        ├── config.py     # Server configuration
        └── __init__.py
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

- Use specific legal terminology when known
- Include act abbreviation (BNS/BNSS/BSA) to narrow scope
- For section lookups, use format: "Section [number] [act]"
- For topic queries, be descriptive: "medical examination of assault victims"

**Examples:**

- ✅ Good: "What is the punishment for murder under BNS?"
- ✅ Good: "Section 184 BNSS medical examination"
- ❌ Less effective: "murder" (too broad)

### Common Issues

**Empty Results:**

- Try broader terms or synonyms
- Remove act abbreviation to search all documents
- Use `--verbose` to see retrieval stages

**Irrelevant Results:**

- Add more specific keywords
- Include section number if known
- Specify the act (BNS/BNSS/BSA)

**LLM Errors:**

- Ensure `GEMINI_API_KEY` is set in `.env`
- Check internet connectivity
- Use `--no-llm` flag to skip LLM and see raw results
- Rate limits: System auto-retries, wait 30-60 seconds

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
