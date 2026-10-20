"""HR Assist - HR & IT agentic support chatbot with employee login and an HR admin panel."""
import importlib
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import streamlit as st

st.set_page_config(
    page_title="HR Assist",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

# After a `git push`, Streamlit Cloud re-runs app.py but can keep OLD copies of the
# src/*.py files in memory. Reload them whenever a file on disk has changed.
_SRC_MODULES = ["src.config", "src.holidays", "src.llm", "src.database", "src.auth",
                "src.notifications", "src.services", "src.rag", "src.graph"]


def _load_latest_src_modules():
    stale = False
    for name in _SRC_MODULES:
        mod = sys.modules.get(name)
        if mod is not None and getattr(mod, "_loaded_mtime", None) != os.path.getmtime(mod.__file__):
            stale = True
    for name in _SRC_MODULES:
        if stale and name in sys.modules:
            mod = importlib.reload(sys.modules[name])
        else:
            mod = importlib.import_module(name)
        mod._loaded_mtime = os.path.getmtime(mod.__file__)


_load_latest_src_modules()

import pandas as pd  # noqa: E402

from src.auth import authenticate, change_password  # noqa: E402
from src.config import (ADMIN_EMAIL, ADMIN_PASSWORD, ALLOW_SIGNUP, ALLOWED_EMAIL_DOMAINS,  # noqa: E402
                        DEFAULT_EMPLOYEE_PASSWORD, GOOGLE_API_KEY, HR_EMAIL, KNOWLEDGE_DIR, SHOW_DEMO_LOGINS)
from src.database import (CATEGORIES, IS_SQLITE, LEAVE_TYPES, create_user, get_user, init_db,  # noqa: E402
                          list_chat_log, list_email_log, list_requests, list_users, request_stats,
                          set_password, set_user_active, update_leave_balance)
from src.graph import run_chat  # noqa: E402
from src.holidays import holiday_list, upcoming_holidays, working_days  # noqa: E402
from src.llm import active_model  # noqa: E402
from src.notifications import email_configured, hr_recipients, notify_hr_new_account, send_test_email  # noqa: E402
from src.rag import (build_knowledge_base, ensure_knowledge_base, index_info,  # noqa: E402
                     knowledge_base_exists, knowledge_base_up_to_date, list_knowledge_files)
from src.services import decide_and_notify, submit_request  # noqa: E402

init_db()

# ----------------------------- Styling --------------------------------------
st.markdown(r"""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@400;500;600;700;800&display=swap');
:root { --forest:#123d2c; --forest2:#1e5a40; --leaf:#dcecdf; --mint:#f1f7f0; --ink:#17251d; --muted:#6c7c70; --line:#e0e9e0; }
html, body, [class*="css"] { font-family:'DM Sans',sans-serif; }
.stApp { background:linear-gradient(135deg,#f5f8f2 0%,#edf5ec 55%,#e3efe3 100%); color:var(--ink); }
[data-testid="stHeader"] { background:rgba(245,248,242,.88); }
.block-container { padding-top:3.5rem; padding-bottom:2.5rem; max-width:1440px; }
section[data-testid="stSidebar"] { background:linear-gradient(180deg,#103b2a,#092c20); border-right:1px solid rgba(255,255,255,.08); }
section[data-testid="stSidebar"] * { color:#f2f8f1 !important; }
section[data-testid="stSidebar"] [data-testid="stRadio"] label { padding:.5rem .7rem; border-radius:12px; margin:.08rem 0; }
section[data-testid="stSidebar"] [data-testid="stRadio"] label:hover { background:rgba(255,255,255,.10); }
section[data-testid="stSidebar"] hr { border-color:rgba(255,255,255,.15); }
section[data-testid="stSidebar"] div.stButton > button { background:rgba(255,255,255,.08); border-color:rgba(255,255,255,.25); }
.brand { display:flex; align-items:center; gap:10px; padding:8px 4px 18px; font-family:Manrope,sans-serif; font-weight:800; font-size:1.25rem; letter-spacing:-.4px; }
.brand-mark { display:grid; place-items:center; width:35px;height:35px;border-radius:12px;background:#d8edda;color:#17452f;font-size:20px; }
.eyebrow { color:#50755c; text-transform:uppercase; font-weight:700; font-size:.73rem; letter-spacing:1.4px; }
.hero { background:linear-gradient(105deg,rgba(255,255,255,.93),rgba(231,243,228,.88)); border:1px solid #dce9dc; border-radius:24px; padding:26px 32px; box-shadow:0 12px 35px rgba(24,65,40,.06); margin-bottom:20px; }
.hero h1 { font-family:Manrope,sans-serif; color:#14251b; font-size:2rem; line-height:1.2; margin:.3rem 0 .45rem; letter-spacing:-1.1px; }
.hero p { color:#5b7460; font-size:1rem; margin:0; }
.section-title { font-family:Manrope,sans-serif; font-size:1.1rem; font-weight:800; color:#1b2c21; margin:1.2rem 0 .7rem; }
.feature-card { background:rgba(255,255,255,.9); border:1px solid #dfe9df; border-radius:17px; padding:16px; min-height:88px; box-shadow:0 6px 18px rgba(20,60,35,.04); }
.feature-icon { display:inline-grid; place-items:center; width:38px;height:38px;border-radius:12px;background:#e0f0df;font-size:20px;margin-bottom:9px; }
.feature-card h3 { font-size:.98rem; margin:0 0 4px; color:#203327; font-weight:800; }
.feature-card p { font-size:.8rem; color:#718074; margin:0; }
div.stButton > button { border-radius:12px; border:1px solid #d5e5d6; background:#fff; color:#234832; font-weight:700; padding:.5rem 1rem; transition:all .15s ease; min-height:2.6rem; }
div.stButton > button:hover { border-color:#6c9d77; color:#123d2c; background:#eff7ee; }
div.stButton > button[kind="primary"], div[data-testid="stFormSubmitButton"] > button { background:#174b34; color:white; border-color:#174b34; }
div.stButton > button[kind="primary"]:hover { background:#236344; color:white; }
[data-testid="stChatMessage"] { background:rgba(255,255,255,.84); border:1px solid #e0e9df; border-radius:16px; padding:12px 14px; }
[data-testid="stMetric"] { background:rgba(255,255,255,.85); border:1px solid #dfe9df; padding:14px 16px; border-radius:16px; }
[data-testid="stMetricLabel"] { color:#66796b; }
hr { border-color:#dfe9df; }
.small-muted { color:#728275; font-size:.86rem; }
.badge { display:inline-block; padding:2px 10px; border-radius:999px; font-size:.74rem; font-weight:800; letter-spacing:.3px; }
.badge-PENDING { background:#fff2cc; color:#7a5200; } .badge-APPROVED { background:#dff3e4; color:#17633a; } .badge-REJECTED { background:#fde2e1; color:#a1271f; }
.holiday-next { background:#174b34; color:#fff; border-radius:18px; padding:18px 22px; }
.holiday-next b { font-size:1.25rem; } .holiday-next span { opacity:.85; }
.login-hero { text-align:center; padding:10px 0 6px; }
.login-hero .brand-mark { width:56px; height:56px; font-size:30px; margin:0 auto 10px; border-radius:16px; }
.login-hero h1 { font-family:Manrope,sans-serif; font-size:2rem; color:#14251b; margin:0; letter-spacing:-1px; }
.login-hero p { color:#5b7460; margin:.3rem 0 0; }
@media(max-width:700px){ .hero{padding:22px 20px}.hero h1{font-size:1.6rem}.block-container{padding-left:1rem;padding-right:1rem} }
</style>
""", unsafe_allow_html=True)


# ----------------------------- Helpers --------------------------------------
EMPLOYEE_PAGES = ["Home", "Chat", "Raise a Request", "My Requests", "Holidays", "Policies",
                  "Knowledge Base", "My Profile"]
ADMIN_PAGES = ["Admin Dashboard", "All Requests", "Employees", "Knowledge Base", "Email Log",
               "Chat Insights", "Chat", "Holidays", "My Profile", "Settings"]


def hero(eyebrow, title, text):
    st.markdown(f'<div class="hero"><div class="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{text}</p></div>',
                unsafe_allow_html=True)


def feature(icon, title, desc):
    st.markdown(f'<div class="feature-card"><div class="feature-icon">{icon}</div><h3>{title}</h3><p>{desc}</p></div>',
                unsafe_allow_html=True)


def badge(status):
    return f'<span class="badge badge-{status}">{status.title()}</span>'


def flash(kind, text):
    st.session_state.setdefault("flash", []).append((kind, text))


def show_flash():
    for kind, text in st.session_state.pop("flash", []):
        getattr(st, kind)(text)


def navigate(page, prompt=None):
    st.session_state["nav_page"] = page
    if prompt:
        st.session_state["pending_prompt"] = prompt


def goto(page):
    """Switch page from normal code (not a button callback)."""
    st.session_state["_goto"] = page
    st.rerun()


def go_button(label, page, key, prompt=None, type="secondary"):
    return st.button(label, key=key, on_click=navigate, args=(page, prompt), type=type, width="stretch")


def email_status_text(ok, msg):
    return "HR has been notified by email ✅" if ok else f"Saved for HR in the admin panel. ({msg})"


def logout():
    for key in list(st.session_state.keys()):
        del st.session_state[key]


# ----------------------------- Login ----------------------------------------
def login_view():
    st.markdown("<style>section[data-testid='stSidebar'],[data-testid='stSidebarCollapsedControl']"
                "{display:none !important}</style>", unsafe_allow_html=True)
    _, mid, _ = st.columns([1, 1.25, 1])
    with mid:
        st.markdown('<div class="login-hero"><div class="brand-mark">🌿</div><h1>HR Assist</h1>'
                    '<p>Your HR &amp; IT companion · please sign in</p></div>', unsafe_allow_html=True)
        with st.container(border=True):
            tabs = st.tabs(["Log in", "Create account"] if ALLOW_SIGNUP else ["Log in"])
            with tabs[0]:
                with st.form("login_form"):
                    email = st.text_input("Email ID", placeholder="you@company.com")
                    password = st.text_input("Password", type="password")
                    submitted = st.form_submit_button("Log in", type="primary", width="stretch")
                if submitted:
                    user, error = authenticate(email, password)
                    if user:
                        st.session_state["user"] = user
                        st.session_state["nav_page"] = "Admin Dashboard" if user["role"] == "admin" else "Home"
                        st.rerun()
                    else:
                        st.error(error + (" New here? Use the Create account tab."
                                          if ALLOW_SIGNUP and error.startswith("Incorrect") else ""))
                st.caption("Forgot your password? Contact HR — they can reset it from the admin panel.")
            if ALLOW_SIGNUP:
                with tabs[1]:
                    signup_form()
        if SHOW_DEMO_LOGINS:
            with st.expander("Demo accounts"):
                rows = []
                if ADMIN_EMAIL == "hr.admin@company.com" and ADMIN_PASSWORD == "Admin@123":
                    rows.append({"Role": "HR Admin", "Email": "hr.admin@company.com", "Password": "Admin@123"})
                if DEFAULT_EMPLOYEE_PASSWORD == "Welcome@123":
                    rows += [{"Role": "Employee", "Email": e, "Password": "Welcome@123"}
                             for e in ("apeksha@company.com", "priya.sharma@company.com", "arjun.reddy@company.com")]
                if rows:
                    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
                else:
                    st.caption("Ask HR for your login details.")


def signup_form():
    with st.form("signup_form", clear_on_submit=False):
        name = st.text_input("Full name")
        email = st.text_input("Your email ID", placeholder="you@gmail.com")
        c1, c2 = st.columns(2)
        dept = c1.selectbox("Department", ["Engineering", "Design", "IT Support", "Finance", "Sales",
                                           "Marketing", "Human Resources", "Operations", "Other"])
        desig = c2.text_input("Designation", placeholder="e.g. Software Engineer")
        pw = st.text_input("Create password (min 6 characters)", type="password")
        pw2 = st.text_input("Confirm password", type="password")
        create = st.form_submit_button("Create account", type="primary", width="stretch")
    if create:
        email_clean = (email or "").strip().lower()
        domain = email_clean.split("@")[-1] if "@" in email_clean else ""
        if not name.strip():
            st.error("Please enter your full name.")
        elif "@" not in email_clean or "." not in domain:
            st.error("Please enter a valid email ID.")
        elif ALLOWED_EMAIL_DOMAINS and domain not in ALLOWED_EMAIL_DOMAINS:
            st.error("Please use your company email (" + ", ".join("@" + d for d in ALLOWED_EMAIL_DOMAINS) + ").")
        elif pw != pw2:
            st.error("The passwords don't match.")
        else:
            try:
                user = create_user(email_clean, name, pw, "employee", dept, desig.strip())
                try:
                    notify_hr_new_account(user)
                except Exception as exc:
                    print("Could not email HR about new account:", exc)
                st.session_state["user"] = user
                st.session_state["nav_page"] = "Home"
                flash("success", f"Welcome, {user['full_name']}! Your account is ready.")
                st.rerun()
            except ValueError as exc:
                msg = str(exc)
                if "already exists" in msg:
                    msg += " Please use the Log in tab."
                st.error(msg)


if "user" not in st.session_state:
    login_view()
    st.stop()

# Refresh the logged-in user from the database (balances, role, active flag).
USER = get_user(st.session_state["user"]["email"])
if not USER or not USER["is_active"]:
    logout()
    st.rerun()
st.session_state["user"] = USER
IS_ADMIN = USER["role"] == "admin"
PAGES = ADMIN_PAGES if IS_ADMIN else EMPLOYEE_PAGES
if st.session_state.get("nav_page") not in PAGES:
    st.session_state["nav_page"] = PAGES[0]

# Build / refresh the knowledge base automatically (no button needed).
AUTO_BUILD_ERROR = ""
if not knowledge_base_up_to_date():
    with st.spinner("Preparing the HR knowledge base (about 20 seconds the first time)..."):
        _ok, AUTO_BUILD_ERROR = ensure_knowledge_base()

# ----------------------------- Sidebar --------------------------------------
with st.sidebar:
    st.markdown('<div class="brand"><span class="brand-mark">🌿</span><span>HR Assist</span></div>',
                unsafe_allow_html=True)
    if st.session_state.get("_goto") in PAGES:
        st.session_state["nav_page"] = st.session_state.pop("_goto")
    page = st.radio("Navigation", PAGES, key="nav_page", label_visibility="collapsed")
    st.markdown("---")
    initial = (USER["full_name"] or "?")[0].upper()
    role_label = "HR Admin" if IS_ADMIN else (USER["designation"] or "Employee")
    st.markdown(
        "<div style='display:flex;align-items:center;gap:10px;padding:6px 3px'>"
        f"<span style='display:grid;place-items:center;background:#8fc59b;color:#123d2c;width:34px;height:34px;"
        f"border-radius:50%;font-weight:800'>{initial}</span>"
        f"<div><b>{USER['full_name']}</b><div style='font-size:12px;opacity:.75'>{role_label}</div>"
        f"<div style='font-size:11px;opacity:.6'>{USER['email']}</div></div></div>",
        unsafe_allow_html=True)
    if st.button("Log out", key="logout_btn", width="stretch"):
        logout()
        st.rerun()

show_flash()


# ----------------------------- Chat -----------------------------------------
def run_prompt(prompt):
    prompt = (prompt or "").strip()
    if not prompt:
        return
    st.session_state.setdefault("messages", []).append({"role": "user", "content": prompt})
    try:
        with st.spinner("Finding the right support..."):
            result = run_chat(prompt, USER)
        st.session_state.messages.append({"role": "assistant",
                                          "content": result.get("answer", "Sorry, please try again.")})
    except Exception as exc:
        st.session_state.messages.append({"role": "assistant",
                                          "content": f"I couldn't process that request. Details: `{exc}`"})


def page_chat():
    hero("Ask · Explore · Resolve", "Chat with HR Assist",
         "Ask about leave, holidays, policies, payroll or your own requests — or describe an IT problem.")
    c1, c2 = st.columns([5, 1])
    with c2:
        if st.button("Clear chat", key="clear_chat", width="stretch"):
            st.session_state.messages = []
            st.rerun()
    pending = st.session_state.pop("pending_prompt", None)
    if pending:
        run_prompt(pending)
    if not st.session_state.get("messages"):
        st.caption("Try: *Which holidays are there next month?* · *What is my leave balance?* · "
                   "*How do I apply for sick leave?* · *My VPN is not connecting*")
    for message in st.session_state.get("messages", []):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    prompt = st.chat_input("Ask anything about HR or IT...")
    if prompt:
        run_prompt(prompt)
        st.rerun()


# ----------------------------- Employee pages -------------------------------
def page_home():
    first = USER["full_name"].split()[0]
    left, right = st.columns([1.6, 1], vertical_alignment="center")
    with left:
        hero("Your workplace, made simpler", f"Hi {first} 👋",
             "Ask questions, raise requests and track everything in one place.")
        st.text_input("Question", placeholder="⌕  Ask anything about HR or IT...",
                      label_visibility="collapsed", key="home_query")

        def _ask():
            q = (st.session_state.get("home_query") or "").strip()
            if q:
                navigate("Chat", q)
        st.button("Ask your question  →", type="primary", key="home_ask", on_click=_ask)
    with right:
        nxt = upcoming_holidays(date.today(), 1)
        if nxt:
            d, name, day = nxt[0]
            days_left = (d - date.today()).days
            when = "today 🎉" if days_left == 0 else f"in {days_left} day(s)"
            st.markdown(f'<div class="holiday-next"><span>Next public holiday</span><br><b>{name}</b><br>'
                        f'<span>{d:%d %B %Y} · {day} · {when}</span></div>', unsafe_allow_html=True)
    pending = [r for r in list_requests(user_email=USER["email"]) if r["status"] == "PENDING"]
    a, b, c, d_ = st.columns(4)
    a.metric("Annual leave left", f"{USER['annual_leave']:g}")
    b.metric("Sick leave left", f"{USER['sick_leave']:g}")
    c.metric("Casual leave left", f"{USER['casual_leave']:g}")
    d_.metric("Pending requests", len(pending))

    st.markdown('<div class="section-title">How can we help today?</div>', unsafe_allow_html=True)
    cards = [("💬", "Chat", "Ask HR & IT questions", "Chat"),
             ("📝", "Raise a Request", "Leave, WFH, IT, payroll…", "Raise a Request"),
             ("📋", "My Requests", "Track status & HR replies", "My Requests"),
             ("📅", "Holidays", "Public holiday calendar", "Holidays")]
    cols = st.columns(4)
    for i, (icon, title, desc, target) in enumerate(cards):
        with cols[i]:
            feature(icon, title, desc)
            go_button(f"Open {title} →", target, f"home_card_{i}", type="primary")

    st.markdown('<div class="section-title">Popular questions</div>', unsafe_allow_html=True)
    quick = [("Holidays next month", "Which holidays are there next month?"),
             ("My leave balance", "What is my leave balance?"),
             ("How to apply for leave", "How do I apply for leave?"),
             ("Work from home rules", "What is the work from home policy?"),
             ("Reset my password", "How do I reset my password?"),
             ("Expense claims", "How do I claim expense reimbursement?")]
    qcols = st.columns(3)
    for i, (label, q) in enumerate(quick):
        with qcols[i % 3]:
            go_button(label + " →", "Chat", f"quick_{i}", prompt=q)


def page_raise_request():
    hero("Support request", "Raise a Request",
         "Your request is saved and emailed to HR. You'll get an email when HR approves or rejects it.")
    if st.session_state.pop("_clear_rq", False):
        st.session_state.pop("rq_details", None)
    category = st.selectbox("What do you need?", CATEGORIES, key="rq_category")
    leave_type, start, end, days, balance = "", None, None, 0, 0
    today = date.today()
    if category in ("Leave", "Work From Home"):
        if category == "Leave":
            leave_type = st.selectbox("Leave type", LEAVE_TYPES, key="rq_leave_type")
        c1, c2 = st.columns(2)
        start = c1.date_input("From", value=today + timedelta(days=1), key="rq_start", format="DD/MM/YYYY")
        end = c2.date_input("To", value=start, key="rq_end", format="DD/MM/YYYY")
        days = working_days(start, end)
        if category == "Leave":
            field = {"Annual Leave": "annual_leave", "Sick Leave": "sick_leave", "Casual Leave": "casual_leave"}[leave_type]
            balance = USER[field]
            st.info(f"**{days} working day(s)** (weekends and public holidays are not counted) · "
                    f"your {leave_type} balance: **{balance:g}** day(s)")
        else:
            st.info(f"**{days} working day(s)** of work from home.")
    default_subject = ""
    if category == "Leave" and start:
        default_subject = f"{leave_type}: {start:%d %b} – {end:%d %b %Y}"
    elif category == "Work From Home" and start:
        default_subject = f"Work from home: {start:%d %b} – {end:%d %b %Y}"
    subject = st.text_input("Subject", value=default_subject, key=f"rq_subject_{category}_{start}_{end}_{leave_type}",
                            placeholder="Short title, e.g. Laptop not connecting to office Wi-Fi")
    details = st.text_area("Details", key="rq_details", height=120,
                           placeholder="Add the reason or describe the problem.")
    priority = st.selectbox("Priority", ["Low", "Medium", "High", "Urgent"], index=1, key="rq_priority")

    if st.button("Submit request", type="primary", key="rq_submit"):
        errors = []
        if not subject.strip():
            errors.append("Please add a subject.")
        if category in ("Leave", "Work From Home") and end < start:
            errors.append("The 'To' date must be on or after the 'From' date.")
        elif category in ("Leave", "Work From Home") and days == 0:
            errors.append("The selected dates contain no working days.")
        if category == "Leave" and days > balance:
            errors.append(f"You have only {balance:g} {leave_type} day(s) left.")
        if category not in ("Leave", "Work From Home") and not details.strip():
            errors.append("Please add some details.")
        if errors:
            for e in errors:
                st.error(e)
        else:
            with st.spinner("Submitting and notifying HR..."):
                req, ok, msg = submit_request(USER, category, subject, details, priority, leave_type,
                                              start, end, days)
            flash("success", f"Request **{req['request_id']}** submitted. {email_status_text(ok, msg)}")
            st.session_state["_clear_rq"] = True
            goto("My Requests")


def render_request_card(r, admin=False):
    with st.container(border=True):
        top_l, top_r = st.columns([4, 1])
        who = f" · {r['user_name']} ({r['department']})" if admin else ""
        top_l.markdown(f"**{r['request_id']}** · {r['category']}{who}")
        top_r.markdown(badge(r["status"]), unsafe_allow_html=True)
        st.markdown(f"**{r['subject']}**")
        if r["start_date"]:
            extra = f" · {r['leave_type']}" if r["leave_type"] else ""
            st.caption(f"📅 {r['start_date']:%d %b %Y} → {r['end_date']:%d %b %Y} · "
                       f"{r['days']:g} working day(s){extra}")
        if r["details"]:
            st.write(r["details"])
        if r["admin_comment"]:
            st.info(f"HR comment: {r['admin_comment']}")
        st.caption(f"Priority: {r['priority']} · Raised: {r['created_at']} via "
                   f"{'chatbot' if r['source'] == 'chat' else 'form'}"
                   + (f" · Decided by {r['decided_by']} on {r['updated_at']}" if r["decided_by"] else ""))


def page_my_requests():
    hero("Track your support", "My Requests", "Every request you raised, with its status and HR's reply.")
    reqs = list_requests(user_email=USER["email"])
    if not reqs:
        st.info("You haven't raised any requests yet.")
        go_button("Raise a request →", "Raise a Request", "myreq_raise", type="primary")
        return
    status = st.radio("Show", ["All", "PENDING", "APPROVED", "REJECTED"], horizontal=True,
                      format_func=lambda s: s.title(), key="myreq_filter")
    shown = [r for r in reqs if status == "All" or r["status"] == status]
    st.caption(f"{len(shown)} request(s)")
    for r in shown:
        render_request_card(r)


def page_holidays():
    hero("Plan ahead", "Holiday Calendar 📅",
         "Government of India gazetted public holidays (DoPT list for Central Government offices).")
    upcoming = upcoming_holidays(date.today(), 3)
    if upcoming:
        cols = st.columns(len(upcoming))
        for col, (d, name, day) in zip(cols, upcoming):
            col.metric(name, f"{d:%d %b %Y}", f"{day} · in {(d - date.today()).days} day(s)", delta_color="off")
    years = sorted({d.year for d, _, _ in holiday_list()})
    default_year = date.today().year if date.today().year in years else years[0]
    year = st.radio("Year", years, index=years.index(default_year), horizontal=True, key="hol_year")
    rows = [{"Date": d.strftime("%d %b %Y"), "Day": day, "Holiday": name,
             "Status": "Upcoming" if d >= date.today() else "Past"} for d, name, day in holiday_list(year)]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", height=640)
    st.caption("Dates of Id-ul-Fitr, Bakrid, Muharram and Milad-un-Nabi depend on the moon and may change. "
               "Restricted (optional) holidays: up to 2 per year — request them under Holiday Query.")
    go_button("Ask the assistant about holidays →", "Chat", "hol_ask", prompt="Which holidays are there next month?")


def page_policies():
    hero("Guidance at your fingertips", "Policies & Guidelines", "Pick a topic and the assistant answers from the company documents.")
    topics = [("🌴", "Leave", "Types, balances, how to apply", "Explain the leave policy and how to apply for leave."),
              ("📅", "Public holidays", "2026–2027 calendar", "Which public holidays are there in the next two months?"),
              ("🏠", "Work from home", "Rules and approval", "What is the work from home policy?"),
              ("💳", "Expenses", "Reimbursement and claims", "How do I claim expense reimbursement?"),
              ("💰", "Payroll", "Salary date, payslips", "When is salary credited and how do I get my payslip?"),
              ("🖥️", "IT support", "Response times, self-help", "What are the IT support response times?")]
    for row in range(2):
        cols = st.columns(3)
        for i in range(3):
            icon, title, desc, prompt = topics[row * 3 + i]
            with cols[i]:
                feature(icon, title, desc)
                go_button("Ask about this →", "Chat", f"policy_{row}_{i}", prompt=prompt, type="primary")


def page_profile():
    hero("Your account", "My Profile", "Your details, leave balance and password.")
    a, b = st.columns([1.2, 1])
    with a:
        with st.container(border=True):
            st.markdown(f"**{USER['full_name']}**  \n{USER['designation']} · {USER['department']}")
            st.caption(f"Employee ID: {USER['employee_code'] or '-'} · Manager: {USER['manager'] or '-'}")
            st.caption(f"Email: {USER['email']} · Role: {'HR Admin' if IS_ADMIN else 'Employee'} · "
                       f"Last login: {USER['last_login']}")
        m1, m2, m3 = st.columns(3)
        m1.metric("Annual leave", f"{USER['annual_leave']:g}")
        m2.metric("Sick leave", f"{USER['sick_leave']:g}")
        m3.metric("Casual leave", f"{USER['casual_leave']:g}")
    with b:
        with st.container(border=True):
            st.markdown("**Change password**")
            with st.form("pw_form", clear_on_submit=True):
                cur = st.text_input("Current password", type="password")
                new = st.text_input("New password (min 6 characters)", type="password")
                new2 = st.text_input("Confirm new password", type="password")
                ok = st.form_submit_button("Update password", type="primary")
            if ok:
                if new != new2:
                    st.error("The new passwords don't match.")
                else:
                    try:
                        change_password(USER["email"], cur, new)
                        st.success("Password updated.")
                    except ValueError as exc:
                        st.error(str(exc))


def page_knowledge_base():
    hero("Company knowledge", "Knowledge Base 📚",
         "The documents the assistant answers from. New or changed documents are picked up automatically.")
    if AUTO_BUILD_ERROR:
        st.error(f"Knowledge base problem: {AUTO_BUILD_ERROR}")
    info = index_info()
    if knowledge_base_exists():
        backend = {"chroma": "ChromaDB", "memory": "In-memory vector store",
                   "keyword": "Keyword search"}.get(info.get("backend"), "Unknown")
        st.success(f"Knowledge base is ready · {len(info.get('files', []))} document(s) · "
                   f"{info.get('chunks', 0)} chunks · {backend} · built {info.get('built_at', '')}")
        if info.get("embedding_error"):
            st.warning("Gemini embeddings are not available, so keyword search is being used "
                       "(answers still work). Details: " + info["embedding_error"])
    else:
        st.warning("The knowledge base is not ready yet.")
    if IS_ADMIN:
        with st.container(border=True):
            st.markdown("**Add documents** (PDF, TXT, DOCX)")
            uploads = st.file_uploader("Upload HR or IT policy documents", type=["pdf", "txt", "docx"],
                                       accept_multiple_files=True, label_visibility="collapsed")
            if uploads and st.button("Save and update knowledge base", type="primary", key="save_uploads"):
                base = Path(KNOWLEDGE_DIR)
                base.mkdir(parents=True, exist_ok=True)
                for up in uploads:
                    (base / Path(up.name).name).write_bytes(up.getvalue())
                with st.spinner("Updating the knowledge base..."):
                    ok, err = ensure_knowledge_base(retry_after_seconds=0)
                (st.success if ok else st.error)("Knowledge base updated." if ok else err)
            if st.button("↻ Rebuild now", key="rebuild_kb"):
                with st.spinner("Rebuilding..."):
                    try:
                        n = build_knowledge_base()
                        st.success(f"Rebuilt from {n} document(s).")
                    except Exception as exc:
                        st.error(str(exc))
            st.caption("On Streamlit Cloud, uploaded files are temporary. To keep a document permanently, "
                       "add it to data/knowledge_base in GitHub and push.")
    st.markdown("**Documents**")
    for p in list_knowledge_files():
        st.write("📄 " + p.name)


# ----------------------------- Admin pages ----------------------------------
def page_admin_dashboard():
    hero("HR admin panel", "Admin Dashboard", "Requests, employees and notifications at a glance.")
    users = list_users()
    stats = request_stats()
    emails = list_email_log(500)
    a, b, c, d, e, f = st.columns(6)
    a.metric("Employees", sum(1 for u in users if u["is_active"]))
    b.metric("Total requests", stats["total"])
    c.metric("Pending", stats["by_status"].get("PENDING", 0))
    d.metric("Approved", stats["by_status"].get("APPROVED", 0))
    e.metric("Rejected", stats["by_status"].get("REJECTED", 0))
    f.metric("Emails sent", sum(1 for m in emails if m["Status"] == "SENT"))
    if not email_configured():
        st.warning("Email is not configured yet, so requests are only visible here. "
                   "Add the SMTP settings (see the guide) to receive them by email.")
    left, right = st.columns([1, 1.3])
    with left:
        st.markdown('<div class="section-title">Requests by category</div>', unsafe_allow_html=True)
        if stats["by_category"]:
            st.bar_chart(pd.DataFrame({"Requests": stats["by_category"]}), color="#1e5a40", horizontal=True)
        else:
            st.caption("No requests yet.")
    with right:
        st.markdown('<div class="section-title">Waiting for you</div>', unsafe_allow_html=True)
        pending = list_requests(status="PENDING")
        if not pending:
            st.success("No pending requests 🎉")
        for r in pending[:5]:
            st.markdown(f"{badge('PENDING')} **{r['request_id']}** · {r['category']} · {r['user_name']} — {r['subject']}",
                        unsafe_allow_html=True)
        go_button("Review all requests →", "All Requests", "dash_review", type="primary")


def page_all_requests():
    hero("HR admin panel", "All Requests", "Approve or reject requests. The employee is emailed automatically.")
    f1, f2, f3 = st.columns([1, 1, 1.4])
    status = f1.selectbox("Status", ["PENDING", "APPROVED", "REJECTED", "All"], key="ar_status",
                          format_func=lambda s: s.title())
    category = f2.selectbox("Category", ["All"] + CATEGORIES, key="ar_category")
    search = f3.text_input("Search (name, email, ID, subject)", key="ar_search")
    reqs = list_requests(status=None if status == "All" else status,
                         category=None if category == "All" else category)
    if search.strip():
        s = search.lower()
        reqs = [r for r in reqs if s in " ".join([r["user_name"], r["user_email"], r["request_id"],
                                                    r["subject"]]).lower()]
    st.caption(f"{len(reqs)} request(s)")
    for r in reqs:
        render_request_card(r, admin=True)
        if r["status"] == "PENDING":
            if r["category"] == "Leave":
                emp = get_user(r["user_email"]) or {}
                field = {"Annual Leave": "annual_leave", "Sick Leave": "sick_leave",
                         "Casual Leave": "casual_leave"}.get(r["leave_type"])
                if field and field in emp:
                    st.caption(f"Employee's current {r['leave_type']} balance: {emp[field]:g} day(s)")
            comment = st.text_input("Comment to employee (optional)", key=f"cm_{r['id']}")
            c1, c2, _ = st.columns([1, 1, 3])
            for col, label, new_status, kind in ((c1, "✓ Approve", "APPROVED", "primary"),
                                                 (c2, "✕ Reject", "REJECTED", "secondary")):
                if col.button(label, key=f"{new_status}_{r['id']}", type=kind, width="stretch"):
                    try:
                        done, ok, msg = decide_and_notify(r["id"], new_status, comment, USER["email"])
                        note = f" {done['balance_note']}" if done.get("balance_note") else ""
                        mail = "Employee notified by email ✅" if ok else f"Email not sent: {msg}"
                        flash("success", f"{done['request_id']} {new_status.lower()}.{note} {mail}")
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))


