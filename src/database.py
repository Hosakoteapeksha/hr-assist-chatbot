"""Database (SQLAlchemy): SQLite by default, PostgreSQL when DATABASE_URL is set.

Tables
  users             employees and HR admins (login, role, leave balances)
  support_requests  every request / ticket (leave, IT, holiday, payroll, HR query, ...)
  email_log         every email the app tried to send
  chat_log          questions asked to the chatbot (for the admin's insights page)
"""
import csv
from datetime import datetime

from sqlalchemy import (Boolean, Column, Date, DateTime, Float, Integer, String, Text,
                        create_engine, func)
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import (ADMIN_EMAIL, ADMIN_PASSWORD, DATA_DIR, DATABASE_URL,
                     DEFAULT_EMPLOYEE_PASSWORD, EMPLOYEES_CSV)


# --------------------------------------------------------------------------- #
# Connection
# --------------------------------------------------------------------------- #
def _database_url():
    url = DATABASE_URL
    if not url:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{(DATA_DIR / 'hr_assist.db').as_posix()}"
    # Cloud Postgres (Neon, Supabase...) gives postgres:// or postgresql:// - use psycopg v3.
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def _make_engine(url):
    return create_engine(
        url,
        connect_args={"check_same_thread": False} if url.startswith("sqlite") else {},
        pool_pre_ping=True,
    )


URL = _database_url()
IS_SQLITE = URL.startswith("sqlite")
engine = _make_engine(URL)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
Base = declarative_base()


# --------------------------------------------------------------------------- #
# Tables
# --------------------------------------------------------------------------- #
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String(200), unique=True, nullable=False, index=True)
    full_name = Column(String(150), nullable=False)
    employee_code = Column(String(30), default="")
    department = Column(String(100), default="")
    designation = Column(String(100), default="")
    manager = Column(String(150), default="")
    role = Column(String(20), default="employee")          # "employee" or "admin"
    password_hash = Column(String(300), nullable=False)
    annual_leave = Column(Float, default=18)
    sick_leave = Column(Float, default=12)
    casual_leave = Column(Float, default=6)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    last_login = Column(DateTime, nullable=True)


class SupportRequest(Base):
    __tablename__ = "support_requests"
    id = Column(Integer, primary_key=True)
    request_id = Column(String(30), unique=True, nullable=False)
    user_email = Column(String(200), nullable=False, index=True)
    user_name = Column(String(150), default="")
    department = Column(String(100), default="")
    category = Column(String(50), nullable=False)           # Leave, IT Support, ...
    leave_type = Column(String(50), default="")
    subject = Column(String(250), nullable=False)
    details = Column(Text, default="")
    priority = Column(String(20), default="Medium")
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    days = Column(Float, default=0)
    status = Column(String(30), default="PENDING")          # PENDING / APPROVED / REJECTED
    admin_comment = Column(Text, default="")
    decided_by = Column(String(200), default="")
    source = Column(String(20), default="form")             # form / chat
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now)


class EmailLog(Base):
    __tablename__ = "email_log"
    id = Column(Integer, primary_key=True)
    to_address = Column(String(300), nullable=False)
    subject = Column(String(300), nullable=False)
    status = Column(String(30), nullable=False)             # SENT / FAILED / NOT_CONFIGURED
    error = Column(Text, default="")
    request_id = Column(String(30), default="")
    created_at = Column(DateTime, default=datetime.now)


class ChatLog(Base):
    __tablename__ = "chat_log"
    id = Column(Integer, primary_key=True)
    user_email = Column(String(200), default="")
    question = Column(Text, nullable=False)
    intent = Column(String(20), default="")
    created_at = Column(DateTime, default=datetime.now)


CATEGORIES = ["Leave", "Work From Home", "IT Support", "Holiday Query",
              "Payroll / Salary", "HR Query", "Other"]
