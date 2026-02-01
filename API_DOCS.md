# Legal RAG Engine - API Documentation & Frontend Guide

This document describes the API endpoints provided by the Legal RAG backend and provides **design guidelines** for the frontend to strictly implement the **Victim-Centric** interface.

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

The primary endpoint. It automatically detects if the user is a `victim_distress`, `professional`, or `informational` user.

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

### Response (Victim-Centric Schema)

The response structure is dynamic. Frontend **MUST** handle the `safety_alert` field with highest priority.

```json
{
	"answer": "I understand you have been assaulted...",
	"safety_alert": "Dial 112 immediately. Move to a secure location.",
	"immediate_action_plan": [
		"Go to the nearest police station.",
		"File a Zero FIR.",
		"Seek medical attention."
	],
	"legal_basis": "Based on General SOP and NALSA Scheme.",
	"procedure_steps": ["detailed procedural step 1", "..."],
	"important_notes": ["Note 1"],
	"sources": [
		{
			"law": "General SOP",
			"section": "Zero FIR",
			"citation": "General SOP - Zero FIR",
			"text": "..."
		}
	],
	"metadata": {
		"intent": "procedure",
		"user_context": "victim_distress",
		"confidence": 0.95
	}
}
```

---

## 🎨 Frontend Design Guide (CRITICAL)

The UI must adapt based on the `safety_alert` presence and `user_context`.

### 1. The "Victim Mode" UI

**Trigger**: When `safety_alert` is NOT null OR `metadata.user_context == "victim_distress"`.

- **🚨 Safety Banner (Top Priority)**
    - **Component**: Full-width alert banner at the very top of the message bubble.
    - **Color**: Red (`bg-red-50` text-red-900` border-red-200`).
    - **Icon**: Warning Triangle / Siren.
    - **Content**: Display the `safety_alert` string in bold.

- **📋 Immediate Action Plan (Above the Fold)**
    - **Component**: Checklist or Stepper.
    - **Location**: Immediately below the Safety Banner, BEFORE the main text answer.
    - **Style**: Simple, large text. Checkboxes that allow users to mentally "check off" steps.
    - **Color**: Orange/Amber accent.

- **💬 Main Answer**
    - **Style**: Supportive, empathetic typography.
    - **formatting**: Paragraphs with generous line height.

### 2. The "Professional/Informational" UI

**Trigger**: When `user_context` is `professional` or `informational`.

- **Layout**: Standard Chat Interface.
- **Answer**: Display `answer` first.
- **Sources**: Show citations as clickable footnotes or a "Sources" accordion at the bottom.
- **No Safety Banner**: Do not show empty alerts.

### 3. Component Recommendations (ShadCN/Tailwind)

| Feature      | Recommended Component                                     |
| :----------- | :-------------------------------------------------------- |
| Safety Alert | `Alert` (Destructive variant with custom styling)         |
| Action Plan  | `Card` with `Checkbox` list                               |
| Citations    | `HoverCard` or `Accordion`                                |
| Disclaimer   | Small muted text footer (`text-xs text-muted-foreground`) |

### 4. Accessibility

- **Typography**: Use `Inter` or `sans-serif`. Min font size `16px` for body text.
- **Reading Level**: The backend targets Grade 8 English. Frontend should not complicate this with dense layouts.
