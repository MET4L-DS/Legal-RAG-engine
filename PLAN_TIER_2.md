Excellent — Tier 1 is **cleanly implemented**, and your README shows a **well-disciplined procedural RAG** already .
Tier 2 should **extend depth**, not change direction.

Below is a **precise Tier-2 architecture plan**, designed to **plug into your existing system** with minimal refactor and maximum gain.

---

# 🎯 Tier-2 Objective (Clear & Narrow)

Tier-2 must answer **two new classes of questions** that Tier-1 cannot fully handle:

1. **“Did police collect / preserve evidence correctly?”**
2. **“What compensation, rehabilitation, and financial relief can I get?”**

We will achieve this by adding **two documents only**, each mapped to a **single responsibility**.

---

# 📦 Tier-2 Documents (Confirmed)

| Document                                         | Role                            |
| ------------------------------------------------ | ------------------------------- |
| **Crime Scene Investigation Manual (DFS / GoI)** | Evidence & forensic correctness |
| **NALSA Compensation Scheme (2018)**             | Victim relief & rehabilitation  |

📂 Files:

```text
./documents/crime scene manual full_organized.pdf
./documents/NALSA Compensation Scheme for Women Victims Survivors of Sexual Assault other Crimes – 2018.pdf
```

---

# 🧠 Tier-2 Design Principles (Do NOT violate)

1. ❌ Do NOT mix these into SOP blocks
2. ❌ Do NOT treat them like BNS/BNSS
3. ❌ Do NOT make them mandatory for every query

✔ They are **conditional depth layers**, triggered only when relevant.

---

# 🧩 Tier-2 Architecture Overview

```
User Query
   ↓
Intent + Stage Detection (existing)
   ↓
IF evidence-related → Evidence Path
IF compensation-related → Compensation Path
   ↓
Specialized Tier-2 Retriever
   ↓
Tier-1 output + Tier-2 augmentation
```

Tier-2 **never replaces** Tier-1 — it **augments it**.

---

# 🟦 PART A — Crime Scene Investigation Manual Integration

## 🎯 Purpose

Enable your RAG to:

-   Audit police conduct
-   Explain correct evidence handling
-   Detect investigative lapses

### Example questions unlocked:

-   “Police didn’t seal the crime scene — is that legal?”
-   “What evidence should be collected in a rape case?”
-   “Can bad evidence handling weaken my case?”

---

## A1️⃣ Parsing Strategy (DO NOT use chapter/section logic)

### ❌ Wrong

-   Chapter → Section → Subsection

### ✅ Correct

Parse into **Operational Evidence Blocks**

Each block should represent **one investigative action**.

### Example block

```json
{
	"doc_type": "EVIDENCE_MANUAL",
	"title": "Securing the crime scene",
	"text": "The first officer must cordon off the area...",
	"procedural_stage": "EVIDENCE_COLLECTION",
	"stakeholder": ["police", "IO"],
	"evidence_type": ["physical", "biological"],
	"action_type": "duty",
	"failure_impact": "contamination",
	"source": "DFS Crime Scene Manual"
}
```

---

## A2️⃣ New Metadata Fields (Tier-2 only)

Add **new dimensions**, don’t overload existing ones:

```json
{
	"evidence_type": ["biological", "digital", "weapon"],
	"failure_impact": "case_weakening",
	"linked_stage": "investigation"
}
```

These allow:

-   Evidence-specific filtering
-   Smarter explanations

---

## A3️⃣ Retrieval Rules (STRICT)

### Trigger conditions

```python
if "evidence" in query
or "crime scene" in query
or "forensic" in query
or SOP returns EVIDENCE_COLLECTION stage:
```

### Retrieval order

```
1️⃣ Crime Scene Manual blocks (top priority)
2️⃣ SOP evidence blocks
3️⃣ BNSS procedural backing
```

🚫 Do NOT return evidence manual blocks for:

-   Punishment queries
-   Definitions
-   Appeals

---

## A4️⃣ Output Contract (Evidence Mode)

When evidence manual is used, **force this section**:

```
🧪 Evidence & Investigation Standards
✔ What police should have done
⚠ What happens if this is not followed
📘 Source: Crime Scene Investigation Manual
```

This keeps explanations grounded and non-speculative.

---

# 🟩 PART B — Victim Compensation Scheme (NALSA) Integration

## 🎯 Purpose

Answer:

-   “Can I get money help?”
-   “Even if accused is not convicted?”
-   “Who do I apply to?”

---

## B1️⃣ Parsing Strategy (Policy-Driven Blocks)

Do **NOT** chunk by paragraphs blindly.

Chunk by **entitlements**.

### Example block

```json
{
	"doc_type": "COMPENSATION_SCHEME",
	"title": "Interim compensation for rape survivors",
	"text": "Survivors are entitled to interim compensation...",
	"procedural_stage": "COMPENSATION",
	"stakeholder": "victim",
	"eligibility": ["rape", "sexual assault"],
	"authority": "DLSA/SLSA",
	"source": "NALSA 2018 Scheme"
}
```

---

## B2️⃣ Metadata That Matters

```json
{
	"crime_covered": ["rape", "sexual assault"],
	"authority": "Legal Services Authority",
	"application_stage": ["post_fir", "post_trial"],
	"payment_type": "interim/final"
}
```

---

## B3️⃣ Retrieval Rules

### Trigger conditions

```python
if "compensation" in query
or "financial help"
or "rehabilitation"
or stage == COMPENSATION:
```

### Retrieval order

```
1️⃣ NALSA scheme blocks
2️⃣ BNSS §396 (legal basis)
```

---

## B4️⃣ Output Contract (Compensation Mode)

```
💰 Compensation & Rehabilitation

• Who can apply
• When to apply
• Authority to approach
• Whether conviction is required

📘 Source: NALSA Compensation Scheme
⚖️ Legal Basis: BNSS §396
```

This is **critical for victim trust**.

---

# 🔄 How Tier-2 Integrates with Tier-1 (No Conflict)

| Tier   | Responsibility                                       |
| ------ | ---------------------------------------------------- |
| Tier-1 | “What should happen procedurally?”                   |
| Tier-2 | “Was it done correctly?” / “What extra help exists?” |

Tier-2 **never runs alone**.

---

# 🧠 Changes Required in Codebase (Minimal)

### 1️⃣ New parsers

```text
src/evidence_manual_parser.py
src/compensation_parser.py
```

### 2️⃣ Extend vector_store namespaces

```python
evidence_index
compensation_index
```

### 3️⃣ Small change in retriever.py

```python
if evidence_intent:
    include evidence retriever
if compensation_intent:
    include compensation retriever
```

🚫 No change to:

-   BM25 weights
-   Existing SOP logic
-   Legal hierarchy

---

# 🧪 Tier-2 Validation Queries (Must Pass)

```bash
python cli.py query "Police did not preserve the crime scene properly. What does law say?"
python cli.py query "What evidence should police collect in a rape case?"
python cli.py query "Can a rape survivor get compensation even if accused is not convicted?"
```

Expected:

-   Crime Scene Manual cited
-   NALSA cited
-   BNSS only as support, not primary

---

# 🏁 Tier-2 Success Criteria

✔ Evidence handling questions become answerable
✔ Compensation questions are concrete, not vague
✔ No noise in non-procedural queries
✔ Tier-1 behavior remains unchanged

---

# 🔚 Final Summary

**Tier-2 is about accountability + relief**, not law expansion.

You are building:

-   A **procedural watchdog**
-   A **victim support navigator**

This plan keeps your system:

-   Modular
-   Explainable
-   Scalable
