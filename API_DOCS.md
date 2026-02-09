# Legal RAG Engine - API Documentation & Frontend Guide

This document describes the API endpoints provided by the Legal RAG backend and provides **design guidelines** for the frontend, specifically for the **Victim-Centric** and **Markdown-enabled** interface.

## Base URL

- **Local**: `http://localhost:8000`
- **Prod**: `TBD`

---

## 1. Health Check

- **URL**: `/health`
- **Method**: `GET`
- **Response**: `{"status": "ok", "components": {"vector_store": "ready", "llm": "ready"}}`

---

## 2. Legal Query (Chat)

The primary endpoint for all user queries.

- **URL**: `/api/v1/query`
- **Method**: `POST`
- **Content-Type**: `application/json`

### Request Body

```json
{
	"query": "I have been assaulted, what can I do?",
	"stream": false
}
```

### Response Schema

| Field                   | Type             | Description                                                                                                                                                     |
| :---------------------- | :--------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `answer`                | `string`         | **Markdown Format.** Contains inline citation chips like `[BNS:115]`, `[BNSS:48]` that correspond to source chip_labels. All important notes are included here. |
| `safety_alert`          | `string \| null` | Immediate critical safety advice. **Only populated if `user_context` is `victim_distress`.**                                                                    |
| `immediate_action_plan` | `array[string]`  | Top-priority chronological steps. **Only populated if `user_context` is `victim_distress`.**                                                                    |
| `legal_basis`           | `string`         | Summary of the laws/sections used.                                                                                                                              |
| `procedure_steps`       | `array[string]`  | Detailed chronological steps (if procedural).                                                                                                                   |
| `sources`               | `array[object]`  | Exact source citations. Each has `uid` (unique ID like "BNS_115"), `chip_label` (like "[BNS:115]"), `law`, `section`, `content`, `citation`.                    |
| `metadata`              | `object`         | Processing details (intent, context, confidence).                                                                                                               |

---

## 🎨 Frontend Design Guide (CRITICAL)

The frontend MUST support Markdown rendering and handle conditional safety fields.

### 1. Markdown Rendering

**Required**: The `answer` field contains Markdown (bolding, lists, etc.).

- **Library**: Use `react-markdown` or `markdown-it`.
- **CSS**: Apply `prose` (Tailwind Typography) to the answer container.

### 2. Context-Aware Layouts

#### A. Victim Distress Mode

**Trigger**: `safety_alert != null` OR `metadata.user_context == "victim_distress"`.

- **Display 🚨 Safety Alert**: Use a high-visibility Red/Amber banner at the top of the response.
- **Display 📋 Immediate Action Plan**: Show as a checklist or stepper BEFORE the main `answer`.
- **Formatting**: The `answer` should be empathetic and encouraging.

#### B. Informational / Professional Mode

**Trigger**: `metadata.user_context` is `informational` or `professional`.

- **Clean Layout**: Do not reserve space for safety alerts/action plans if they are null.
- **Answer First**: Focus on the Markdown answer which now includes integrated legal notes.

### 3. Component Recommendations (ShadCN)

| Feature      | Component                | Notes                                               |
| :----------- | :----------------------- | :-------------------------------------------------- |
| Answer       | `Prose` / `Markdown`     | Enable support for lists and bolding.               |
| Safety Alert | `Alert` (Destructive)    | Fixed to top of response bubble.                    |
| Action Plan  | `Card` / `Checkbox` list | Interactive encourages user engagement.             |
| Citations    | `Accordion`              | Keep clean by hiding full snippets until requested. |

### 4. Citation Chip Rendering & Persistent Sources

**New Feature**: Citations now use law-based chips like `[BNS:115]`, `[BNSS:48]` instead of numeric `[1]`, `[2]`.

#### Source Registry Pattern

Maintain a global source registry for the entire chat session:

```typescript
// Global source registry
const sourceRegistry = new Map<string, SourceData>();

// When receiving a response
response.sources.forEach((source) => {
	if (!sourceRegistry.has(source.uid)) {
		sourceRegistry.set(source.uid, source);
	}
});
```

#### Chip Rendering

Parse and render citation chips as clickable elements:

```jsx
// Parse citation chips in answer
const renderAnswer = (text: string) => {
  return text.replace(/\[([A-Z]+)(?::(\d+))?\]/g, (match, law, section) => {
    const uid = section ? `${law}_${section}` : `${law}_GENERAL`;
    return `<Chip onClick={() => focusSource(uid)}>${match}</Chip>`;
  });
};
```

#### Benefits

- **No Duplicates**: Same source always has same `uid` across messages
- **Reduced Lag**: Only new sources are added to the panel
- **User-Friendly**: `[BNS:115]` is more informative than `[1]`

### 5. Accessibility

- **Font**: Use readable sans-serif (Inter/Geist).
- **Contrast**: Ensure high contrast for safety alerts (WCAG AA).
- **Structure**: Use proper heading hierarchy within the Markdown answer.
