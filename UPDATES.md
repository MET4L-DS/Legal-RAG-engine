Perfect. Below is a **clean, execution-ready checklist** of **next steps**, separated clearly into **Backend** and **Frontend**, ordered by **priority**, and written so you (or Copilot) can pick tasks one by one without ambiguity.

This is no longer about architecture — this is about **hardening and product-readiness**.

---

# ✅ BACKEND — NEXT STEPS (FastAPI + RAG)

## 🎯 Backend Goal (Next Phase)

Make the backend:

- **Frontend-safe**
- **Contract-stable**
- **Clarification-aware**
- **Auditable**

No new tiers. No new documents. No rewrites.

---

## 🔴 BACKEND STEP 1 — Add a Response Adapter (HIGH PRIORITY)

### Problem

Backend currently exposes **internal structures** (`tier_info`, `retrieval`, flags).

Frontend should **never depend on these**.

### Action

Add a **response adapter layer** in FastAPI that:

- Keeps internal RAG output unchanged
- Exposes a **flattened, frontend-safe schema**

### Target response shape (final, stable)

```json
{
	"answer": "string",
	"tier": "tier1 | tier2_evidence | tier2_compensation | tier3 | standard",
	"case_type": "string | null",
	"stage": "string | null",
	"citations": ["string"],
	"clarification_needed": null,
	"confidence": "high | medium | low"
}
```

### Notes

- `stage` → pick the **primary detected stage**
- Hide: `retrieval`, `flags`, internal heuristics
- This becomes the **only contract** frontend relies on

✅ This is the **single most important backend fix**.

---

## 🔴 BACKEND STEP 2 — Add Clarification Signals (Minimal, Deterministic)

### Goal

Allow backend to say:

> “I need clarification before proceeding.”

WITHOUT agentic behavior.

### Add logic for **ambiguous terms only**, e.g.:

- assault
- complaint
- violence
- harassment

### Output format

```json
"clarification_needed": {
  "type": "case_type",
  "options": ["sexual_assault", "physical_assault"],
  "reason": "The term 'assault' has different legal procedures"
}
```

### Rules

- Only **one clarification per response**
- No LLM-generated questions
- Options must be **predefined enums**

🚫 Do NOT reprocess previous answers
🚫 Do NOT store conversation memory in backend

---

## 🟡 BACKEND STEP 3 — Add Confidence Scoring (Lightweight)

### Purpose

Help frontend decide:

- When to ask clarification
- When to show “general guidance” disclaimer

### Simple heuristic (example)

- `high` → clear offence + clear tier
- `medium` → general SOP / weak intent
- `low` → ambiguous intent

No ML required. Deterministic rules only.

---

## 🟡 BACKEND STEP 4 — Add Health & Meta Endpoints (If Not Already)

### `/health`

```json
{ "status": "ok", "rag_loaded": true }
```

### `/rag/meta` (optional)

Expose:

- Tier labels
- Supported case types
- Supported stages

Frontend can hardcode initially, but this helps later.

---

## 🟢 BACKEND STEP 5 — Lock the Contract

- Freeze `/rag/query` schema
- Update README
- Add 2–3 API tests comparing CLI vs API output

Once done:

> ❗ Backend logic should be considered **frozen**.
