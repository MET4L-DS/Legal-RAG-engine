# Next Steps Checklist (Backend → Frontend)

> **Purpose**
> This document defines the **exact implementation steps** to take next, in the **correct order**, assuming the **backend is implemented first** and the frontend follows.
>
> It is written to be **explicit, linear, and Copilot-friendly**. Each step is small, verifiable, and should be completed fully before moving to the next.

---

## PART A — BACKEND NEXT STEPS (FastAPI + RAG)

### 🎯 Backend Objective (This Phase)

- Make legal **timelines first-class, structured data**
- Freeze a **stable API contract (v1)**
- Remove remaining ambiguity between internal RAG logic and frontend needs

Do **NOT** add new tiers, documents, or agentic behavior.

---

## A1. Define a Timeline Data Model (REQUIRED)

### Action

Create a **formal timeline schema** in the backend.

### Example (Python / Pydantic)

```python
class TimelineItem(BaseModel):
    stage: str                    # e.g. "fir", "medical_examination"
    action: str                   # human-readable action
    deadline: str | None          # e.g. "24 hours", "immediately"
    mandatory: bool               # legal obligation or not
    legal_basis: list[str]        # BNSS / SOP references
```

### Rules

- Timeline items must come from **SOP / BNSS metadata**, not the LLM
- No free-text inference
- No frontend parsing required later

---

## A2. Extract Timelines During Retrieval (CRITICAL)

### Action

While assembling the RAG response:

- Inspect retrieved SOP / General SOP / Evidence blocks
- If a block contains:
    - explicit time limits
    - words like `within`, `immediately`, `without delay`, `hours`, `days`

- Convert that information into `TimelineItem` objects

### Rules

- Do NOT rely on LLM-generated text
- Prefer SOP metadata if available
- If no timeline exists, return an empty list (not null)

---

## A3. Attach Timeline to `/rag/query` Response

### Action

Extend the **frontend-safe response adapter** to include timelines.

### Final Response Shape (v1)

```json
{
	"answer": "string",
	"tier": "tier1 | tier2_evidence | tier2_compensation | tier3 | standard",
	"case_type": "string | null",
	"stage": "string | null",
	"citations": ["string"],
	"timeline": [
		{
			"stage": "string",
			"action": "string",
			"deadline": "string | null",
			"mandatory": true,
			"legal_basis": ["string"]
		}
	],
	"clarification_needed": null,
	"confidence": "high | medium | low"
}
```

### Rules

- Timeline must be **separate from `answer` text**
- Timeline must be **optional but structured**
- Do NOT embed timeline inside markdown

---

## A4. Freeze the Backend Contract (IMPORTANT)

### Action

Once timeline is added:

- Declare `/rag/query` response as **v1 stable** in README
- Add a note:

    > "Frontend depends on this schema. Changes require version bump."

### Optional

Add:

```json
"api_version": "1.0"
```

---

## A5. Add Minimal Tests for Timeline Integrity

### Action

Add backend tests that assert:

- Timeline is present for cases with known deadlines (rape, FIR, medical exam)
- Timeline is empty for cases without deadlines
- Timeline items always include `stage` and `action`

No frontend involved yet.

---

## A6. (Optional) Add Reason Codes

### Action

Expose a non-UI field:

```json
"reason_codes": ["procedural_intent", "general_sop"]
```

This is for debugging and analytics only.
