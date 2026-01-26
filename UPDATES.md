### **References & Citations — how should we show them, and how do we query source sections?**

You’re absolutely right about this:

> “We’ll have to set up a system to allow querying the source sections from the backend.”

This is the **correct next problem** to solve.

---

## 4️⃣ First principle (very important)

### ❌ Do NOT dump full legal text into the chat by default

### ❌ Do NOT make the frontend re-search documents

### ❌ Do NOT let the LLM paraphrase source law again

### ✅ Treat citations as **primary sources**, not decorations

The chat answer is an **explanation layer**.
Citations are **authoritative evidence**.

They deserve a **separate interaction model**.

---

## 5️⃣ The correct UX model for citations (recommended)

### 🧠 Think in **three layers**

#### Layer 1 — Inline citation chips (you already have this)

Example:

```
GENERAL_SOP_BPRD – Section GSOP_004
BNSS Section 183
```

These are identifiers, not content.

---

#### Layer 2 — “View Source” expansion (MOST IMPORTANT)

On click:

- Show the **exact source excerpt**
- Verbatim text
- Highlighted relevant paragraph
- Clear source header

Example UI:

```
📋 General SOP (BPR&D)
Section GSOP_004 – Receipt of Complaint

[Exact extracted text here]
```

No LLM involved here.

---

#### Layer 3 — Optional side panel (future polish)

For advanced users:

- Persistent “Sources” panel
- Allows comparing multiple sections
- Useful for lawyers / students

This is optional for v1.

---

## 6️⃣ Backend: what you need to add (small but crucial)

You **do not need a new RAG pipeline**.
You already have the data.

You need **one simple, explicit endpoint**.

---

### ✅ Add a Source-Fetch Endpoint

Example:

```
GET /rag/source
```

Request:

```json
{
	"source_type": "general_sop | sop | bnss | bns | bsa",
	"source_id": "GSOP_004"
}
```

Response:

```json
{
	"source_type": "general_sop",
	"title": "SOP on Receipt of Complaint – FIR Issuance & Jurisdiction",
	"section_id": "GSOP_004",
	"content": "Exact extracted text from SOP...",
	"legal_references": ["BNSS Section 154"],
	"last_updated": "2023"
}
```

### Key rules

- Content must be **verbatim**
- No LLM summarization
- Same parser output you already store
- Read-only endpoint

This makes your system **inspectable and defensible**.

---

## 7️⃣ Frontend: how to wire this cleanly

### Minimal v1 approach (recommended)

1. Citations render as clickable chips
2. On click:
    - Fetch `/rag/source`
    - Open a modal / drawer
    - Display source text with scroll

3. Allow “Copy source” / “Open full section”

That’s it.

No re-querying, no state explosion.

---

## 8️⃣ Why this matters (and why you’re right to ask now)

At this stage, users will ask:

> “Where is this coming from?”

You can now answer:

> “Here is the exact government SOP / section.”

That’s the difference between:

- ❌ “AI legal advice”
- ✅ “AI-assisted legal guidance backed by primary sources”

Very few systems get this right.

---

## 9️⃣ So… what is **next**, concretely?

Assuming everything else is stable (it is), your roadmap should be:

### 🔴 Immediate (v1.1)

- Add `/rag/source` endpoint
- Add citation click → source modal
- Freeze backend again

### 🟡 Short-term polish

- Highlight referenced paragraph
- Copy-to-clipboard
- Source panel UX refinement
