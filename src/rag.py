"""RAG pipeline: load documents -> split -> Gemini embeddings -> vector store -> answer.

* The knowledge base is built AUTOMATICALLY (no admin needed) and rebuilt by itself
  whenever a document in data/knowledge_base is added or changed.
* Vector store: ChromaDB. If ChromaDB cannot start, an in-memory vector store is used.
* If Gemini embeddings fail (quota, key or model problem), a keyword search over the
  same document chunks is used instead, so answers keep working.
"""
import json
import math
import os
import re
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import CHROMA_DIR, KNOWLEDGE_DIR, SUPPORTED_EXTENSIONS, sync_bundled_documents
from .llm import get_llm, get_embeddings, invoke_llm

COLLECTION = "hr_policies"
INFO_FILE = Path(CHROMA_DIR) / "index_info.json"
MEMORY_FILE = Path(CHROMA_DIR) / "memory_store.json"
CHUNKS_FILE = Path(CHROMA_DIR) / "chunks.json"
IST = timezone(timedelta(hours=5, minutes=30))   # India Standard Time

_store = None          # cached vector store object
_chunks_cache = None   # cached chunks for keyword search


# --------------------------------------------------------------------------- #
# Documents
# --------------------------------------------------------------------------- #
def list_knowledge_files():
    sync_bundled_documents()
    base = Path(KNOWLEDGE_DIR)
    base.mkdir(parents=True, exist_ok=True)
    return sorted(
        p for p in base.rglob("*")
        if p.is_file()
        and p.suffix.lower() in SUPPORTED_EXTENSIONS
        and not p.name.lower().startswith("readme")   # never index instruction files
    )


def files_signature():
    """Names + sizes of all documents. If this changes, the index is rebuilt."""
    return [[p.name, p.stat().st_size] for p in list_knowledge_files()]


def _load_documents():
    from langchain_community.document_loaders import PyPDFLoader, TextLoader, Docx2txtLoader

    docs, errors = [], []
    for path in list_knowledge_files():
        try:
            suffix = path.suffix.lower()
            if suffix == ".pdf":
                loaded = PyPDFLoader(str(path)).load()
            elif suffix == ".txt":
                loaded = TextLoader(str(path), encoding="utf-8").load()
            else:  # .docx
                loaded = Docx2txtLoader(str(path)).load()
            for d in loaded:
                d.metadata["source_name"] = path.name
            docs.extend(loaded)
        except Exception as e:
            errors.append(f"{path.name}: {e}")
            print(f"Could not load {path}: {e}")
    return docs, errors


# --------------------------------------------------------------------------- #
# Index status
# --------------------------------------------------------------------------- #
def _write_info(info):
    Path(CHROMA_DIR).mkdir(parents=True, exist_ok=True)
    INFO_FILE.write_text(json.dumps(info, indent=2), encoding="utf-8")


