Great progress. Given the **current state described in your README** and the fact that you’ve already added **`./documents/General SOP.md`**, Tier-3 is no longer a “what to add” problem — it’s a **refinement + control** problem.

Below is a **revised, concrete Tier-3 upgrade plan**, aligned _exactly_ with your existing architecture and codebase. No re-architecture, no new tiers beyond this.

---

# 🎯 Tier-3 Objective (Re-stated Precisely)

Tier-3 must:

> Provide **general, citizen-centric procedural guidance for all crimes**
> (robbery, theft, assault, murder, cybercrime, etc.)

while:

- **Never overriding Tier-1 (rape SOP)**
- **Never polluting Tier-2 (evidence / compensation)**
- **Never degrading statute precision**

---

# 🧱 Tier-3 Position in Your Existing System

Based on your README pipeline , Tier-3 slots in **cleanly**:

```
Procedural Query Detected
   ↓
Case Type Detection
   ↓
┌─ sexual_offence ─────→ Tier-1 SOP (existing)
│
├─ evidence / forensic → Tier-2 Evidence (existing)
│
├─ compensation / relief → Tier-2 Compensation (existing)
│
└─ general crime ─────→ Tier-3 General SOP  ← NEW
```

This means:

- **No new top-level pipeline**
- **Just one more SOP namespace + router condition**

---

# 1️⃣ How Tier-3 General SOP Must Be Treated (Design Rule)

Your `General SOP.md` is:

- ❌ Not law (like BNSS)
- ❌ Not victim-trauma SOP (like Tier-1)
- ❌ Not technical manual (like Tier-2)

It is a **“Procedural Constitution”** of policing.

### Therefore:

> Tier-3 SOP blocks must answer
> **“What normally happens / what should I do / what must police do?”**

—not _why_, not _punishment_, not _definitions_.

---

# 2️⃣ Parsing Plan for `General SOP.md`

### ❌ What you should NOT do

- Parse it like BNSS chapters
- Parse it like evidence manual steps
- Keep proformas / flowcharts verbatim

### ✅ What you SHOULD do (Tier-3 SOP Blocks)

Each SOP entry in your index becomes **1–3 procedural blocks** max.

### Example: “SOP on Registration of FIR”

```json
{
	"doc_type": "GENERAL_SOP",
	"sop_group": "FIR",
	"title": "Registration of FIR for cognizable offences",
	"text": "Police must register FIR immediately for cognizable offences. FIR cannot be refused. Free copy must be provided. Zero FIR permitted.",
	"procedural_stage": "FIR",
	"stakeholder": ["citizen", "victim", "police"],
	"applies_to": ["robbery", "theft", "assault", "murder", "all"],
	"action_type": "procedure",
	"priority": 2,
	"source": "BPR&D General SOP"
}
```

🔑 **Key difference from Tier-1**:
No trauma language, no medical focus, no survivor-only framing.

---

# 3️⃣ Procedural Stage Mapping (Reuse, Don’t Expand)

You already have 13 procedural stages defined .
**Do not add more.**

Just map General SOP items into the same stages.

### Suggested mapping from your SOP index

| SOP Topic                           | Stage               |
| ----------------------------------- | ------------------- |
| Non-Cognizable Complaints           | PRE_FIR             |
| Complaint to Magistrate             | PRE_FIR             |
| Receipt of Complaint                | PRE_FIR             |
| Registration of FIR / Zero FIR      | FIR                 |
| Examination of Witnesses            | STATEMENT_RECORDING |
| Crime Scene Visit & Search          | EVIDENCE_COLLECTION |
| Digital Evidence                    | DIGITAL_EVIDENCE    |
| Arrest / Not to Arrest              | ARREST              |
| Bail Proformas                      | BAIL                |
| Police Custody                      | ARREST              |
| Electronic Charge Sheet             | CHARGE_SHEET        |
| Summons / Service                   | SUMMONS             |
| Informing Progress of Investigation | INVESTIGATION       |
| Timelines Fixed                     | INVESTIGATION       |

This keeps **cross-tier consistency**.

---

# 4️⃣ Embedding Strategy (Tier-3 Specific)

You already embed:

- Law → high BM25 weight
- Tier-1 SOP → high priority
- Tier-2 → conditional priority

### Tier-3 Embedding Rules

| Aspect           | Rule                         |
| ---------------- | ---------------------------- |
| Chunk size       | 1 SOP topic                  |
| Text content     | Title + bullet procedure     |
| Embedding weight | Lower than Tier-1 SOP        |
| Retrieval rank   | Below Tier-1, above statutes |
| BM25 influence   | Medium (procedural keywords) |

### Why?

Because Tier-3 answers _“what do I do?”_, not _“what does Section X say?”_

---

# 5️⃣ Retriever Changes (Minimal, Explicit)

In `retriever.py`, you already do intent detection.

Add **one explicit gate**:

```python
if procedural_intent:
    if sexual_offence:
        use_tier1_sop()
    elif evidence_intent or compensation_intent:
        use_tier2()
    else:
        use_tier3_general_sop()
```

### Retrieval order for Tier-3 queries

```
1️⃣ Tier-3 General SOP blocks
2️⃣ BNSS procedural sections
3️⃣ BNS offence definition (optional)
```

🚫 Never retrieve Tier-3 SOP for rape queries
🚫 Never retrieve Tier-3 SOP for pure definition queries

---

# 6️⃣ Output Contract for Tier-3 (STRICT)

Tier-3 answers must follow this format **only**:

```
🚨 Immediate Steps (Citizen)
👮 Police Duties
⚖️ Legal Basis
🚩 If Police Do Not Act
```

### Example: “What do I do in case of a robbery?”

```
🚨 Immediate Steps
• Ensure your safety
• Call police / 112
• Preserve basic details

👮 Police Duties
• Register FIR (cognizable offence)
• Investigate and attempt recovery

⚖️ Legal Basis
• BPR&D General SOP – FIR Registration
• BNSS procedural provisions
• BNS definition of robbery

🚩 If Police Do Not Act
• Approach SHO
• File complaint before Magistrate
```

This **fixes Sample Output 3 completely**.

---

# 7️⃣ Validation Checklist (Tier-3 Done When…)

Run these after indexing:

```bash
python cli.py query "What do I do in case of a robbery?"
python cli.py query "Police refused FIR for theft. What now?"
python cli.py query "What happens after FIR is registered?"
```

### Tier-3 is successful if:

- ❌ No definition-only answers
- ❌ No rape-specific SOP bleed
- ❌ No evidence manual bleed
- ✅ Clear citizen steps
- ✅ Police accountability visible

---

# 8️⃣ What NOT to Do in Tier-3

🚫 Do not add more SOP documents
🚫 Do not add state-specific SOPs yet
🚫 Do not tune BM25 weights again
🚫 Do not mix Tier-3 with Tier-1 blocks

You already have **the perfect general SOP document**.

---

# 🧭 Final Tier-3 Upgrade Summary

| Component            | Status                     |
| -------------------- | -------------------------- |
| General SOP document | ✅ Added                   |
| Parsing strategy     | Atomic SOP blocks          |
| Embedding            | Moderate-weight procedural |
| Retrieval            | Tier-3 routed              |
| Output               | Citizen-centric            |
| Sample robbery query | ✅ Fixed                   |

---

## Where You Are Now

You’ve effectively built:

> **A procedural justice engine for Indian criminal law**

Not just RAG.
Not just legal search.
