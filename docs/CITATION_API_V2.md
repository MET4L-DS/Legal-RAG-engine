# Citation API v2.0 - Structured Citations

## Overview

**API Version: 2.0** (Breaking Change from v1.0)

The citation system has been completely overhauled. Citations are now returned as **structured objects** with explicit `source_type` and `source_id` fields, eliminating the need for frontend parsing.

### Why This Change?

**Problem (v1.0):**

```json
{
	"citations": [
		"General SOP (BPR&D) - SOP ON FITNESS OF SURETIES - FITNESS OF SURETIES Q & A [GENERAL]",
		"BNSS_2023 - Chapter XIII - Section 183"
	]
}
```

- Frontend had to parse strings with regex to extract source type and ID
- General SOP citations had no `GSOP_XXX` ID in the string
- Parsing frequently failed, causing 404s on `/rag/source` calls

**Solution (v2.0):**

```json
{
	"citations": [
		{
			"source_type": "general_sop",
			"source_id": "GSOP_095",
			"display": "General SOP: SOP ON FITNESS OF SURETIES...",
			"context_snippet": "• There must be lawful directions from...",
			"relevance_score": 0.85
		},
		{
			"source_type": "bnss",
			"source_id": "183",
			"display": "BNSS Section 183",
			"context_snippet": "Section 183(1) of BNSS states that any...",
			"relevance_score": 0.92
		}
	]
}
```

---

## StructuredCitation Schema

```typescript
interface StructuredCitation {
	source_type: SourceType; // Required: Type of source
	source_id: string; // Required: Direct ID for /rag/source
	display: string; // Required: Human-readable text for UI
	context_snippet?: string; // Optional: Snippet of used content (max 200 chars)
	relevance_score?: number; // Optional: Retrieval score (0.0 - 1.0)
}

type SourceType =
	| "general_sop" // BPR&D General SOP (GSOP_001, GSOP_095, etc.)
	| "sop" // MHA Rape SOP blocks
	| "bnss" // BNSS sections (Section 183, etc.)
	| "bns" // BNS sections
	| "bsa" // BSA sections
	| "evidence" // Crime Scene Manual blocks
	| "compensation"; // NALSA Compensation blocks
```

---

## Frontend Usage

### 1. Rendering Citation Chips

```tsx
// Each citation can be rendered as a clickable chip
{
	response.citations.map((cit, i) => (
		<CitationChip
			key={i}
			label={cit.display}
			onClick={() => fetchSource(cit.source_type, cit.source_id)}
		/>
	));
}
```

### 2. Fetching Source Content

```typescript
// Direct fetch - NO PARSING NEEDED
const fetchSource = async (citation: StructuredCitation) => {
	const response = await fetch("/rag/source", {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({
			source_type: citation.source_type,
			source_id: citation.source_id,
		}),
	});
	return response.json();
};
```

### 3. Source Highlight (Future Ready)

The `context_snippet` field contains the specific text that was used from the source. This can be used for:

- Showing a preview before fetching full content
- Highlighting the relevant portion when displaying the full source

```typescript
// When showing full source, highlight the snippet
const highlightSource = (fullContent: string, snippet: string) => {
	if (!snippet) return fullContent;
	const idx = fullContent.indexOf(snippet.replace("...", ""));
	if (idx >= 0) {
		// Scroll to and highlight this portion
	}
};
```

---

## API Endpoints

### POST /rag/query

Returns the main response with structured citations.

**Response (v2.0):**

```json
{
  "answer": "As per Section 183 of BNSS...",
  "tier": "tier3",
  "case_type": "theft",
  "stage": "fir_registration",
  "citations": [
    {
      "source_type": "general_sop",
      "source_id": "GSOP_004",
      "display": "General SOP: SOP ON FIR REGISTRATION...",
      "context_snippet": "• Every person has the right to register FIR...",
      "relevance_score": 0.91
    },
    {
      "source_type": "bnss",
      "source_id": "173",
      "display": "BNSS Section 173",
      "context_snippet": "Information in cognizable cases...",
      "relevance_score": 0.88
    }
  ],
  "timeline": [...],
  "confidence": "high",
  "api_version": "2.0"
}
```