def index_info():
    try:
        return json.loads(INFO_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def knowledge_base_exists():
    return bool(index_info().get("chunks"))


def knowledge_base_up_to_date():
    info = index_info()
    return bool(info.get("chunks")) and info.get("signature") == files_signature()


# --------------------------------------------------------------------------- #
# Vector store helpers
# --------------------------------------------------------------------------- #
def _patch_sqlite_if_needed():
    """ChromaDB needs SQLite >= 3.35. Swap in pysqlite3 if it is installed and needed."""
    try:
        import sqlite3
        if tuple(int(x) for x in sqlite3.sqlite_version.split(".")[:3]) >= (3, 35, 0):
            return
        import pysqlite3  # noqa: F401  (optional package)
        sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")
    except Exception:
        pass


def _open_chroma(embeddings):
    os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")  # stops noisy telemetry errors
    _patch_sqlite_if_needed()
    from langchain_community.vectorstores import Chroma
    return Chroma(
        persist_directory=CHROMA_DIR,
        embedding_function=embeddings,
        collection_name=COLLECTION,
    )


def build_knowledge_base():
    """(Re)build the index from every file in data/knowledge_base.
    Returns the number of documents indexed."""
    global _store, _chunks_cache
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    docs, load_errors = _load_documents()
    docs = [d for d in docs if d.page_content.strip()]
    if not docs:
        raise RuntimeError("No readable PDF, TXT or DOCX documents found in data/knowledge_base.")

    chunks = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=120).split_documents(docs)

    # Remove the old marker first, so a failed build never looks "ready".
    if INFO_FILE.exists():
        INFO_FILE.unlink()
    _store, _chunks_cache = None, None
    Path(CHROMA_DIR).mkdir(parents=True, exist_ok=True)

    # Always save the chunks, so keyword search works even without embeddings.
    CHUNKS_FILE.write_text(json.dumps(
        [{"text": c.page_content, "source": c.metadata.get("source_name", "")} for c in chunks]
    ), encoding="utf-8")

    backend, embedding_error = "keyword", ""
    try:
        embeddings = get_embeddings()
        try:
            store = _open_chroma(embeddings)
            try:
                # Safer than deleting the folder (Windows locks the Chroma files while in use).
                store.delete_collection()
            except Exception:
                pass
            store = _open_chroma(embeddings)
            store.add_documents(chunks)
            backend = "chroma"
        except Exception as chroma_error:
            print(f"ChromaDB unavailable, trying in-memory vector store: {chroma_error}")
            from langchain_core.vectorstores import InMemoryVectorStore
            store = InMemoryVectorStore(embedding=embeddings)
            store.add_documents(chunks)
            store.dump(str(MEMORY_FILE))
            backend = "memory"
        _store = store
    except Exception as exc:
        embedding_error = f"{type(exc).__name__}: {exc}"[:500]
        print("Gemini embeddings failed, using keyword search instead:", embedding_error)

    files = sorted({d.metadata.get("source_name", "") for d in docs})
    _write_info({
        "backend": backend,
        "files": files,
        "chunks": len(chunks),
        "signature": files_signature(),
        "load_errors": load_errors,
        "embedding_error": embedding_error,
        "built_at": datetime.now(IST).strftime("%d %b %Y %H:%M IST"),
    })
    return len(files)


_build_lock = threading.Lock()
_last_build_attempt = 0.0
_last_build_error = ""


def ensure_knowledge_base(retry_after_seconds=60):
    """Build/refresh the knowledge base automatically when needed (no admin needed).
    Returns (ok, error_message)."""
    global _last_build_attempt, _last_build_error
    if knowledge_base_up_to_date():
        return True, ""
    with _build_lock:
        if knowledge_base_up_to_date():          # another user may have just built it
            return True, ""
        if _last_build_error and time.time() - _last_build_attempt < retry_after_seconds:
            return knowledge_base_exists(), _last_build_error
        _last_build_attempt = time.time()
        try:
            build_knowledge_base()
            _last_build_error = ""
            return True, ""
        except Exception as exc:
            _last_build_error = f"{type(exc).__name__}: {exc}"
            print("Knowledge base build failed:", _last_build_error)
            return knowledge_base_exists(), _last_build_error


# --------------------------------------------------------------------------- #
# Retrieval
# --------------------------------------------------------------------------- #
_STOP = set("""a an and are as at be by can could do does for from get got have how i if in is it
its me my of on or our please should so tell that the their them there this to was we what when
where which who why will with would you your about any some know""".split())


def _tokens(text):
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in _STOP]


def _load_chunks():
    global _chunks_cache
    if _chunks_cache is None:
        try:
            _chunks_cache = json.loads(CHUNKS_FILE.read_text(encoding="utf-8"))
        except Exception:
            _chunks_cache = []
    return _chunks_cache


def _keyword_search(query, k):
    chunks = _load_chunks()
    if not chunks:
        return []
    tokenised = [_tokens(c["text"]) for c in chunks]
    n = len(chunks)
    q_terms = set(_tokens(query))
    scored = []
    for chunk, toks in zip(chunks, tokenised):
        score = 0.0
        for term in q_terms:
            tf = toks.count(term)
            if tf:
                df = sum(1 for t in tokenised if term in t)
                score += (1 + math.log(tf)) * (math.log((n + 1) / (df + 1)) + 1)
        if score > 0:
            scored.append((score, chunk))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:k]]