LEAVE_TYPES = ["Annual Leave", "Sick Leave", "Casual Leave"]
_PREFIX = {"Leave": "LV", "Work From Home": "WFH", "IT Support": "IT", "Holiday Query": "HD",
           "Payroll / Salary": "PAY", "HR Query": "HRQ", "Other": "REQ"}
_BALANCE_FIELD = {"Annual Leave": "annual_leave", "Sick Leave": "sick_leave", "Casual Leave": "casual_leave"}


# --------------------------------------------------------------------------- #
# Setup
# --------------------------------------------------------------------------- #
_initialised = False


def init_db():
    """Create tables (falls back to a temp SQLite file if needed) and load the employee dataset."""
    global _initialised, engine, URL
    if _initialised:
        return
    try:
        Base.metadata.create_all(engine)
    except Exception as first_error:
        if not IS_SQLITE:
            raise
        import tempfile
        from pathlib import Path
        fallback = Path(tempfile.gettempdir()) / "hr_assist_fallback.db"
        print(f"SQLite at {URL} failed ({first_error}); using {fallback}")
        URL = f"sqlite:///{fallback.as_posix()}"
        engine = _make_engine(URL)
        SessionLocal.configure(bind=engine)
        Base.metadata.create_all(engine)
    seed_users()
    _initialised = True


