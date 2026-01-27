**Option B (span-based attribution)** is the _correct_ long-term fix, and you can implement it **incrementally** without breaking what you already have.

Below is a **Copilot-friendly, step-by-step guide**, split cleanly into **Backend** and **Frontend**, written so an agent (or future you) can follow it linearly.

I’ll assume:

- FastAPI backend
- Python RAG pipeline
- React / Next.js frontend
- Existing `/rag/query` and `/rag/source` endpoints

---

# ✅ OPTION B — SPAN-BASED ATTRIBUTION

_(Verbatim-safe citation mapping)_

---

# 🧠 Core Principle (put this at the top of your README)

> **Only text that is directly grounded in source spans may be highlighted.**
> Synthesized guidance may list supporting sources but must not highlight text.

Everything below enforces this rule.

---

# BACKEND GUIDE (IMPLEMENT FIRST)

---

## 1️⃣ Change the mental model: “answers are made of units”

Instead of returning:

```json
"answer": "Preserve evidence. File FIR immediately."
```

You will return:

```json
"answer_units": [ ... ]
```

Each unit is **one sentence or bullet**.

---

## 2️⃣ Define the Answer Unit schema (NEW)

Create a dedicated model.

```python
# models/answer_unit.py

class SourceSpan(BaseModel):
    doc_id: str                 # e.g. GENERAL_SOP_BPRD
    section_id: str             # e.g. GSOP_057
    start_char: int             # absolute char offset
    end_char: int               # absolute char offset
    quote: str                  # exact text slice (for safety)

class AnswerUnit(BaseModel):
    id: str                     # e.g. "S1"
    text: str                   # sentence text
    kind: Literal["verbatim", "derived"]
    source_spans: list[SourceSpan] = []
```

---

## 3️⃣ During retrieval: preserve absolute text offsets (CRITICAL)

When chunking documents:

```python
chunk = {
    "doc_id": "GENERAL_SOP_BPRD",
    "section_id": "GSOP_057",
    "text": section_text,
    "start_char": absolute_start,
    "end_char": absolute_end
}
```

✅ These offsets **must refer to the full document**, not the chunk.

---

## 4️⃣ During answer generation: force citation discipline

### Prompt rule (MANDATORY)

Add this to the system prompt:

```
RULES:
- If a sentence is directly supported by a specific passage,
  mark it as VERBATIM and quote the exact source text.
- If a sentence is guidance, summary, or best-practice,
  mark it as DERIVED and DO NOT quote any source.
- Never invent quotations.
```

---

## 5️⃣ LLM output format (machine-readable)

Force JSON:

```json
{
	"answer_units": [
		{
			"id": "S1",
			"text": "Electronic communication should be sent to the SHO’s official email.",
			"kind": "verbatim",
			"quote": "Electronic communication should preferably be to official e-mail address or official mobile number of SHO..."
		},
		{
			"id": "S2",
			"text": "Preserve evidence if it is safe to do so.",
			"kind": "derived"
		}
	]
}
```

⚠️ **No source IDs yet** — just quotes.

---

## 6️⃣ Span resolution step (deterministic, no LLM)

For each `verbatim` unit:

```python
def resolve_span(quote, retrieved_chunks):
    for chunk in retrieved_chunks:
        idx = chunk.text.find(quote)
        if idx != -1:
            return SourceSpan(
                doc_id=chunk.doc_id,
                section_id=chunk.section_id,
                start_char=chunk.start_char + idx,
                end_char=chunk.start_char + idx + len(quote),
                quote=quote
            )
    return None
```

If resolution fails:

- Downgrade unit → `derived`
- Log warning

---

## 7️⃣ Final API response shape (IMPORTANT)

```json
{
	"answer_units": [
		{
			"id": "S1",
			"text": "...",
			"kind": "verbatim",
			"source_spans": [
				{
					"doc_id": "GENERAL_SOP_BPRD",
					"section_id": "GSOP_007",
					"start_char": 412,
					"end_char": 615,
					"quote": "Electronic communication should preferably..."
				}
			]
		},
		{
			"id": "S2",
			"text": "Preserve evidence if it is safe to do so.",
			"kind": "derived",
			"source_spans": []
		}
	]
}
```

---

## 8️⃣ Update `/rag/source` endpoint (small change)

Accept **explicit span requests**:

```json
{
	"doc_id": "GENERAL_SOP_BPRD",
	"section_id": "GSOP_007",
	"start_char": 412,
	"end_char": 615
}
```

Backend:

- Load full document
- Slice `[start_char:end_char]`
- Return exact text + surrounding context (±300 chars)

---

## 9️⃣ Add regression tests (DO NOT SKIP)

```python
def test_no_highlight_for_derived_units():
    for unit in answer_units:
        if unit.kind == "derived":
            assert unit.source_spans == []
```

This prevents **fake citations forever**.

---

# FRONTEND GUIDE

---

## 1️⃣ Render answer units, not raw text

```tsx
answer_units.map((unit) => <AnswerSentence key={unit.id} unit={unit} />);
```

---

## 2️⃣ Clickability rules (VERY IMPORTANT)

| Unit kind | Clickable | Highlight |
| --------- | --------- | --------- |
| verbatim  | ✅ yes    | ✅ exact  |
| derived   | ❌ no     | ❌ none   |

---

## 3️⃣ Sentence component behavior

```tsx
if (unit.kind === "verbatim") {
	renderClickableSentence(unit);
} else {
	renderPlainSentence(unit);
}
```

Add subtle UI:

- 🔗 icon for verbatim
- ℹ️ “Derived guidance” tooltip for derived

---

## 4️⃣ On click → fetch exact span

```ts
POST / rag / source;
{
	(doc_id, section_id, start_char, end_char);
}
```

---

## 5️⃣ Source side panel behavior

- Accordion per document
- Cache fetched spans in session state
- Auto-scroll to `start_char`
- Highlight ONLY `[start_char:end_char]`

No fuzzy matching. No searching.

---

## 6️⃣ Highlight implementation (simple & correct)

```ts
highlightRange(startChar, endChar);
```

Do **not** search by words.
Use absolute offsets only.

---

## 7️⃣ UX copy (important for trust)

For derived sentences:

> “This guidance is derived from verified SOPs but is not quoted verbatim.”

This protects you legally and ethically.

---

# ❌ WHAT NOT TO DO (put this in README)

- ❌ Do not highlight derived text
- ❌ Do not search for keywords in source
- ❌ Do not attach spans without exact quote match
- ❌ Do not force every sentence to have a citation

---

# 🧪 Acceptance Checklist

Before shipping, confirm:

- [ ] Clicking a sentence **always highlights correct text**
- [ ] No highlight exists without a quote match
- [ ] “Preserve evidence” does **not** highlight unrelated SOPs
- [ ] Regression tests pass
- [ ] Side panel never jumps to random locations

---

# 🏁 Final Note

This design:

- Matches **academic citation standards**
- Matches **legal research tools**
- Eliminates misleading UX
- Makes your system _defensible_

You are now building something that **law students, lawyers, and courts could actually trust**.