def _get_store():
    global _store
    if _store is not None:
        return _store
    info = index_info()
    embeddings = get_embeddings()
    if info.get("backend") == "memory":
        from langchain_core.vectorstores import InMemoryVectorStore
        _store = InMemoryVectorStore.load(str(MEMORY_FILE), embedding=embeddings)
    else:
        _store = _open_chroma(embeddings)
    return _store


def retrieve(query, k=6):
    """Return the most relevant chunks as [{"text": ..., "source": ...}]."""
    if not knowledge_base_exists():
        return []
    if index_info().get("backend") in ("chroma", "memory"):
        try:
            docs = _get_store().similarity_search(query, k=k)
            return [{"text": d.page_content,
                     "source": d.metadata.get("source_name") or Path(d.metadata.get("source", "")).name}
                    for d in docs]
        except Exception as exc:
            print("Vector search failed, using keyword search:", exc)
    return _keyword_search(query, k)


# --------------------------------------------------------------------------- #
# Answering
# --------------------------------------------------------------------------- #
PROMPT = """You are HR Assist, a friendly HR & IT help-desk assistant for company employees.
Today's date is {today}.
Answer ONLY using the company knowledge base below.
- For questions about holidays, use today's date to work out "next month", "this month",
  "upcoming" etc., and list each holiday with its date and day.
- If the knowledge base does not contain the answer, say clearly that it is not available
  in the current documents and suggest contacting HR or raising a request.
- Never invent policies, numbers, dates or limits.
- Keep the answer short and clear. Use bullet points for lists and steps.
{extra}

Company knowledge base:
{context}

Employee question:
{query}
"""

_DATE_WORDS = re.compile(
    r"holiday|month|mounth|week|today|tomorrow|upcoming|next|this year|festival|diwali|"
    r"christmas|dussehra|holi|eid|id-ul|calendar|vacation|off day|day off", re.I)


def _date_context():
    now = datetime.now(IST)
    first_next = (now.replace(day=1) + timedelta(days=32)).replace(day=1)
    first_after = (first_next + timedelta(days=32)).replace(day=1)
    return now, first_next, first_after


def answer_from_kb(query, mode="HR"):
    ok, error = ensure_knowledge_base()
    if not knowledge_base_exists():
        return ("Sorry, I can't search the company documents right now because the "
                "knowledge base could not be prepared.\n\n"
                f"**Technical details:** `{error[:500]}`")

    now, next_month, month_after = _date_context()
    # 1) Always search with the employee's own question.
    chunks = retrieve(query, k=6)
    # 2) For date / holiday questions, ALSO search the calendar for the current and next months,
    #    and add those results (the original results are never replaced).
    if _DATE_WORDS.search(query):
        dated = retrieve(f"{query} holidays {now:%B %Y} {next_month:%B %Y} {month_after:%B %Y}", k=4)
        seen = {c["text"] for c in dated}
        chunks = dated + [c for c in chunks if c["text"] not in seen]   # calendar months first
    if not chunks:
        return ("I couldn't find anything about that in the company documents. "
                "Please contact HR or use **Raise a Request**.")

    context = "\n\n---\n\n".join(c["text"] for c in chunks)
    sources = sorted({c["source"] for c in chunks if c.get("source")})
    sources_line = "\n\n*Sources: " + ", ".join(sources) + "*" if sources else ""

    if not get_llm():
        return "Here is what the company documents say:\n\n" + context[:3500] + sources_line

    extra = ("- This is an IT issue: give the self-help troubleshooting steps from the guide."
             if mode == "IT" else "")
    prompt = PROMPT.format(today=f"{now:%A, %d %B %Y}", extra=extra, context=context, query=query)
    try:
        answer = invoke_llm(prompt).strip()
    except Exception as exc:
        return ("The AI service is not responding right now, so here is the relevant part of the "
                "company documents:\n\n" + context[:2500] + sources_line +
                f"\n\n**Technical details:** `{type(exc).__name__}: {str(exc)[:300]}`")
    return answer + sources_line


def answer_hr_query(query):
    """Kept for backward compatibility with the original code."""
    return answer_from_kb(query, mode="HR")
