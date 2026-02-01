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

| Pattern          | Action                           |            |
| ---------------- | -------------------------------- | ---------- |
| `# PART`         | set `part`                       |            |
| `# CHAPTER`      | set `chapter`                    |            |
| `## <TITLE>`     | set chapter title                |            |
| `## Section X —` | set section + reset sub-sections |            |
| `**(1)**`        | set sub-section                  |            |
| `Illustrations`  | switch to illustration mode      |            |
| `Explanation.—`  | explanation mode                 |            |
| `                | ` table row                      | table mode |
| `**Step X:**`    | SOP step                         |            |
| `---`            | flush current chunk              |            |

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

### Example (BNS Section 14):

```txt
Bharatiya Nyaya Sanhita, 2023
Chapter III – General Exceptions
Section 14 – Act done by a person bound by law

Nothing is an offence which is done by a person who is...
```

⚠️ This header is **injected by code**, never written in markdown.

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

- Each numbered scenario (`03.`, `04.`)
- Bullets stay inside same chunk

---

### 🟪 D. General SOP

Chunks:

- Each **Step**
- Each **Decision branch**
- Each **Outcome**

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

- **One embedding model**
- Embed **ONLY canonical chunk text**
- Metadata is stored, **not embedded**
- Target size: **150–500 tokens**

---

## 7️⃣ Vector Store Strategy (FINAL)

✅ **ONE vector store ONLY**

Do **NOT** separate by:

- Act
- SOP
- Scheme

Filtering is done **at query time**, not storage time.

---

## 8️⃣ Retrieval Logic (tree-like behavior WITHOUT tree embeddings)

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

## 9️⃣ Re-ingestion & Updates

When law/SOP changes:

1. Update `.md`
2. Re-run ingestion
3. Rebuild vector index

❌ No manual fixes
❌ No partial updates
