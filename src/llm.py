from .config import GOOGLE_API_KEY, GEMINI_MODEL, EMBEDDING_MODEL

# If the configured model is retired by Google, these are tried automatically.
FALLBACK_MODELS = ["gemini-2.5-flash", "gemini-flash-latest", "gemini-2.5-flash-lite", "gemini-2.0-flash"]
_MODEL_GONE_HINTS = ("404", "not found", "not_found", "is not supported", "no longer available",
                     "has been deprecated", "unsupported model")

_llms = {}
_working_model = None
_embeddings = None


def get_llm(model=None):
    """Return a cached Gemini chat model, or None if no API key is configured."""
    if not GOOGLE_API_KEY:
        return None
    model = model or _working_model or GEMINI_MODEL
    if model not in _llms:
        from langchain_google_genai import ChatGoogleGenerativeAI
        _llms[model] = ChatGoogleGenerativeAI(
            model=model,
            temperature=0.2,
            google_api_key=GOOGLE_API_KEY,
            max_retries=2,
            timeout=60,
        )
    return _llms[model]


def _candidate_models():
    ordered = []
    for m in [_working_model, GEMINI_MODEL, *FALLBACK_MODELS]:
        if m and m not in ordered:
            ordered.append(m)
    return ordered


def invoke_llm(prompt):
    """Send a prompt to Gemini and return plain text.
    Automatically switches to a backup model if the configured one no longer exists."""
    global _working_model
    if not GOOGLE_API_KEY:
        raise RuntimeError("GOOGLE_API_KEY is missing. Add it to .env (local) or Streamlit Secrets (cloud).")
    last_error = None
    for model in _candidate_models():
        try:
            text = llm_text(get_llm(model).invoke(prompt))
            _working_model = model
            return text
        except Exception as exc:
            if any(h in str(exc).lower() for h in _MODEL_GONE_HINTS):
                print(f"Model {model} unavailable, trying the next one: {exc}")
                last_error = exc
                continue
            raise
    raise last_error


def active_model():
    return _working_model or GEMINI_MODEL


def get_embeddings():
    """Return a cached Gemini embeddings model."""
    global _embeddings
    if not GOOGLE_API_KEY:
        raise RuntimeError(
            "GOOGLE_API_KEY is missing. Add it to .env (local) or to Streamlit Secrets (cloud)."
        )
    if _embeddings is None:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        _embeddings = GoogleGenerativeAIEmbeddings(
            model=EMBEDDING_MODEL,
            google_api_key=GOOGLE_API_KEY,
        )
    return _embeddings


def llm_text(response):
    """Get plain text from an LLM response (content can be a str or a list of parts)."""
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and part.get("type", "text") == "text":
                parts.append(part.get("text", ""))
        return "".join(parts)
    return str(content)
