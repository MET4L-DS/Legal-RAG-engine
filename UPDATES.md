2️⃣ What is ACTUALLY going wrong in both examples?
🔍 Root cause (same for robbery & sexual assault)

Your system is currently doing this:

“From all retrieved SOP blocks, extract any timelines.”

This is technically correct
but legally incomplete

Why?

Because not all timelines are equal.

Law has:

Primary victim-critical timelines

Secondary procedural timelines

Downstream administrative timelines

Right now, your system treats them as peers.

3️⃣ The sexual assault example — what is missing?

Look at your sexual assault timeline:

✔ Medical examination — 24 hours (correct)
✔ Rehabilitation — promptly (correct)

❌ But what is missing from “Critical Timelines”?

These are missing or under-emphasized:

Recording of FIR / Zero FIR – immediate

Recording of statement u/s 183 BNSS – without delay

Production before Magistrate (if arrest occurs) – 24 hours

Informing Legal Services Authority – promptly

These are core victim-action timelines.

Why didn’t they appear?

👉 Because they live in General SOP, not just the Rape SOP.

4️⃣ Why “query General SOP every time” feels right (but isn’t enough)

You’re right about this intuition:

“To get correct timelines, we need General SOP every time”

But here’s the key insight:

🔴 The problem is NOT retrieval
🔴 The problem is timeline anchoring

You already retrieve General SOP content.
The issue is how you decide which timelines are “critical.”

5️⃣ The correct architectural fix (THIS IS IMPORTANT)
❌ Do NOT do:

Multi-threaded RAG

Parallel querying

Re-querying on failure

Letting LLM “merge” timelines

These add complexity without solving the legal logic problem.

✅ The CORRECT solution: Timeline Anchors
Introduce a new concept in backend:

TIMELINE ANCHORS

A timeline anchor is a mandatory stage that must exist for a given case type, regardless of which SOP it comes from.

6️⃣ Concrete design (Copilot-friendly)
Step 1: Define timeline anchors per case type
TIMELINE_ANCHORS = {
"sexual_assault": [
"fir_registration",
"medical_examination",
"statement_recording",
"victim_protection"
],
"robbery": [
"fir_registration",
"investigation_commencement"
]
}

These are not documents, they are legal stages.

Step 2: Map SOP sections to stages

Example:

SOP_STAGE_MAP = {
"SOP_RAPE_MHA": [
"medical_examination",
"victim_protection",
"rehabilitation"
],
"GENERAL_SOP_BPRD": [
"fir_registration",
"statement_recording",
"investigation_commencement"
]
}

This mapping is static, testable, and deterministic.

Step 3: Timeline extraction becomes a 2-pass process
Pass 1 — Anchor resolution (mandatory)

For each anchor:

Find any SOP block (rape SOP or general SOP) that satisfies it

If none found → hard failure

Pass 2 — Secondary timelines

Add downstream / administrative timelines

Mark them as secondary

7️⃣ How this fixes BOTH of your examples
Sexual assault

Your “Critical Timelines” would now be:

FIR registration — immediate (General SOP)

Medical examination — 24 hours (Rape SOP)

Statement recording — without delay (General SOP)

Victim protection / shelter — promptly (Rape SOP)

Rehabilitation becomes secondary, not leading.

Robbery

Primary:

FIR registration — immediate

Investigation commencement — promptly

Secondary:

Property attachment — 14 days

Exactly what a victim expects.

8️⃣ What to do when anchors FAIL (this answers your first question)

If an anchor cannot be resolved:

🔴 For Tier-1 crimes (sexual assault, rape, custodial violence)

→ FAIL HARD

{
"system_notice": {
"type": "ANCHOR_MISSING",
"stage": "fir_registration",
"message": "Mandatory procedural timeline could not be reliably determined."
},
"confidence": "low",
"timeline": []
}

This is legally safer than guessing.
