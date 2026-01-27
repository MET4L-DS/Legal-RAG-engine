# Span-Based Attribution (answer_units) - API Documentation

## Overview

**Feature Version:** 2.1 (Extension to Citation API v2.0)

The `answer_units` field provides **span-based attribution** with verbatim/derived classification. This ensures legally defensible citations where users can verify every highlighted claim.

## Core Principle

> **Only text that is directly grounded in source spans may be highlighted.**
> Synthesized guidance may list supporting sources but must NOT highlight text.

This eliminates "fake citations" where the LLM synthesizes guidance but incorrectly attributes it to a specific source.

---

## Schema Definitions

### SourceSpan

Represents an exact location within a source document.

```typescript
interface SourceSpan {
	doc_id: string; // Document identifier, e.g., "GENERAL_SOP_BPRD"
	section_id: string; // Section identifier, e.g., "GSOP_057"
	start_char: number; // Absolute character offset within section (0-indexed)
	end_char: number; // Exclusive end offset
	quote: string; // Exact text slice (for verification)
}
```

### AnswerUnit

Represents a single sentence/unit in the answer with attribution metadata.

```typescript
interface AnswerUnit {
	id: string; // Unique identifier: "S1", "S2", etc.
	text: string; // The sentence text as it appears in answer
	kind: "verbatim" | "derived"; // CRITICAL: determines if clickable/highlightable
	source_spans: SourceSpan[]; // Only populated for verbatim units
	supporting_sources: string[]; // Source IDs (primarily for derived units)
}
```

### AnswerUnitsResponse

```typescript
interface AnswerUnitsResponse {
	units: AnswerUnit[];
}
```

---

## API Response Format

### Full Response Example

```json
{
  "answer": "File FIR immediately. Preserve evidence safely.",
  "citations": [...],
  "sentence_citations": [...],
  "answer_units": {
    "units": [
      {
        "id": "S1",
        "text": "File FIR immediately.",
        "kind": "verbatim",
        "source_spans": [{
          "doc_id": "GENERAL_SOP_BPRD",
          "section_id": "GSOP_004",
          "start_char": 42,
          "end_char": 62,
          "quote": "File FIR immediately"
        }],
        "supporting_sources": []
      },
      {
        "id": "S2",
        "text": "Preserve evidence safely.",
        "kind": "derived",
        "source_spans": [],
        "supporting_sources": ["GSOP_004", "GSOP_057"]
      }
    ]
  }
}
```

---

## Frontend Clickability Rules

| Unit Kind | Clickable | Can Highlight Source |
| --------- | --------- | -------------------- |
| verbatim  | ✅ Yes    | ✅ Yes (exact span)  |
| derived   | ❌ No     | ❌ No                |

**Key Rule:** NEVER make a derived unit clickable. Derived text is synthesized guidance that cannot be traced to an exact source location.

---

## Frontend Implementation

### React Component Example

```tsx
import React from "react";

interface SourceSpan {
	doc_id: string;
	section_id: string;
	start_char: number;
	end_char: number;
	quote: string;
}

interface AnswerUnit {
	id: string;
	text: string;
	kind: "verbatim" | "derived";
	source_spans: SourceSpan[];
	supporting_sources: string[];
}

interface Props {
	units: AnswerUnit[];
	onSpanClick: (span: SourceSpan) => void;
}

const AnswerWithUnits: React.FC<Props> = ({ units, onSpanClick }) => {
	return (
		<div className="answer-container">
			{units.map((unit) => (
				<span
					key={unit.id}
					data-unit-id={unit.id}
					data-kind={unit.kind}
					className={
						unit.kind === "verbatim"
							? "unit-verbatim"
							: "unit-derived"
					}
					onClick={
						unit.kind === "verbatim" && unit.source_spans.length > 0
							? () => onSpanClick(unit.source_spans[0])
							: undefined
					}
				>
					{unit.text}
					{unit.kind === "verbatim" && (
						<sup
							className="citation-indicator"
							title="Click to view source"
						>
							🔗
						</sup>
					)}
					{unit.kind === "derived" && (
						<sup
							className="derived-indicator"
							title="Synthesized guidance - not verbatim"
						>
							ℹ️
						</sup>
					)}{" "}
				</span>
			))}
		</div>
	);
};

export default AnswerWithUnits;
```

### CSS Styling

```css
.unit-verbatim {
	cursor: pointer;
	border-bottom: 1px dotted #3b82f6;
	transition: background-color 0.15s ease;
}

.unit-verbatim:hover {
	background-color: #eff6ff;
}

.unit-derived {
	cursor: default;
	color: #4b5563;
}

.citation-indicator {
	font-size: 0.7em;
	vertical-align: super;
	margin-left: 2px;
	color: #3b82f6;
}

.derived-indicator {
	font-size: 0.7em;
	vertical-align: super;
	margin-left: 2px;
	color: #9ca3af;
}
```

### Fetching Source with Highlight

