---
title: Indian Legal RAG Engine
emoji: ⚖️
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
license: mit
---

# Indian Legal RAG Engine (V3)

A high-precision Retrieval-Augmented Generation (RAG) system specialized in Indian Law. This engine is designed to bridge the gap between complex legal statutes and citizen understanding, with a specialized **Victim-Centric** focus for individuals.

## 🚀 API Endpoints

- **Health Check**: `GET /health`
- **Legal Query**: `POST /api/v1/query`

### Example Query

```json
POST /api/v1/query
{
  "query": "I have been assaulted, what should I do?",
  "stream": false
}
```

## 📚 Data Sources

- Bharatiya Nyaya Sanhita (BNS), 2023
- Bharatiya Nagarik Suraksha Sanhita (BNSS), 2023
- Bharatiya Sakshya Adhiniyam (BSA), 2023
- NALSA Compensation Scheme, 2018
- Police Standard Operating Procedures

## ⚖️ Disclaimer

This engine provides information based on legal texts but does **not** constitute professional legal advice.
