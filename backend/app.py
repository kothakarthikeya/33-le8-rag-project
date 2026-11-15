"""
Nutrition RAG backend (FastAPI).

Pipeline (same as the Colab notebook):
PDF -> chunks -> HuggingFace embeddings -> FAISS -> Gemini answer.

Run from the project root:
    uvicorn backend.app:app --reload
Then open http://127.0.0.1:8000
"""
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from langchain_community.document_loaders import PyMuPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

env_pdf = os.getenv("PDF_PATH")
if env_pdf:
    PDF_PATH = Path(env_pdf)
    if not PDF_PATH.is_absolute():
        PDF_PATH = ROOT / PDF_PATH
else:
    default_full = ROOT / "data" / "Human-Nutrition-2020-Edition-1598491699.pdf"
    default_sample = ROOT / "data" / "sample-nutrition.pdf"
    PDF_PATH = default_full if default_full.exists() else default_sample
INDEX_DIR = ROOT / "FAISS_index"
FRONTEND_DIR = ROOT / "frontend"

EMBED_MODEL = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", 500))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", 120))

TEMPLATE = """You are a helpful teaching assistant.
Answer ONLY using the supplied document context.
If the answer is not present, say:
'I could not find this in the provided document.'
Use simple language and cite source page numbers where possible (each context
block starts with its page label, e.g. [Page 42]).
Do not invent citations.

Document context:
{context}

Question: {question}"""

state = {}


def build_or_load_index(embeddings):
    """Load the saved FAISS index, or build it from the PDF on first run."""
    if INDEX_DIR.exists():
        print("Loading existing FAISS index...")
        return FAISS.load_local(
            str(INDEX_DIR), embeddings, allow_dangerous_deserialization=True
        )

    if not PDF_PATH.exists():
        raise FileNotFoundError(
            f"PDF not found at {PDF_PATH}. Put it in the data/ folder "
            "or set PDF_PATH in .env"
        )

    print(f"Building index from {PDF_PATH.name} (first run only, may take a few minutes)...")
    docs = PyMuPDFLoader(str(PDF_PATH)).load()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP
    )
    chunks = splitter.split_documents(docs)
    print(f"{len(docs)} pages -> {len(chunks)} chunks")

    store = FAISS.from_documents(chunks, embeddings)
    store.save_local(str(INDEX_DIR))
    return store


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not os.getenv("GOOGLE_API_KEY"):
        raise RuntimeError("GOOGLE_API_KEY is missing. Copy .env.example to .env and add your key.")

    embeddings = HuggingFaceEmbeddings(model_name=EMBED_MODEL)
    state["store"] = build_or_load_index(embeddings)

    llm = ChatGoogleGenerativeAI(model=GEMINI_MODEL)
    prompt = ChatPromptTemplate.from_template(TEMPLATE)
    state["chain"] = prompt | llm | StrOutputParser()
    print("RAG backend ready.")
    yield
    state.clear()


app = FastAPI(title="Nutrition RAG Assistant", lifespan=lifespan)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=1000)
    k: int = Field(4, ge=1, le=10)


class Source(BaseModel):
    page: int
    snippet: str
    score: float


class AskResponse(BaseModel):
    answer: str
    sources: list[Source]


def page_of(doc) -> int:
    # PyMuPDFLoader pages are 0-indexed; show 1-indexed to match PDF viewers.
    return int(doc.metadata.get("page", 0)) + 1


@app.get("/api/health")
def health():
    return {"status": "ok", "ready": "chain" in state}


@app.post("/api/ask", response_model=AskResponse)
def ask(req: AskRequest):
    if "chain" not in state:
        raise HTTPException(503, "Backend is still starting up.")
    try:
        results = state["store"].similarity_search_with_score(req.question, k=req.k)
        context = "\n\n".join(f"[Page {page_of(d)}]\n{d.page_content}" for d, _ in results)
        answer = state["chain"].invoke({"context": context, "question": req.question})
    except Exception as e:  # surface LLM/API errors to the UI
        raise HTTPException(500, f"Failed to generate answer: {e}")

    sources = [
        Source(
            page=page_of(d),
            snippet=d.page_content.strip().replace("\n", " ")[:300],
            score=float(score),
        )
        for d, score in results
    ]
    return AskResponse(answer=answer, sources=sources)


# Frontend (static files)
@app.get("/")
def index():
    return FileResponse(FRONTEND_DIR / "index.html")


app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