### POST /rag/source

Fetch verbatim source content with optional highlighting.

**Request:**

```json
{
	"source_type": "general_sop",
	"source_id": "GSOP_004",
	"highlight_snippet": "• Every person has the right to register FIR..."
}
```

The `highlight_snippet` field is **optional**. Pass the citation's `context_snippet` to get highlight offsets for auto-scrolling.

**Response:**

```json
{
	"source_type": "general_sop",
	"doc_id": "GENERAL_SOP_BPRD",
	"title": "SOP ON FIR REGISTRATION",
	"section_id": "GSOP_004",
	"content": "• Every person has the right to register FIR...",
	"legal_references": ["173", "154"],
	"metadata": {
		"procedural_stage": "fir",
		"stakeholders": ["citizen", "police", "sho"],
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

**Highlight Usage:**

```typescript
// Frontend: Pass context_snippet to get highlight offsets
const fetchSourceWithHighlight = async (citation: StructuredCitation) => {
	const response = await fetch("/rag/source", {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({
			source_type: citation.source_type,
			source_id: citation.source_id,
			highlight_snippet: citation.context_snippet, // Optional: enables highlighting
		}),
	});
	return response.json();
};

// Render with highlights
const renderWithHighlights = (content: string, highlights: HighlightRange[]) => {
	if (!highlights.length) return content;

	const { start, end } = highlights[0];
	return (
		<>
			{content.slice(0, start)}
			<mark className="bg-yellow-200">{content.slice(start, end)}</mark>
			{content.slice(end)}
		</>
	);
};
```

---

## Source ID Formats

| Source Type    | ID Format      | Examples                           |
| -------------- | -------------- | ---------------------------------- |
| `general_sop`  | `GSOP_XXX`     | `GSOP_004`, `GSOP_095`, `GSOP_001` |
| `sop`          | `SOP_RAPE_XXX` | `SOP_RAPE_001`, `SOP_RAPE_012`     |
| `bnss`         | Section number | `183`, `173`, `244`                |
| `bns`          | Section number | `351`, `356`, `103`                |
| `bsa`          | Section number | `147`, `24`, `132`                 |
| `evidence`     | `EVID_XXX`     | `EVID_001`, `EVID_015`             |
| `compensation` | `COMP_XXX`     | `COMP_001`, `COMP_005`             |

---

## Sentence-Level Citation Mapping (NEW)

The API now supports **inline citation dots** by mapping each answer sentence to its supporting sources. This enables Wikipedia-style sentence-level references.

### Response Format

The `sentence_citations` field is included in the `/rag/query` response:

```json
{
  "answer": "File FIR immediately. Police must act within 24 hours. You can approach any station.",
  "citations": [...],
  "sentence_citations": {
    "sentences": [
      {"sid": "S1", "text": "File FIR immediately."},
      {"sid": "S2", "text": "Police must act within 24 hours."},
      {"sid": "S3", "text": "You can approach any station."}
    ],
    "mapping": {
      "S1": ["general_sop:GSOP_004", "bnss:173"],
      "S2": ["general_sop:GSOP_004"],
      "S3": ["bnss:154"]
    }
  }
}
```

### TypeScript Types

```typescript
interface AnswerSentence {
	sid: string; // "S1", "S2", etc.
	text: string; // The sentence text
}

interface SentenceCitations {
	sentences: AnswerSentence[];
	mapping: Record<string, string[]>; // sid → ["source_type:source_id", ...]
}

