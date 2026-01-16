Below is a **revised, implementation-ready refinement plan** that focuses **only on Tier-1**, i.e. integrating **one authoritative Police SOP** into your _existing_ RAG **without breaking or overcomplicating it**.

I’m aligning this **directly with your current architecture** (hierarchical parsing, BM25+FAISS, CLI, Gemini) and fixing the exact failure you observed in the sample output.

---

# 🎯 Goal of Tier-1 Refinement

After this refinement, your system **must be able to**:

> Answer questions like
> **“What can a woman do if she is assaulted?”**
> with **procedural, step-wise, victim-centric guidance**, instead of dumping random legal definitions.

We are **NOT** adding new models, new vector DBs, or a full rewrite.

---

# 🧩 Tier-1 Scope (STRICT)

### ✅ Documents involved

You will now have **4 documents only**:

| Type                     | Status            |
| ------------------------ | ----------------- |
| BNS 2023                 | already indexed   |
| BNSS 2023                | already indexed   |
| BSA 2023                 | already indexed   |
| **MHA/BPR&D SOP (Rape)** | **NEW – add now** |

📄 File:

```
./documents/SOP for Investigation and Prosecution of Rape against Women - Final submitted (Revised) to JS WS MHA.pdf
```

---

# 🧠 Core Problem We Are Fixing

### Current behavior

Your retriever answers:

-   _“What is assault?”_
-   _“What definitions exist?”_

### Required behavior

Your retriever must answer:

-   _“What happens first?”_
-   _“What police must do?”_
-   _“What can the victim demand?”_
-   _“What if police fail?”_

👉 This **cannot** be solved by embeddings alone.
👉 It requires **procedural structuring**.

---

# 🛠️ Revised Tier-1 Refinement Plan (Step-by-Step)

---

## STEP 1 — Treat SOP as a **Procedural Document** (Not a Law)

### ❌ Do NOT parse SOP like BNS/BNSS

No chapters → sections → subsections.

### ✅ Parse SOP into **procedural blocks**

Each block should represent:

-   A **step**
-   A **duty**
-   A **right**
-   A **timeline**
-   A **responsibility**

### Example SOP chunk

```json
{
	"doc_type": "SOP",
	"title": "Registration of FIR in rape cases",
	"text": "Police must register FIR immediately and cannot refuse...",
	"procedural_stage": "FIR",
	"stakeholder": ["police", "victim"],
	"action_type": "duty",
	"case_type": "rape",
	"source": "MHA/BPR&D SOP"
}
```

📌 **This is the single most important design change.**

---

## STEP 2 — Add a **Procedural Stage Taxonomy**

Introduce a **shared stage vocabulary** used by both laws and SOP.

```python
STAGES = [
  "pre_fir",
  "fir",
  "investigation",
  "medical_examination",
  "charge_sheet",
  "trial",
  "appeal",
  "compensation"
]
```

Now map:

| Document           | Mapping             |
| ------------------ | ------------------- |
| BNSS §183          | investigation       |
| BNSS §184          | medical_examination |
| SOP FIR rules      | fir                 |
| SOP evidence rules | investigation       |

---

## STEP 3 — Metadata Overlay (No Re-Embedding Required)

You **do not need to re-embed existing Acts**.

Instead:

-   Add metadata only to SOP chunks
-   Light metadata augmentation for BNSS sections (optional, incremental)

### Minimum SOP metadata

```json
{
	"procedural_stage": "investigation",
	"stakeholder": "victim",
	"case_type": "rape",
	"priority": 1
}
```

Later you can backfill BNSS metadata gradually.

---

## STEP 4 — Retrieval Rule Change (CRITICAL FIX)

### ❌ Current retrieval logic

```
Top-k most similar sections globally
```

### ✅ Tier-1 retrieval logic

```
IF query intent = procedural AND case_type = rape:
    Retrieve SOP chunks FIRST
    Then retrieve BNSS sections
    Then retrieve BNS definitions (optional)
```

### Practical rule

```python
if intent == "procedural" and case_type == "rape":
    sop_hits = search_sop(top_k=5)
    bnss_hits = search_bnss(stage=detected_stage, top_k=3)
```

This guarantees SOP dominance **without deleting law relevance**.

---

## STEP 5 — Introduce a Lightweight **Stage Detector**

No ML needed. Regex + keywords are enough.

### Example mapping

```python
if "assault" or "rape" and ("what can" or "how"):
    intent = "procedural"
    stage = "pre_fir"
```

This is what your system **currently lacks**.

---

## STEP 6 — Change LLM Role (MANDATORY)

### ❌ Old LLM role

> “Explain these legal extracts”

### ✅ New LLM role

> “Compose a procedural guide for the victim using retrieved material”

### New output contract

```
STAGE: FIR & IMMEDIATE ACTION

1️⃣ What the survivor can do
2️⃣ What police must do (SOP-backed)
3️⃣ Legal support (BNSS section)
4️⃣ If police fail (escalation)
```

### Hard constraint

-   Every step must cite **SOP or law**
-   If SOP covers it → SOP wins
-   If SOP silent → BNSS

---

## STEP 7 — CLI Output Improvement (Minimal but Powerful)

You don’t need UI changes yet.

Just add labels:

```
📘 SOP (MHA/BPR&D)
⚖️ BNSS
📕 BNS
```

Example:

```
📘 SOP: Police must register FIR immediately
⚖️ BNSS §183: Statement recording
```

This instantly improves **trust and clarity**.

---

## STEP 8 — Validation Test (Your New Gold Test)

After Tier-1, this query **must pass**:

```bash
python cli.py query "What can a woman do if she is assaulted?"
```

### Expected answer structure

-   FIR steps
-   Medical examination
-   Police duties
-   Victim rights
-   Escalation if FIR refused

❌ No definitions dump
❌ No accused-centric sections
❌ No mental illness provisions

---

# 🧪 What You Should NOT Do in Tier-1

🚫 Don’t add more SOPs
🚫 Don’t add state schemes yet
🚫 Don’t re-embed all Acts
🚫 Don’t tune BM25 weights yet

---

# 📌 Tier-1 Success Criteria

You know Tier-1 is successful if:

✔ SOP text appears in answers
✔ Answers are step-based
✔ Output changes meaningfully from your sample
✔ Same architecture still works for murder/theft (falls back to BNSS)

---

# 🏁 Final Summary

**Tier-1 refinement = procedural intelligence, not more data.**

You are:

-   Keeping your hierarchy
-   Keeping hybrid search
-   Adding ONE SOP
-   Adding ONE new dimension: _procedure_

This is the **correct next step**.