def seed_users():
    """Create the accounts from data/employees.csv (and the HR admin) if they don't exist yet."""
    from .auth import hash_password
    rows = []
    try:
        with open(EMPLOYEES_CSV, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    except FileNotFoundError:
        pass
    custom_admin = ADMIN_EMAIL != "hr.admin@company.com"
    if custom_admin:
        # Your own admin email is set: don't create the demo admin account.
        rows = [r for r in rows if (r.get("role") or "").strip().lower() != "admin"
                or (r.get("email") or "").strip().lower() == ADMIN_EMAIL]
    if not any(r.get("email", "").strip().lower() == ADMIN_EMAIL for r in rows):
        rows.insert(0, {"employee_code": "HR000", "full_name": "HR Admin", "email": ADMIN_EMAIL,
                        "department": "Human Resources", "designation": "HR Manager", "role": "admin"})
    db = SessionLocal()
    try:
        if custom_admin:   # switch off the demo admin if it exists from earlier
            demo = db.query(User).filter(User.email == "hr.admin@company.com").first()
            if demo and demo.is_active:
                demo.is_active = False
        existing = {e for (e,) in db.query(User.email).all()}
        for r in rows:
            email = (r.get("email") or "").strip().lower()
            if not email or email in existing:
                continue
            role = (r.get("role") or "employee").strip().lower()
            password = ADMIN_PASSWORD if role == "admin" else DEFAULT_EMPLOYEE_PASSWORD
            db.add(User(
                email=email,
                full_name=(r.get("full_name") or email).strip(),
                employee_code=(r.get("employee_code") or "").strip(),
                department=(r.get("department") or "").strip(),
                designation=(r.get("designation") or "").strip(),
                manager=(r.get("manager") or "").strip(),
                role="admin" if role == "admin" else "employee",
                password_hash=hash_password(password),
                annual_leave=float(r.get("annual_leave") or 18),
                sick_leave=float(r.get("sick_leave") or 12),
                casual_leave=float(r.get("casual_leave") or 6),
            ))
            existing.add(email)
        db.commit()
    finally:
        db.close()


# --------------------------------------------------------------------------- #
# Users
# --------------------------------------------------------------------------- #
def user_dict(u):
    if u is None:
        return None
    return {
        "id": u.id, "email": u.email, "full_name": u.full_name, "employee_code": u.employee_code,
        "department": u.department, "designation": u.designation, "manager": u.manager,
        "role": u.role, "annual_leave": u.annual_leave, "sick_leave": u.sick_leave,
        "casual_leave": u.casual_leave, "is_active": u.is_active,
        "last_login": u.last_login.strftime("%d %b %Y, %H:%M") if u.last_login else "Never",
    }


def get_user_record(email):
    """Full row including password_hash (used by auth only)."""
    init_db()
    db = SessionLocal()
    try:
        return db.query(User).filter(func.lower(User.email) == (email or "").strip().lower()).first()
    finally:
        db.close()


def get_user(email):
    return user_dict(get_user_record(email))


def list_users():
    init_db()
    db = SessionLocal()
    try:
        return [user_dict(u) for u in db.query(User).order_by(User.role, User.full_name).all()]
    finally:
        db.close()


def admin_emails():
    init_db()
    db = SessionLocal()
    try:
        return [e for (e,) in db.query(User.email).filter(User.role == "admin", User.is_active.is_(True)).all()]
    finally:
        db.close()


def create_user(email, full_name, password, role="employee", department="", designation="",
                employee_code="", manager="", annual_leave=18, sick_leave=12, casual_leave=6):
    from .auth import hash_password
    init_db()
    email = (email or "").strip().lower()
    if not email or "@" not in email:
        raise ValueError("Please enter a valid email address.")
    if len(password or "") < 6:
        raise ValueError("Password must be at least 6 characters.")
    db = SessionLocal()
    try:
        if db.query(User).filter(func.lower(User.email) == email).first():
            raise ValueError("An account with this email already exists.")
        u = User(email=email, full_name=full_name.strip() or email, role=role,
                 department=department, designation=designation, employee_code=employee_code,
                 manager=manager, password_hash=hash_password(password),
                 annual_leave=annual_leave, sick_leave=sick_leave, casual_leave=casual_leave)
        db.add(u)
        db.commit()
        return user_dict(u)
    finally:
        db.close()


def _update_user(email, **fields):
    init_db()
    db = SessionLocal()
    try:
        u = db.query(User).filter(func.lower(User.email) == email.strip().lower()).first()
        if not u:
            raise ValueError("User not found.")
        for k, v in fields.items():
            setattr(u, k, v)
        db.commit()
        return user_dict(u)
    finally:
        db.close()


def set_password(email, new_password):
    from .auth import hash_password
    if len(new_password or "") < 6:
        raise ValueError("Password must be at least 6 characters.")
    return _update_user(email, password_hash=hash_password(new_password))


def set_user_active(email, active):
    return _update_user(email, is_active=bool(active))


def update_leave_balance(email, annual, sick, casual):
    return _update_user(email, annual_leave=float(annual), sick_leave=float(sick), casual_leave=float(casual))


def record_login(email):
    return _update_user(email, last_login=datetime.now())


# --------------------------------------------------------------------------- #
# Requests
# --------------------------------------------------------------------------- #
def request_dict(r):
    return {
        "id": r.id, "request_id": r.request_id, "user_email": r.user_email, "user_name": r.user_name,
        "department": r.department, "category": r.category, "leave_type": r.leave_type,
        "subject": r.subject, "details": r.details, "priority": r.priority,
        "start_date": r.start_date, "end_date": r.end_date, "days": r.days, "status": r.status,
        "admin_comment": r.admin_comment, "decided_by": r.decided_by, "source": r.source,
        "created_at": r.created_at.strftime("%d %b %Y, %H:%M") if r.created_at else "",
        "updated_at": r.updated_at.strftime("%d %b %Y, %H:%M") if r.updated_at else "",
    }


def create_request(user, category, subject, details="", priority="Medium", leave_type="",
                   start_date=None, end_date=None, days=0, source="form"):
    init_db()
    if category not in CATEGORIES:
        category = "Other"
    db = SessionLocal()
    try:
        last_id = db.query(func.max(SupportRequest.id)).scalar() or 0
        r = SupportRequest(
            request_id=f"{_PREFIX.get(category, 'REQ')}-{last_id + 1:04d}",
            user_email=user["email"], user_name=user.get("full_name", ""),
            department=user.get("department", ""), category=category,
            leave_type=leave_type or "", subject=subject.strip()[:250], details=details or "",
            priority=priority, start_date=start_date, end_date=end_date, days=days or 0,
            status="PENDING", source=source,
        )
        db.add(r)
        db.commit()
        return request_dict(r)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def list_requests(user_email=None, status=None, category=None):
    init_db()
    db = SessionLocal()
    try:
        q = db.query(SupportRequest)
        if user_email:
            q = q.filter(func.lower(SupportRequest.user_email) == user_email.lower())
        if status:
            q = q.filter(SupportRequest.status == status)
        if category:
            q = q.filter(SupportRequest.category == category)
        return [request_dict(r) for r in q.order_by(SupportRequest.id.desc()).all()]
    finally:
        db.close()


def get_request(pk):
    init_db()
    db = SessionLocal()
    try:
        r = db.query(SupportRequest).filter(SupportRequest.id == pk).first()
        return request_dict(r) if r else None
    finally:
        db.close()


def decide_request(pk, status, comment, admin_email):
    """Approve / reject a request. Approved leave is deducted from the employee's balance."""
    init_db()
    db = SessionLocal()
    try:
        r = db.query(SupportRequest).filter(SupportRequest.id == pk).first()
        if not r:
            raise ValueError("Request not found.")
        if r.status != "PENDING":
            raise ValueError(f"{r.request_id} was already {r.status.lower()}.")
        note = ""
        if status == "APPROVED" and r.category == "Leave" and r.leave_type in _BALANCE_FIELD:
            u = db.query(User).filter(func.lower(User.email) == r.user_email.lower()).first()
            if u:
                field = _BALANCE_FIELD[r.leave_type]
                balance = getattr(u, field) or 0
                if balance < r.days:
                    raise ValueError(f"{u.full_name} has only {balance:g} {r.leave_type} day(s) left, "
                                     f"but the request is for {r.days:g}.")
                setattr(u, field, balance - r.days)
                note = f"{r.days:g} day(s) deducted from {r.leave_type}; {balance - r.days:g} left."
        r.status = status
        r.admin_comment = comment or ""
        r.decided_by = admin_email
        r.updated_at = datetime.now()
        db.commit()
        result = request_dict(r)
        result["balance_note"] = note
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def request_stats():
    reqs = list_requests()
    by_status, by_category = {}, {}
    for r in reqs:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
        by_category[r["category"]] = by_category.get(r["category"], 0) + 1
    return {"total": len(reqs), "by_status": by_status, "by_category": by_category}


# --------------------------------------------------------------------------- #
# Email + chat logs
# --------------------------------------------------------------------------- #
def log_email(to_address, subject, status, error="", request_id=""):
    init_db()
    db = SessionLocal()
    try:
        db.add(EmailLog(to_address=to_address, subject=subject[:300], status=status,
                        error=(error or "")[:2000], request_id=request_id or ""))
        db.commit()
    finally:
        db.close()


def list_email_log(limit=200):
    init_db()
    db = SessionLocal()
    try:
        rows = db.query(EmailLog).order_by(EmailLog.id.desc()).limit(limit).all()
        return [{"Time": e.created_at.strftime("%d %b %Y, %H:%M"), "To": e.to_address, "Subject": e.subject,
                 "Status": e.status, "Request": e.request_id, "Error": e.error} for e in rows]
    finally:
        db.close()


def log_chat(user_email, question, intent):
    init_db()
    db = SessionLocal()
    try:
        db.add(ChatLog(user_email=user_email or "", question=question[:2000], intent=intent or ""))
        db.commit()
    finally:
        db.close()


def list_chat_log(limit=200):
    init_db()
    db = SessionLocal()
    try:
        rows = db.query(ChatLog).order_by(ChatLog.id.desc()).limit(limit).all()
        return [{"Time": c.created_at.strftime("%d %b %Y, %H:%M"), "Employee": c.user_email,
                 "Question": c.question, "Type": c.intent} for c in rows]
    finally:
        db.close()