interface FrontendResponse {
	// ... existing fields
	sentence_citations?: SentenceCitations; // Optional, may be null
}
```

### Frontend Usage

```tsx
// Render answer with inline citation dots
const renderAnswerWithCitations = (response: FrontendResponse) => {
	if (!response.sentence_citations) {
		return <p>{response.answer}</p>;
	}

	const { sentences, mapping } = response.sentence_citations;

	return (
		<div>
			{sentences.map((sent) => (
				<span key={sent.sid} data-sid={sent.sid}>
					{sent.text}
					{mapping[sent.sid]?.length > 0 && (
						<sup className="citation-dots">
							{mapping[sent.sid].map((key, i) => (
								<CitationDot
									key={key}
									citationKey={key}
									onClick={() => scrollToCitation(key)}
								/>
							))}
						</sup>
					)}{" "}
				</span>
			))}
		</div>
	);
};

// Parse citation key to fetch source
const parseCitationKey = (key: string): { type: string; id: string } => {
	const [type, id] = key.split(":");
	return { type, id };
};

const scrollToCitation = (key: string) => {
	const { type, id } = parseCitationKey(key);
	// Highlight the matching citation chip or scroll to source viewer
};
```

### CSS for Citation Dots

```css
.citation-dots {
	vertical-align: super;
	font-size: 0.7em;
	margin-left: 2px;
}

.citation-dots .citation-dot {
	display: inline-block;
	width: 6px;
	height: 6px;
	border-radius: 50%;
	background-color: #3b82f6;
	margin-right: 2px;
	cursor: pointer;
}

.citation-dots .citation-dot:hover {
	background-color: #1d4ed8;
}
```

### How It Works

1. **Sentence Splitting (Deterministic)**: After LLM generates the answer, it's split into sentences with IDs (S1, S2, S3...). This handles abbreviations, bullet points, and markdown formatting.

2. **Citation Alignment (LLM or Heuristic)**:
    - If LLM is available: A fast model (gemini-2.5-flash-lite) maps sentences to citations using a constrained prompt that only allows mapping to available citations.
    - Fallback: Keyword-based heuristic matching if LLM unavailable.

3. **Response Integration**: The `sentence_citations` field is added to the response without breaking existing fields.

### Notes

- The field is **optional** and may be `null` if:
    - No answer was generated
    - No citations were available
    - Attribution computation failed
- Mapping values use format `"source_type:source_id"` (e.g., `"bnss:183"`)
- A sentence may map to zero, one, or multiple sources
- General statements (like "Here are the steps") may have empty citation lists

---

## Migration Guide

### Before (v1.0)

```typescript
// ❌ Complex parsing required
const parseCitation = (cit: string): SourceRequest | null => {
	const text = cit.toUpperCase();
	let type: SourceRequest["source_type"] | null = null;
	let id = cit;

	const sectionMatch = cit.match(/Section\s+(\d+[A-Za-z]*)/i);
	const codeMatch = cit.match(/([A-Z]+_\d+)/);

	if (text.includes("BNSS")) type = "bnss";
	else if (text.includes("GENERAL SOP")) type = "general_sop";
	// ... more parsing logic

	if (sectionMatch) id = `Section ${sectionMatch[1]}`;
	else if (codeMatch) id = codeMatch[1];
	// ... often fails!

	return { source_type: type, source_id: id };
};

// Usage
const parsed = parseCitation(citation);
if (parsed) {
	fetchSource(parsed.source_type, parsed.source_id);
}
```

### After (v2.0)

```typescript
// ✅ Direct access - no parsing, with highlighting
const fetchSourceForCitation = (citation: StructuredCitation) => {
	return fetch("/rag/source", {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({
			source_type: citation.source_type,
			source_id: citation.source_id,
			highlight_snippet: citation.context_snippet, // Auto-highlight!
		}),
	}).then((r) => r.json());
};

// Usage
fetchSourceForCitation(citation); // Just works with highlighting!
```

---

## TypeScript Types

```typescript
// Copy these types for frontend use

