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

Fetch verbatim source content. **No changes to this endpoint.**

**Request:**

```json
{
	"source_type": "general_sop",
	"source_id": "GSOP_004"
}
```

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
	}
}
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
// ✅ Direct access - no parsing
const fetchSourceForCitation = (citation: StructuredCitation) => {
	return fetchSource(citation.source_type, citation.source_id);
};

// Usage
fetchSourceForCitation(citation); // Just works!
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

export interface SourceRequest {
	source_type: SourceType;
	source_id: string;
}

export interface SourceResponse {
	source_type: SourceType;
	doc_id: string;
	title: string;
	section_id: string;
	content: string;
	legal_references: string[];
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

[SOURCE] Fetch request: type=general_sop, id='GSOP_004'
[SOURCE] Cache hit for document: GENERAL_SOP_BPRD.json
[SOURCE] Found SOP block: GSOP_004 → 'SOP ON FIR REGISTRATION...'
[SOURCE] ✓ Fetch success: general_sop/GSOP_004 → 1523 chars
```

---

## Summary

| Feature          | v1.0              | v2.0                        |
| ---------------- | ----------------- | --------------------------- |
| Citation format  | `string`          | `StructuredCitation` object |
| Parsing required | Yes (regex)       | No                          |
| Source ID access | Parse from string | `citation.source_id`        |
| Context preview  | Not available     | `context_snippet` field     |
| Relevance info   | Not available     | `relevance_score` field     |
| API version      | `"1.0"`           | `"2.0"`                     |

**Breaking Change:** The `citations` field is now an array of objects, not strings.
