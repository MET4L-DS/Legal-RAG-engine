# 🚀 Next Phase: LLM Logic Integration

I’ll give you a **clear, ordered plan** so you don’t accidentally mix concerns.

---

## 🧭 Phase 4: Answer Intelligence Layer (MOST IMPORTANT)

Right now you have:

- ✅ _What to retrieve_
- ❌ _How to answer like a lawyer_

Your next step is to build a **Legal Answer Orchestrator**, not just “pass chunks to LLM”.

---

## 1️⃣ Query Understanding & Classification (Step 4.1)

Before retrieval, classify the **intent of the question**.

### Why this matters

Legal questions behave very differently:

- “What is Section 14 BNS?” ≠
- “What should police do if FIR is online?” ≠
- “Is this offence bailable?”

### Implement a lightweight classifier (rule + LLM)

```python
QUERY_TYPES = [
  "definition",
  "procedure",
  "punishment",
  "bailability",
  "jurisdiction",
  "rights_of_victim",
  "police_duty",
  "court_power",
  "compensation",
  "general_explanation"
]
```

This controls:

- retrieval filters
- answer tone
- citation strictness

⚠️ Do **not** answer yet — only classify.

---

## 2️⃣ Retrieval Orchestration (Step 4.2)

You already have **hybrid retrieval**.
Now add **legal priority logic**.

### Retrieval pipeline (final form)

```text
User Query
   ↓
Intent Classification
   ↓
Hybrid Search (FAISS + BM25)
   ↓
Priority Filtering
   ↓
Parent Expansion
   ↓
Dedup + Ordering
```

### Priority Rules (crucial)

1. **Primary legislation** (BNS / BNSS / BSA)
2. **Schemes** (NALSA)
3. **SOPs**

If SOP conflicts with statute:

- statute wins
- SOP is treated as implementation guidance

---

## 3️⃣ Parent Expansion Logic (Step 4.3)

You already embedded atomically — now **reconstruct hierarchy**.

### Example

If retrieved:

- BNSS Section 8(3)

Auto-include:

- BNSS Section 8 (main heading)

If retrieved:

- Illustration (b)

Auto-include:

- Section rule text

This makes answers:

- complete
- legally safe
- readable

---

## 🧠 Phase 5: Legal Answer Generation (THIS IS WHERE QUALITY COMES FROM)

---

## 4️⃣ Strict Legal Prompt Template (Step 5.1)

You must **lock the LLM into a legal role**.

### Core system instruction (example)

> You are a legal assistant answering strictly based on provided Indian legal sources.
> Do not assume facts.
> Do not generalize beyond the text.
> Always cite sections verbatim when stating law.

### Answer structure (fixed)

```text
Answer:
<Direct response>

Legal Basis:
• Section X, Act – quoted or paraphrased strictly

Procedure / Explanation (if applicable):
<Steps>

Important Notes:
<Conditions / exceptions>

Sources:
• BNS Section X
• BNSS Section Y
```

This eliminates:

- hallucinations
- vague answers
- “AI-sounding” replies

---

## 5️⃣ Citation Binding (Step 5.2)

You already solved **retrieval accuracy**.
Now bind answers to **exact chunks**.

Each answer paragraph should map to:

- `chunk_id`
- `law`
- `section`
- `source_file`

This enables:

- clickable citations
- exact highlight rendering
- auditability (huge for legal tools)

---

## 🖥️ Phase 6: Frontend Contract (Don’t skip this)

---

## 6️⃣ Define the API Contract (Step 6.1)

Before writing UI, freeze the response shape:

```json
{
	"answer": "...",
	"sections": [
		{
			"law": "BNSS",
			"section": "173",
			"text": "...",
			"confidence": 0.92
		}
	],
	"procedural_steps": [],
	"warnings": [],
	"sources": []
}
```

Your frontend should **never parse raw LLM text**.

---

## 7️⃣ Safety & Scope Guardrails (Step 6.2)

Since this is law:

- Add **non-advisory disclaimer logic**
- Block:
    - personalized legal advice
    - predictions of court outcomes

- Reframe as:

    > “As per the law, the procedure is…”

This protects your project if it ever goes public.

---

## 🧪 Phase 7: Lawyer-Grade Testing (Very important)

---

## 8️⃣ Legal Test Set (Step 7.1)

Create **30–50 canonical queries**, like:

- “Is FIR mandatory for cognizable offence?”
- “What compensation is available for rape victims?”
- “Who can testify in court?”

For each:

- expected sections
- expected acts
- no hallucinations allowed

Failing one = fix logic, not prompt.

---

## 🔚 What NOT to do next (important)

❌ Do NOT add more documents yet
❌ Do NOT tweak embeddings
❌ Do NOT jump to agents
❌ Do NOT over-optimize models

You’re past the hard part already.

---

## 🎯 Recommended Immediate Next Step (DO THIS)

👉 **Implement Query Classification + Retrieval Orchestration**
This is the backbone of the “LLM logic integration” you marked as next.
