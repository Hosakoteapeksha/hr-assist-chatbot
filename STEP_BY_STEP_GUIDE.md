# HR Assist: Step-by-Step Guide

**What the app does**
- Employees **log in with their email and password**.
- They chat with the AI assistant, raise requests (leave, work from home, IT, holidays, payroll and more) and track them.
- **Every request is emailed to HR.**
- HR logs in to an **admin panel** to approve or reject requests. The employee is emailed automatically.

---

## 1. Logins

**Real users**
- **Employees create their own account.** On the login page, they open the **Create account** tab and enter their name, own email ID and a password. HR gets an email about every new account and can disable it in **Admin → Employees**.
- **You as HR admin, with your own email:** in Secrets (or `.env`) set
  ```toml
  ADMIN_EMAIL = "your.email@gmail.com"
  ADMIN_PASSWORD = "your-strong-password"
  SHOW_DEMO_LOGINS = "0"
  ```
  The demo admin `hr.admin@company.com` is then switched off, and the demo accounts table is hidden.
- **Optional:** `ALLOWED_EMAIL_DOMAINS = "mycompany.com"` lets only company emails sign up. Set `ALLOW_SIGNUP = "0"` if only HR should create accounts.

**Demo accounts** (for testing):

| Who | Email | Password |
|---|---|---|
| HR Admin | `hr.admin@company.com` | `Admin@123` |
| Employee | `apeksha@company.com` | `Welcome@123` |
| Employee | `priya.sharma@company.com` | `Welcome@123` |
| Employee | `arjun.reddy@company.com` (and the rest of `data/employees.csv`) | `Welcome@123` |

- The employee list (the dataset) is in **`data/employees.csv`**. Add rows there, or use **Admin → Employees → Add employee**.
- Change the default passwords with the `ADMIN_PASSWORD` and `DEFAULT_EMPLOYEE_PASSWORD` settings.
- Employees can change their own password in **My Profile**.

---

## 2. Run in VS Code

You only need these steps the first time:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
copy .env.example .env
```
Open `.env` and fill in at least `GOOGLE_API_KEY`. For email, see section 4.

Then run:
```powershell
python -m streamlit run app.py
```
Open http://localhost:8501 and log in with one of the accounts above.

---

## 3. Update GitHub and the live app

```powershell
git add .
git commit -m "Login, admin panel, email to HR"
git push
```
Streamlit Cloud updates itself in 1–2 minutes. Then press **F5** on the app.

---

## 4. Email to HR (Gmail, about 5 minutes)

**4a. Get a Gmail App Password**
1. Sign in to the Gmail account that will **send** the emails.
2. Go to https://myaccount.google.com/security and turn on **2-Step Verification** if it's off.
3. Go to https://myaccount.google.com/apppasswords. Type the name `HR Assist` and click **Create**.
4. Copy the **16-letter password** it shows.

**4b. Add the email settings**
- **Online:** on share.streamlit.io, open your app's **⋮ → Settings → Secrets** and add:
  ```toml
  SMTP_USER = "your.gmail@gmail.com"
  SMTP_PASSWORD = "abcd efgh ijkl mnop"
  HR_EMAIL = "the-hr-inbox@gmail.com"
  APP_URL = "https://hr-assist-apeksha.streamlit.app"
  ```
  Click **Save**. The app restarts by itself.
- **On your laptop:** put the same values in `.env`, without quotes.

**4c. Test it.** Log in as HR Admin, open **Email Log**, and click **Send test email**. You should see "Email sent" and receive the mail.

Without these settings the app still works fully. Requests appear in the admin panel, and the Email Log shows "NOT_CONFIGURED".

---

## 5. Keep data permanently (optional, free)

On Streamlit Cloud, the built-in SQLite database resets when the app restarts. The employees from `employees.csv` always come back, but requests and new employees don't.

To keep everything permanently:
1. Sign up at https://neon.tech (free) and create a project.
2. Copy the **connection string**. It starts with `postgresql://`.
3. In Secrets, add:
   ```toml
   DATABASE_URL = "postgresql://...your string..."
   ```
   Click **Save**.

The app creates all its tables by itself.

---

## 6. What each user sees

**Employee**
- **Home:** leave balances, the next holiday, quick questions
- **Chat:** policies, holidays, "what is my leave balance?", IT problems (creates a ticket and emails HR)
- **Raise a Request:** Leave (working days are calculated automatically, without weekends and public holidays), Work From Home, IT Support, Holiday Query, Payroll, HR Query, Other
- **My Requests:** status and HR comments
- **Holidays:** the 2026–2027 public holiday calendar
- **Policies**, **Knowledge Base**, **My Profile** (where you change your password)

**HR Admin**
- **Admin Dashboard:** counts and the pending list
- **All Requests:** approve or reject with a comment. Approved leave is deducted from the balance, and the employee is emailed.
- **Employees:** add employees, reset passwords, edit leave balances, disable accounts
- **Knowledge Base:** upload documents. The AI re-learns automatically.
- **Email Log:** every email sent, plus a test button
- **Chat Insights:** what employees are asking
- **Settings**

---

## 7. How it works

```
Employee logs in ─► Chat ─► LangGraph agent classifies the message
                     ├─ MY_DATA ─► answers from the database (leave balance, request status)
                     ├─ HR ──────► RAG: searches 6 knowledge PDFs (ChromaDB + Gemini embeddings,
                     │             keyword backup) ─► Gemini answers with sources and today's date
                     └─ IT ──────► self-help steps (RAG) + IT ticket ─► email to HR
Raise a Request ─► database ─► email to HR ─► HR approves/rejects in admin panel ─► email to employee
```

- **Frontend:** Streamlit
- **LLM:** Google Gemini (automatically switches to a backup model if one is retired)
- **Vector DB:** ChromaDB
- **Agent:** LangGraph
- **Database:** SQLAlchemy (SQLite or PostgreSQL)
- **Email:** SMTP
- **Passwords:** stored as PBKDF2-SHA256 hashes, never as plain text

**Knowledge base** (`data/knowledge_base/`):
1. Leave policy
2. Hybrid work and attendance
3. IT troubleshooting
4. Expenses
5. **Holiday Calendar 2026–2027** (Government of India gazetted holidays)
6. **Employee Handbook and Request Guide** (leave types, how to apply, WFH, IT response times, payroll, request categories)

Files 1–4 and 6 are demo policies. Replace them with your company's real documents when you have them.

---

## 8. Troubleshooting

| Problem | Fix |
|---|---|
| "Incorrect email or password" | Use the accounts in section 1. Passwords are case-sensitive. |
| Email Log shows FAILED with `535` / `Username and Password not accepted` | Use a Gmail **App Password** (section 4), not your normal password. |
| Email Log shows NOT_CONFIGURED | `SMTP_USER` or `SMTP_PASSWORD` is missing from Secrets / `.env`. |
| Requests disappeared after a restart | That's normal with SQLite on Streamlit Cloud. Use section 5. |
| The answer says "Technical details: …API key not valid" | Create a new key at aistudio.google.com and update `GOOGLE_API_KEY`. |
| Red error after `git push` | Wait 2 minutes and press F5. If it's still there: **Manage app → ⋮ → Reboot app**. |
