This plan applies to **ALL documents** you shared:

- BNS
- BNSS
- BSA
- NALSA Compensation Scheme (+ tables)
- SOP on Rape
- General SOP
- Future additions (Judgments, Schedules, Amendments)

---

## 🔒 NON-NEGOTIABLE RULES (lock these first)

1. **Do NOT edit `.md` source files**
2. **Do NOT embed chapters, parts, or documents**
3. **Do NOT create multiple vector stores**
4. **Do NOT embed summaries**
5. **EVERY embedding = one atomic legal unit**

---

## 🧠 Core Architecture (Final)

```
Markdown (.md)
   ↓
Stateful Markdown Parser
   ↓
Atomic Chunk Generator
   ↓
Canonical Header Injection
   ↓
Metadata Attachment
   ↓
Embedding Model
   ↓
ONE Vector Store
```

---

## 1️⃣ Define the Atomic Units (what gets embedded)

Everything is reduced to **legal atoms**:

| Document         | Atomic unit                                        |
| ---------------- | -------------------------------------------------- |
| BNS / BNSS / BSA | Section / Sub-section / Explanation / Illustration |
| NALSA Scheme     | Clause / Definition / Table Row                    |
| SOP on Rape      | Each numbered scenario                             |
| General SOP      | Each Step / Decision / Outcome                     |
| Tables           | **Each row**                                       |

👉 **Nothing larger than this is ever embedded.**

---

## 2️⃣ Stateful Markdown Parsing (how structure is understood)

Your parser runs **line by line** and maintains context:

```ts
currentContext = {
	law: null,
	part: null,
	chapter: null,
	chapterTitle: null,
	section: null,
	sectionTitle: null,
	subSection: null,
	mode: "normal", // normal | illustration | explanation | table | sop
};
```

### Context is updated when parser sees:

| Pattern                     | Action                           | Document Type | Notes                            |
| --------------------------- | -------------------------------- | ------------- | -------------------------------- |
| `# PART`                    | set `part`                       | BNS/BNSS/BSA  |                                  |
| `# CHAPTER`                 | set `chapter`                    | BNS/BNSS/BSA  |                                  |
| `## <TITLE>`                | set chapter title                | BNS/BNSS/BSA  | Without section number           |
| `## Section X —`            | set section + reset sub-sections | BNS/BNSS/BSA  |                                  |
| `## X. <TITLE>`             | set clause number + title        | NALSA         | e.g., `## 2. DEFINITIONS`        |
| `## **SOP ON ...**`         | set SOP topic/chapter            | SOP           | General SOP pattern              |
| `**XX. <TITLE> - Suggested` | set SOP step with title          | SOP (Rape)    | e.g., `**01. FIR - Suggested...` |
| `### X. <TITLE>`            | set sub-topic/category           | SOP           | e.g., `### 1. ORAL`              |
| `**(1)**`, `**(2)**`        | set sub-section/sub-clause       | ALL           | Numbered sub-items               |
| `- **(a)**`, `- **(b)**`    | set definition/list item         | NALSA         | Lettered items in definitions    |
| `**Step X:**`               | set procedural step              | SOP (General) | e.g., `**Step 1:**`              |
| `Illustrations`             | switch to illustration mode      | ALL           |                                  |
| `Explanation.—`             | explanation mode                 | ALL           |                                  |
| `\|` (pipe char in line)    | table row detected               | ALL           | Markdown table syntax            |
| `---`                       | flush current chunk              | ALL           | Horizontal rule / separator      |

---

## 3️⃣ Canonical Chunk Text (THIS is what gets embedded)

Every chunk MUST be constructed like this:

```txt
<LAW NAME>, <YEAR>
<PART (if any)>
<CHAPTER NUMBER – CHAPTER TITLE>
Section <X> – <SECTION TITLE>
Sub-section (<Y>) / Illustration / Step (if applicable)

<EXACT ORIGINAL TEXT>
```

### Example 1 (BNS Section 14):

```txt
Bharatiya Nyaya Sanhita, 2023
Chapter III – General Exceptions
Section 14 – Act done by a person bound by law

Nothing is an offence which is done by a person who is...
```

### Example 2 (NALSA Clause 2, Definition (a)):

```txt
NALSA Compensation Scheme, 2018
Clause 2 – Definitions
Definition (a)

"Code" means the Code of Criminal Procedure, 1973 (2 of 1974); or "Sanhita" means The Bhartiya Nagarik Suraksha Sanhita, 2023.
```

### Example 3 (SOP on Rape, Step 01):

