# 🌿 HR Assist: HR & IT Agentic Support Portal

Employees log in with their email ID and password. They:
- ask an AI assistant about leave, public holidays, work from home, expenses, payroll and IT problems (answers come from company documents via RAG)
- ask about their own leave balance and request status
- raise requests, which are **emailed to HR** automatically

HR uses an **admin panel** to approve or reject requests (the employee is emailed), manage employees and leave balances, update the knowledge base and see the email log.

**Tech stack:** Streamlit, Google Gemini, LangChain, LangGraph, ChromaDB, SQLAlchemy (SQLite/PostgreSQL), SMTP email

## Quick start
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
copy .env.example .env      # add GOOGLE_API_KEY (and the SMTP settings for email)
python -m streamlit run app.py
```
Demo logins:
- HR admin: `hr.admin@company.com` / `Admin@123`
- Employee: `apeksha@company.com` / `Welcome@123`

Full instructions (Gmail setup, permanent database, deployment) are in **[STEP_BY_STEP_GUIDE.md](STEP_BY_STEP_GUIDE.md)**.

## Datasets
- `data/employees.csv`: the employee accounts, departments and leave balances, loaded automatically.
- `data/knowledge_base/`: 6 PDFs. These are the leave, hybrid work, IT, expenses and employee handbook policies (demo), plus the **Government of India holiday calendar 2026–2027**. They're indexed automatically and re-indexed whenever a document changes.

## Security
- Passwords are stored as PBKDF2 hashes.
- Never commit `.env` or `.streamlit/secrets.toml`. Put keys in Streamlit **Secrets** instead.
- Change the default passwords before real use.
