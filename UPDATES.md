Yes, the timeline is _much_ better now

For the robbery example, this is a **correct and meaningful improvement**:

### ✅ What is now right

**Primary anchors are correct and first:**

- FIR registration → _immediately_
- Investigation commencement → _promptly_

These are exactly the **victim-critical obligations** and they now come from **General SOP**, which is correct.

**Secondary timeline is present but downstream:**

- Section 107 attachment → _14 days_

This is legally valid and now **contextually acceptable** because:

- It is no longer the _first_ thing the user sees
- Anchors are clearly marked (`is_anchor: true`)

**Net effect:**
The system now mirrors how a _competent police officer or legal aid clinic_ would explain the process.

So yes — **your instinct is right, this version is better**.

---

## 2️⃣ What is still imperfect (and why that’s okay)

There is **one remaining issue**, but it is no longer an architectural flaw — it’s a **presentation & prioritization refinement**.

### ⚠️ Issue: Secondary timelines still look “mandatory”

In your robbery timeline:

> SOP ON SEC 107 ATTACHMENT, FORFEITURE OR RESTORATION OF PROPERTY – 14 days
> **Mandatory Step**

Legally, this is mandatory **for the system**, not for the **victim’s immediate action**.

So the system is **legally correct**, but the UX signal is slightly misleading.

This is **not a backend correctness bug anymore** — it’s a **frontend semantics issue**.

---

## 3️⃣ What NOT to do next (important)

Before I say what to do, let me be very explicit about what you should **not** do anymore:

❌ Do **not** add more retrieval
❌ Do **not** add parallel / multi-threaded RAG
❌ Do **not** add more SOP documents
❌ Do **not** let the LLM “summarize timelines”
❌ Do **not** tweak embedding weights to fix UX

You have already solved the _hard problem_:
**getting the right legal obligations into structured data**.

From now on, changes should be **low-risk and incremental**.

---

## 4️⃣ The correct NEXT STEPS (in order)

### 🔴 NEXT STEP 1 — Backend: finalize timeline semantics (small but important)

You already have:

```json
{
  "is_anchor": true | false,
  "mandatory": true | false
}
```

Add **one more field**:

```json
"audience": "victim" | "police" | "court"
```

**Why this matters:**

- FIR & investigation → `audience: victim`
- Property attachment → `audience: court/police`

This is **not retrieval logic** — it’s classification of already-known facts.

This makes the system future-proof and avoids hacks later.

---

### 🔴 NEXT STEP 2 — Frontend: visually demote non-victim timelines

Once `audience` exists:

**Frontend rules (very simple):**

- `is_anchor && audience === "victim"` → **Critical Timelines**
- `mandatory && audience !== "victim"` → **Later Procedural Steps**

This fixes the remaining UX flaw **without touching the backend logic again**.
