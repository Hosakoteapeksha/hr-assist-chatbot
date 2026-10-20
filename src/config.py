"""Central configuration.

Settings are read from (in this order):
  1. Real environment variables
  2. The local .env file            -> used when running in VS Code
  3. Streamlit secrets (st.secrets) -> used on Streamlit Community Cloud
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SETTING_KEYS = (
    "GOOGLE_API_KEY",
    "DATABASE_URL",
    "GEMINI_MODEL",
    "EMBEDDING_MODEL",
    "APP_NAME",
    "COMPANY_NAME",
    # Login
    "ADMIN_EMAIL",
    "ADMIN_PASSWORD",
    "DEFAULT_EMPLOYEE_PASSWORD",
    "SHOW_DEMO_LOGINS",
    # Email (SMTP) - e.g. Gmail with an App Password
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USER",
    "SMTP_PASSWORD",
    "SMTP_FROM",
    "HR_EMAIL",
    "APP_URL",
)


def _load_settings():
    # 1) Local .env file (VS Code / local run). Does not override real env vars.
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env", override=False)
    except Exception:
        pass

    # 2) Streamlit Cloud secrets. Only fills values that are still empty.
    try:
        import streamlit as st
        secrets = st.secrets
        for key in SETTING_KEYS:
            if not os.getenv(key, "").strip() and key in secrets:
                os.environ[key] = str(secrets[key])
    except Exception:
        # No secrets.toml locally -> that's fine, .env is used instead.
        pass


def _get(key, default=""):
    value = os.getenv(key, default) or default
    # Remove accidental spaces / quotes copied around keys
    return str(value).strip().strip('"').strip("'")


_load_settings()

GOOGLE_API_KEY = _get("GOOGLE_API_KEY")
DATABASE_URL = _get("DATABASE_URL")
GEMINI_MODEL = _get("GEMINI_MODEL", "gemini-2.5-flash")
EMBEDDING_MODEL = _get("EMBEDDING_MODEL", "models/gemini-embedding-001")
APP_NAME = _get("APP_NAME", "HR Assist")
COMPANY_NAME = _get("COMPANY_NAME", "Demo Company")

# ---- Login ----
# The HR admin account. Its email is created automatically on first start.
ADMIN_EMAIL = _get("ADMIN_EMAIL", "hr.admin@company.com").lower()
ADMIN_PASSWORD = _get("ADMIN_PASSWORD", "Admin@123")
# Starting password for the employees in data/employees.csv (they can change it in My Profile).
DEFAULT_EMPLOYEE_PASSWORD = _get("DEFAULT_EMPLOYEE_PASSWORD", "Welcome@123")
SHOW_DEMO_LOGINS = _get("SHOW_DEMO_LOGINS", "1") != "0"

# ---- Email (SMTP) ----
SMTP_HOST = _get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(_get("SMTP_PORT", "587") or 587)
SMTP_USER = _get("SMTP_USER")
SMTP_PASSWORD = _get("SMTP_PASSWORD").replace(" ", "")   # Gmail app passwords are shown with spaces
SMTP_FROM = _get("SMTP_FROM") or SMTP_USER
# Where new requests are emailed. If empty, all HR admin accounts are emailed.
HR_EMAIL = _get("HR_EMAIL")
APP_URL = _get("APP_URL", "https://hr-assist-apeksha.streamlit.app")

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".docx"}

# --------------------------------------------------------------------------- #
# Where runtime files (tickets.db, vector index, uploads) are written.
# On Streamlit Community Cloud the code folder (/mount/src/...) is not a safe
# place for SQLite, so runtime files go to the system temp folder instead.
# Locally (VS Code) everything stays inside the project folder as before.
# --------------------------------------------------------------------------- #
import shutil
import tempfile

BUNDLED_KNOWLEDGE_DIR = ROOT / "data" / "knowledge_base"   # PDFs committed to GitHub
EMPLOYEES_CSV = ROOT / "data" / "employees.csv"            # employee dataset (seed users)


def _is_writable(folder: Path) -> bool:
    try:
        folder.mkdir(parents=True, exist_ok=True)
        probe = folder / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except Exception:
        return False


ON_STREAMLIT_CLOUD = str(ROOT).replace("\\", "/").startswith("/mount/src")
USE_TEMP_STORAGE = (
    ON_STREAMLIT_CLOUD
    or os.getenv("FORCE_TEMP_STORAGE", "") == "1"
    or not _is_writable(ROOT / "data")
)

if USE_TEMP_STORAGE:
    RUNTIME_ROOT = Path(tempfile.gettempdir()) / "hr_assist_runtime"
else:
    RUNTIME_ROOT = ROOT

DATA_DIR = RUNTIME_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
CHROMA_DIR = str(RUNTIME_ROOT / ".chroma")
KNOWLEDGE_DIR = str(DATA_DIR / "knowledge_base")

def sync_bundled_documents():
    """In temp storage, keep a copy of the documents committed to GitHub
    (new or changed files are copied over automatically)."""
    if not USE_TEMP_STORAGE:
        return
    Path(KNOWLEDGE_DIR).mkdir(parents=True, exist_ok=True)
    if not BUNDLED_KNOWLEDGE_DIR.is_dir():
        return
    for src_file in BUNDLED_KNOWLEDGE_DIR.iterdir():
        if not src_file.is_file():
            continue
        dest = Path(KNOWLEDGE_DIR) / src_file.name
        try:
            if not dest.exists() or dest.stat().st_size != src_file.stat().st_size:
                shutil.copy2(src_file, dest)
        except Exception as copy_error:
            print(f"Could not copy {src_file.name}: {copy_error}")


sync_bundled_documents()