```txt
Standard Operating Procedure on Rape Against Women
Section 01 – FIR

FIR must be recorded in accordance with the provisions of Section 173, Bharatiya Nagarik Suraksha Sanhita, 2023 (BNSS)...
```

### Example 4 (NALSA Table Row - Rape Compensation):

```txt
NALSA Compensation Scheme, 2018
Schedule – Women Victims of Crimes
Row 3 – Rape

Minimum Compensation: Rs. 4 Lakh
Maximum Compensation: Rs. 7 Lakh
```

⚠️ These headers are **injected by code**, never written in markdown.

---

## 4️⃣ Chunking Rules (document-specific)

### 🟦 A. BNS / BNSS / BSA

Create **separate chunks** for:

- Main section body
- EACH sub-section `(1)`, `(2)`…
- EACH illustration `(a)`, `(b)`
- EACH explanation

BNSS Section 8 becomes:

- 8(1) → chunk
- 8(2) → chunk
- …
- Explanation → chunk

---

### 🟨 B. NALSA Compensation Scheme

Chunks:

- Each numbered clause
- Each definition `(a)`, `(b)`
- **Each table row**

Table row chunk example:

```txt
NALSA Compensation Scheme, 2018
Schedule – Women Victims of Crimes
Offence: Rape

Minimum Compensation: Rs. 4 Lakh
Maximum Compensation: Rs. 7 Lakh
```

---

### 🟥 C. SOP on Rape

Chunks:

- Each numbered procedural step (e.g., `**01. FIR - Suggested time limit: Immediately**`)
- Sub-bullets and explanatory text stay inside the same chunk
- Each step is a complete procedure with its context

---

### 🟪 D. General SOP

Chunks:

- Each **SOP Topic** (e.g., `## **SOP ON TYPES OF PETITION**`)
- Each **Category/Sub-topic** (e.g., `### 1. ORAL`, `### 2. Written`)
- Each **Step** (e.g., `**Step 1:**`, `**Step 2:**`)
- Each **Decision branch** or **Outcome**

**Chunking Strategy:** Group related steps under the same topic into one chunk when they form a coherent procedure. For complex SOPs with multiple independent procedures, create separate chunks per major section.

---

## 5️⃣ Metadata Schema (attached to every chunk)

```json
{
	"law": "BNS | BNSS | BSA | NALSA | SOP",
	"law_name": "...",
	"year": 2023,
	"doc_type": "primary_legislation | compensation_scheme | sop",
	"part": "IV",
	"chapter": "III",
	"chapter_title": "General Exceptions",
	"section": "14",
	"sub_section": "1",
	"unit_type": "section | sub_section | illustration | explanation | step | table_row",
	"source_file": "BNS.md"
}
```

Tables add:

```json
{
	"offence": "Rape",
	"min_compensation": 400000,
	"max_compensation": 700000
}
```

---

## 6️⃣ Embedding Strategy (FINAL)

- **One embedding model** (Recommended: `text-embedding-3-large` or `cohere-embed-english-v3.0` for legal nuance)
- Embed **ONLY canonical chunk text**
- Metadata is stored, **not embedded**
- Target size: **150–500 tokens**

---

## 7️⃣ Pre-Computation Validation (Dry Run)

Before generating any embeddings, we MUST run a **Dry Run** script:

1. **Parse all documents.**
2. **Generate "Canonical Chunks"** into a pure text file (`debug_chunks.txt`).
3. **Audit the definition boundaries:**
    - Did we accidentally cut a sentence?
    - Is the "SOP on Rape" step linked to the correct parent subject?
    - Are tables correctly expanded (headers + values)?
4. **Sign-off**: Only proceed to embedding once `debug_chunks.txt` looks perfect.

---

## 8️⃣ Vector Store Strategy (FINAL)

✅ **ONE vector store ONLY**

Do **NOT** separate by:

- Act
- SOP
- Scheme

Filtering is done **at query time**, not storage time.

---

## 9️⃣ Retrieval Logic (tree-like behavior WITHOUT tree embeddings)

1. Semantic search → top-K atomic chunks
2. Metadata expansion:
    - If sub-section → include parent section
    - If illustration → include main rule
    - If table row → include scheme clause

3. Priority ordering:
    1. Primary legislation
    2. Compensation schemes
    3. SOPs

This **simulates hierarchy** without embedding it.

---

## 🔟 Re-ingestion & Updates

When law/SOP changes:

1. Update `.md`
2. Re-run ingestion
3. Rebuild vector index

❌ No manual fixes
❌ No partial updates
