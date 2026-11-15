# Nutrition RAG Assistant

A chat web app that answers questions from the *Human Nutrition (2020 Edition)* PDF using
PyMuPDF → chunking → HuggingFace embeddings → FAISS → Gemini.

```
rag-nutrition-app/
├── backend/app.py        FastAPI server (RAG pipeline + /api/ask)
├── frontend/             index.html, style.css, app.js (served by FastAPI)
├── data/                 put the PDF here
├── requirements.txt
└── .env.example
```

## Setup

1. **Python 3.10+** is required.
2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate        # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. Put the PDF in `data/` named `Human-Nutrition-2020-Edition-1598491699.pdf`
   (or set `PDF_PATH` in `.env`).
4. Create your env file and add your Gemini key (https://aistudio.google.com/apikey):
   ```bash
   cp .env.example .env             # Windows: copy .env.example .env
   ```
5. Run:
   ```bash
   uvicorn backend.app:app --reload
   ```
6. Open http://127.0.0.1:8000

The first start builds the FAISS index from the PDF (a few minutes, and downloads the
embedding model). It's saved to `FAISS_index/`, so later starts take seconds.
Delete that folder if you change the PDF or chunk settings.

## API

- `POST /api/ask` with `{"question": "...", "k": 4}` returns `{"answer": "...", "sources": [{page, snippet, score}]}`
- `GET /api/health` returns `{"status": "ok", "ready": true}`
- Interactive docs: http://127.0.0.1:8000/docs

## Notes

- Page numbers shown are 1-indexed (matching PDF viewers). Each retrieved chunk is labelled
  `[Page N]` in the prompt, so Gemini can cite pages without inventing them.
- `--reload` restarts the server on code edits and reloads the models each time. Omit it for
  faster restarts when not developing.
- `allow_dangerous_deserialization=True` is used to load the local FAISS index. Only load
  indexes you created yourself.