def page_employees():
    hero("HR admin panel", "Employees", "Add employees, reset passwords and manage leave balances.")
    users = list_users()
    st.dataframe(pd.DataFrame([{
        "Name": u["full_name"], "Email": u["email"], "Emp ID": u["employee_code"], "Department": u["department"],
        "Designation": u["designation"], "Role": "HR Admin" if u["role"] == "admin" else "Employee",
        "Annual": u["annual_leave"], "Sick": u["sick_leave"], "Casual": u["casual_leave"],
        "Active": "Yes" if u["is_active"] else "No", "Last login": u["last_login"]} for u in users]),
        hide_index=True, width="stretch")
    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            st.markdown("**➕ Add employee**")
            with st.form("add_emp", clear_on_submit=True):
                name = st.text_input("Full name")
                email = st.text_input("Email ID")
                c1, c2 = st.columns(2)
                dept = c1.text_input("Department")
                desig = c2.text_input("Designation")
                c3, c4 = st.columns(2)
                code = c3.text_input("Employee ID")
                role = c4.selectbox("Role", ["employee", "admin"],
                                    format_func=lambda r: "HR Admin" if r == "admin" else "Employee")
                pw = st.text_input("Starting password", value=DEFAULT_EMPLOYEE_PASSWORD, type="password")
                add = st.form_submit_button("Add employee", type="primary")
            if add:
                try:
                    u = create_user(email, name, pw, role, dept, desig, code)
                    flash("success", f"Added {u['full_name']} ({u['email']}). Share the starting password with them.")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
    with right:
        with st.container(border=True):
            st.markdown("**🛠️ Manage employee**")
            emails = [u["email"] for u in users]
            names = {u["email"]: u["full_name"] for u in users}
            sel = st.selectbox("Employee", emails, key="mg_email", format_func=lambda e: f"{names[e]} — {e}")
            u = next(x for x in users if x["email"] == sel)
            c1, c2, c3 = st.columns(3)
            an = c1.number_input("Annual", value=float(u["annual_leave"]), min_value=0.0, step=0.5, key=f"an_{sel}")
            sk = c2.number_input("Sick", value=float(u["sick_leave"]), min_value=0.0, step=0.5, key=f"sk_{sel}")
            cs = c3.number_input("Casual", value=float(u["casual_leave"]), min_value=0.0, step=0.5, key=f"cs_{sel}")
            if st.button("Save leave balance", key="save_bal"):
                update_leave_balance(sel, an, sk, cs)
                flash("success", f"Leave balance updated for {u['full_name']}.")
                st.rerun()
            npw = st.text_input("New password", type="password", key=f"npw_{sel}")
            if st.button("Reset password", key="reset_pw"):
                try:
                    set_password(sel, npw)
                    flash("success", f"Password reset for {u['full_name']}.")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
            if sel != USER["email"]:
                label = "Disable account" if u["is_active"] else "Enable account"
                if st.button(label, key="toggle_active"):
                    set_user_active(sel, not u["is_active"])
                    flash("success", f"{u['full_name']} is now {'disabled' if u['is_active'] else 'enabled'}.")
                    st.rerun()