export type SourceType =
	| "general_sop"
	| "sop"
	| "bnss"
	| "bns"
	| "bsa"
	| "evidence"
	| "compensation";

export interface StructuredCitation {
	source_type: SourceType;
	source_id: string;
	display: string;
	context_snippet?: string;
	relevance_score?: number;
}

export interface HighlightRange {
	start: number; // 0-indexed character offset
	end: number; // Exclusive end offset
	reason: string; // Why this is highlighted
}

export interface SourceRequest {
	source_type: SourceType;
	source_id: string;
	highlight_snippet?: string; // Optional: pass context_snippet for auto-highlighting
}

export interface SourceResponse {
	source_type: SourceType;
	doc_id: string;
	title: string;
	section_id: string;
	content: string;
	legal_references: string[];
	highlights: HighlightRange[]; // NEW: highlight offsets for auto-scroll
	metadata: {
		procedural_stage?: string;
		stakeholders?: string[];
		time_limit?: string;
		chapter_no?: string;
		chapter_title?: string;
		[key: string]: unknown;
	};
}

export interface FrontendResponse {
	answer: string | null;
	tier:
		| "tier1"
		| "tier2_evidence"
		| "tier2_compensation"
		| "tier3"
		| "standard";
	case_type: string | null;
	stage: string | null;
	citations: StructuredCitation[]; // ← Changed from string[]
	timeline: TimelineItem[];
	clarification_needed: ClarificationNeeded | null;
	system_notice: SystemNotice | null;
	confidence: "high" | "medium" | "low";
	api_version: string; // "2.0"
	sentence_citations?: SentenceCitations; // NEW: Sentence-level mapping
}

export interface AnswerSentence {
	sid: string; // "S1", "S2", etc.
	text: string;
}

export interface SentenceCitations {
	sentences: AnswerSentence[];
	mapping: Record<string, string[]>; // sid → ["source_type:source_id", ...]
}
```

---

## Error Handling

The `/rag/source` endpoint now returns clearer errors:

```json
// 404 - Source not found
{
  "error": "source_not_found",
  "message": "Source 'GSOP_999' not found in general_sop"
}

// 500 - Server error
{
  "error": "source_fetch_error",
  "message": "Failed to load document"
}
```

---

## Debug Logs

Enable debug logging to trace citation flow:

```
[CITATION] Using 5 pre-built structured citations
[CITATION] ✓ general_sop/GSOP_004: General SOP: SOP ON FIR REGISTRATION...
[CITATION] ✓ bnss/183: BNSS Section 183...
[CITATION] Converted 5 structured citations

[SOURCE] Fetch request: type=general_sop, id='GSOP_004', highlight=yes
[SOURCE] Cache hit for document: GENERAL_SOP_BPRD.json
[SOURCE] Found SOP block: GSOP_004 → 'SOP ON FIR REGISTRATION...'
[SOURCE] ✓ Fetch success: general_sop/GSOP_004 → 1523 chars
[HIGHLIGHT] Exact match at offset 0
[SOURCE] Computed 1 highlight(s) for snippet
```

---

## Summary

| Feature              | v1.0              | v2.0                        |
| -------------------- | ----------------- | --------------------------- |
| Citation format      | `string`          | `StructuredCitation` object |
| Parsing required     | Yes (regex)       | No                          |
| Source ID access     | Parse from string | `citation.source_id`        |
| Context preview      | Not available     | `context_snippet` field     |
| Relevance info       | Not available     | `relevance_score` field     |
| **Highlighting**     | Not available     | `highlights[]` with offsets |
| **Sentence mapping** | Not available     | `sentence_citations` field  |
| API version          | `"1.0"`           | `"2.0"`                     |

**Breaking Change:** The `citations` field is now an array of objects, not strings.

**New Features:**

- Pass `highlight_snippet` to `/rag/source` to get character offsets for auto-scrolling and highlighting.
- `sentence_citations` maps each answer sentence to its supporting sources for inline citation dots.
