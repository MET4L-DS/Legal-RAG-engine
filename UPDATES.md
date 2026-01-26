## 2️⃣ Sentence-level → source mapping (the right way)

> “I want the source used to correctly map with the text or sentence of the answer with internal links.
> Will that require significant backend changes?”

### Short answer

❌ **No major backend rewrite required**
✅ **One additional data structure + light LLM constraint**

You already have **80% of what’s needed**.

---

## 🔑 Core idea: make the answer _cite-aware at sentence level_

Right now your pipeline looks like this:

```
Retrieved sources → LLM → Answer text
                     ↓
                  Citations (list)
```

What we want is:

```
Retrieved sources → LLM → Answer with sentence IDs
                     ↓
            Sentence ↔ citation mapping
```

### The missing piece

You need a **Sentence Attribution Map**.

---

## 🧠 Backend change (minimal, additive)

### Step A — Assign sentence IDs after generation

After the LLM produces the final answer:

```text
File FIR at nearest police station.
The police must register the FIR immediately.
If police refuse, approach the SP.
```

You **post-process** it into:

```json
[
	{ "sid": "S1", "text": "File FIR at nearest police station." },
	{ "sid": "S2", "text": "The police must register the FIR immediately." },
	{ "sid": "S3", "text": "If police refuse, approach the SP." }
]
```

This is deterministic. No LLM needed.

---

### Step B — Ask the LLM for citation alignment (NOT regeneration)

You already pass retrieved context to the LLM.
Now add **one extra instruction**:

> “For each sentence ID, list which sources support it.
> Use only the provided citations.
> Do not invent sources.”

Expected output (machine-readable):

```json
{
	"S1": ["GENERAL_SOP_BPRD:GSOP_004"],
	"S2": ["BNSS:Section 154"],
	"S3": ["GENERAL_SOP_BPRD:GSOP_057"]
}
```

⚠️ This is **not free-form generation** — it’s a constrained mapping task.

This keeps hallucination risk extremely low.

---

### Step C — Extend API response (non-breaking)

Add **one optional field**:

```json
"sentence_citations": {
  "S1": ["general_sop:GSOP_004"],
  "S2": ["bnss:154"],
  "S3": ["general_sop:GSOP_057"]
}
```

Everything else stays the same.

Your existing `/rag/source` endpoint already supports fetching + highlighting.

---

## 🧩 Frontend implementation (you’re already 70% there)

### How it works in UI

1. Render answer sentences as `<span data-sid="S2">`
2. On hover or click:
    - show a small citation icon

3. On click:
    - open Source Side Panel
    - call `/rag/source` using the mapped source IDs

4. Auto-scroll + highlight (already implemented)

### UX pattern (recommended)

- 🔗 **Inline citation dot** (like Wikipedia / Perplexity)
- 🖱️ Clicking sentence opens source
- 📌 Side panel stays persistent
- 🔁 Cached per session (you already do this)

Your current accordion + cache system is **perfectly compatible** with this.

---

## 🔍 Highlight precision (important detail)

Instead of highlighting the entire SOP block:

- Pass **the exact sentence text** as `highlight_snippet`
- Backend already returns `start/end` offsets
- Result: **precise yellow highlight** for _that sentence only_

This directly solves the “highlight is not that useful” problem.