def page_email_log():
    hero("HR admin panel", "Email Log", "Every notification the app sent (or tried to send).")
    if email_configured():
        st.success(f"Email is configured. New requests are sent to: {', '.join(hr_recipients())}")
    else:
        st.warning("Email is not configured. Add SMTP_USER, SMTP_PASSWORD and HR_EMAIL in Secrets / .env "
                   "(see STEP_BY_STEP_GUIDE.md). Until then, requests appear only in this admin panel.")
    with st.container(border=True):
        c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
        to = c1.text_input("Send a test email to", value=(HR_EMAIL.split(",")[0] if HR_EMAIL else USER["email"]))
        if c2.button("Send test email", type="primary", width="stretch"):
            ok, msg = send_test_email(to.strip())
            (st.success if ok else st.error)(msg)
    log = list_email_log()
    if log:
        st.dataframe(pd.DataFrame(log), hide_index=True, width="stretch")
    else:
        st.caption("No emails yet.")


def page_chat_insights():
    hero("HR admin panel", "Chat Insights", "What employees are asking the assistant.")
    log = list_chat_log(500)
    if not log:
        st.caption("No chat questions yet.")
        return
    counts = {}
    for row in log:
        counts[row["Type"]] = counts.get(row["Type"], 0) + 1
    cols = st.columns(len(counts))
    names = {"HR": "HR / policy questions", "IT": "IT problems", "MY_DATA": "Own balance / requests"}
    for col, (k, v) in zip(cols, sorted(counts.items())):
        col.metric(names.get(k, k), v)
    st.dataframe(pd.DataFrame(log), hide_index=True, width="stretch")