```typescript
const fetchSourceWithHighlight = async (span: SourceSpan) => {
	const response = await fetch("/rag/source", {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({
			source_type: mapDocIdToSourceType(span.doc_id),
			source_id: span.section_id,
			highlight_snippet: span.quote, // For offset calculation
		}),
	});

	const data = await response.json();

	// Use the span's character offsets for precise highlighting
	highlightInViewer(data.content, span.start_char, span.end_char);
};

const mapDocIdToSourceType = (doc_id: string): string => {
	const mapping: Record<string, string> = {
		GENERAL_SOP_BPRD: "general_sop",
		BNSS_2023: "bnss",
		BNS_2023: "bns",
		// ... other mappings
	};
	return mapping[doc_id] || "unknown";
};
```

---

## How Span Resolution Works

### Backend Pipeline

1. **LLM generates answer_units**: The LLM is prompted to classify each sentence as `verbatim` (with exact quote) or `derived`

2. **Span resolution (deterministic)**: For each verbatim unit, the backend:
    - Searches retrieved chunks for the exact `quote` text
    - If found: Calculates absolute character offsets (`start_char`, `end_char`)
    - If NOT found: **Downgrades** the unit to `derived` (no fake citations)

3. **Response assembly**: Units are returned with resolved spans

### Trust Model

| Scenario                                        | Result                                              |
| ----------------------------------------------- | --------------------------------------------------- |
| LLM correctly marks verbatim, quote found       | ✅ Clickable with highlight                         |
| LLM correctly marks derived                     | ✅ Shows info icon, not clickable                   |
| LLM incorrectly marks verbatim, quote NOT found | ✅ **Downgraded to derived** (safety net)           |
| LLM hallucinates a quote                        | ✅ **Downgraded to derived** (caught by resolution) |

This ensures the system is **safe by default** - fabricated citations are caught and neutralized.

---

## Comparison with Other Attribution Methods

### Options Comparison

| Feature                  | `answer` (plain) | `sentence_citations` | `answer_units`     |
| ------------------------ | ---------------- | -------------------- | ------------------ |
| Structured               | ❌ No            | ✅ Sentence-level    | ✅ Sentence-level  |
| Verbatim tracking        | ❌ No            | ❌ No                | ✅ Yes             |
| Exact offsets            | ❌ No            | ❌ No                | ✅ Yes             |
| Fake citation protection | ❌ No            | ❌ No                | ✅ Yes (downgrade) |
| Highlight support        | ❌ No            | ⚠️ Keyword-based     | ✅ Exact character |
| Legal defensibility      | ❌ Low           | ⚠️ Medium            | ✅ High            |

### When to Use Each

- **`answer`**: Legacy support, simple display without attribution
- **`sentence_citations`**: When you need basic source references per sentence
- **`answer_units`**: **Recommended** - when citations must be verifiable and legally defensible

---

## Backend Implementation Notes

### Files Involved

- `src/server/answer_units.py` - Core span resolution and models
- `src/server/schemas.py` - API schemas (SourceSpanSchema, AnswerUnitSchema)
- `src/retrieval/rag.py` - LLM prompt integration
- `src/server/adapter.py` - Response processing

### Key Functions

```python
# answer_units.py

def resolve_span(quote: str, chunks: List[ChunkWithOffsets]) -> Optional[SourceSpan]:
    """
    Find exact location of quote in chunks.
    Returns None if not found (triggers downgrade to derived).
    """

def resolve_all_spans(units: List[AnswerUnit], chunks: List[ChunkWithOffsets]) -> List[AnswerUnit]:
    """
    Resolve spans for all units.
    Verbatim units without found spans are downgraded to derived.
    """
```

### Downgrade Logic

```python
# If verbatim quote not found in chunks, downgrade to derived
if unit.kind == "verbatim" and not resolved_spans:
    unit.kind = "derived"
    unit.source_spans = []
    # Move section_id to supporting_sources
```

---

## Error Handling

### API Response when answer_units Generation Fails

If the LLM fails to generate proper answer_units, the system falls back gracefully:

```json
{
  "answer": "File FIR immediately...",
  "citations": [...],
  "sentence_citations": [...],
  "answer_units": null  // Frontend should fall back to sentence_citations
}
```

### Frontend Fallback

```tsx
const renderAnswer = (response: FrontendResponse) => {
	// Prefer answer_units if available
	if (response.answer_units?.units?.length > 0) {
		return <AnswerWithUnits units={response.answer_units.units} />;
	}

	// Fall back to sentence_citations
	if (response.sentence_citations?.length > 0) {
		return (
			<AnswerWithSentenceCitations data={response.sentence_citations} />
		);
	}

	// Last resort: plain answer
	return <p>{response.answer}</p>;
};
```

---

## Testing

### Regression Tests

The following invariants are tested:

1. **Derived units are never clickable**: `kind == "derived"` ⟹ `source_spans == []`
2. **Verbatim without span is downgraded**: If quote not found, becomes derived
3. **Span offsets are valid**: `0 <= start_char < end_char <= content_length`
4. **Quote verification**: `content[start_char:end_char] == quote`

### Test File

See `tests/test_answer_units.py` for comprehensive test coverage.

---

## Summary

The `answer_units` field provides the most rigorous citation system:

- ✅ **Verbatim tracking**: Only exact quotes can be highlighted
- ✅ **Fake citation prevention**: Unverified quotes are downgraded
- ✅ **Exact positioning**: Character-level offsets for precise highlighting
- ✅ **Legal defensibility**: Every highlighted claim is verifiable
- ✅ **Graceful degradation**: Falls back to other methods if needed

**Recommended for all production deployments where citation accuracy matters.**