def page_settings():
    hero("Workspace", "Settings ⚙️", "Configuration and connection status.")
    info = index_info()
    a, b, c, d = st.columns(4)
    a.metric("Gemini API key", "Configured" if GOOGLE_API_KEY else "Missing")
    b.metric("Knowledge base", {"chroma": "ChromaDB", "memory": "In-memory", "keyword": "Keyword"}.get(
        info.get("backend"), "Not built"))
    c.metric("Database", "SQLite" if IS_SQLITE else "PostgreSQL")
    d.metric("Email", "Configured" if email_configured() else "Not set")
    with st.container(border=True):
        st.write(f"**AI model:** Google Gemini (`{active_model()}`)")
        st.write("**Database:** " + ("SQLite (built in)" if IS_SQLITE else "PostgreSQL (permanent)"))
        st.write("**HR notification email:** " + (", ".join(hr_recipients()) or "-"))
        if IS_SQLITE:
            st.caption("On Streamlit Community Cloud the SQLite file is temporary: requests and new employees reset "
                       "when the app restarts (the employees in data/employees.csv are always recreated). "
                       "Set DATABASE_URL to a free PostgreSQL database (Neon) to keep everything permanently.")


# ----------------------------- Router ---------------------------------------
ROUTES = {
    "Home": page_home, "Chat": page_chat, "Raise a Request": page_raise_request,
    "My Requests": page_my_requests, "Holidays": page_holidays, "Policies": page_policies,
    "Knowledge Base": page_knowledge_base, "My Profile": page_profile,
    "Admin Dashboard": page_admin_dashboard, "All Requests": page_all_requests, "Employees": page_employees,
    "Email Log": page_email_log, "Chat Insights": page_chat_insights, "Settings": page_settings,
}
ROUTES[page]()
