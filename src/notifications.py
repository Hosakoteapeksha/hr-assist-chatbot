"""Email notifications (SMTP). Works with Gmail (App Password), Outlook/Office 365, Zoho, etc.

Every email attempt is saved in the email_log table, so HR can see it in the admin panel
even when SMTP is not configured yet.
"""
import smtplib
import ssl
from email.message import EmailMessage
from html import escape

from .config import (APP_NAME, APP_URL, COMPANY_NAME, HR_EMAIL, SMTP_FROM, SMTP_HOST,
                     SMTP_PASSWORD, SMTP_PORT, SMTP_USER)
from .database import admin_emails, log_email


def email_configured():
    return bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD)


def hr_recipients():
    if HR_EMAIL:
        return [e.strip() for e in HR_EMAIL.replace(";", ",").split(",") if e.strip()]
    return admin_emails()


def send_email(to_list, subject, text, html=None, request_id=""):
    """Send one email. Returns (ok, message)."""
    to_list = [t for t in (to_list or []) if t]
    to_str = ", ".join(to_list)
    if not to_list:
        log_email("-", subject, "FAILED", "No recipient address.", request_id)
        return False, "No recipient address."
    if not email_configured():
        log_email(to_str, subject, "NOT_CONFIGURED",
                  "SMTP settings are missing - the request is saved and visible in the admin panel.", request_id)
        return False, "Email is not configured yet (the request is saved in the admin panel)."
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{APP_NAME} <{SMTP_FROM}>"
    msg["To"] = to_str
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")
    try:
        if SMTP_PORT == 465:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=20,
                                  context=ssl.create_default_context()) as server:
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.send_message(msg)
        else:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as server:
                server.ehlo()
                if server.has_extn("starttls"):
                    server.starttls(context=ssl.create_default_context())
                    server.ehlo()
                if SMTP_USER and SMTP_PASSWORD:
                    server.login(SMTP_USER, SMTP_PASSWORD)
                server.send_message(msg)
        log_email(to_str, subject, "SENT", "", request_id)
        return True, f"Email sent to {to_str}."
    except Exception as exc:
        err = f"{type(exc).__name__}: {exc}"
        log_email(to_str, subject, "FAILED", err, request_id)
        return False, f"Email could not be sent ({err})."


def _html_table(rows):
    cells = "".join(
        f"<tr><td style='padding:6px 12px;color:#5b7460;font-weight:600'>{escape(str(k))}</td>"
        f"<td style='padding:6px 12px'>{escape(str(v))}</td></tr>" for k, v in rows if v not in (None, ""))
    return f"<table style='border-collapse:collapse;font-family:Arial,sans-serif;font-size:14px'>{cells}</table>"


def _request_rows(req):
    rows = [("Request ID", req["request_id"]), ("Employee", f"{req['user_name']} ({req['user_email']})"),
            ("Department", req.get("department", "")), ("Category", req["category"]),
            ("Subject", req["subject"]), ("Priority", req["priority"])]
    if req["category"] == "Leave":
        rows += [("Leave type", req["leave_type"]),
                 ("From", req["start_date"].strftime("%d %b %Y") if req.get("start_date") else ""),
                 ("To", req["end_date"].strftime("%d %b %Y") if req.get("end_date") else ""),
                 ("Working days", f"{req['days']:g}")]
    rows += [("Details", req.get("details", "")), ("Submitted", req["created_at"]),
             ("Raised from", "Chatbot" if req.get("source") == "chat" else "Request form")]
    return rows


def notify_hr_new_request(req):
    """Email HR about a new request/ticket."""
    subject = f"[{APP_NAME}] New {req['category']} request {req['request_id']} from {req['user_name']}"
    rows = _request_rows(req)
    text = (f"A new request was submitted in {APP_NAME} ({COMPANY_NAME}).\n\n"
            + "\n".join(f"{k}: {v}" for k, v in rows if v not in (None, ""))
            + f"\n\nReview it in the admin panel: {APP_URL}\n")
    html = (f"<div style='font-family:Arial,sans-serif'><h2 style='color:#123d2c'>New {escape(req['category'])} request</h2>"
            f"<p>A new request was submitted in <b>{escape(APP_NAME)}</b>.</p>{_html_table(rows)}"
            f"<p><a href='{APP_URL}' style='background:#174b34;color:#fff;padding:10px 16px;border-radius:8px;"
            f"text-decoration:none'>Open admin panel</a></p></div>")
    return send_email(hr_recipients(), subject, text, html, req["request_id"])


def notify_employee_decision(req):
    """Email the employee when HR approves or rejects their request."""
    word = "approved ✅" if req["status"] == "APPROVED" else "rejected ❌"
    subject = f"[{APP_NAME}] Your request {req['request_id']} was {word}"
    rows = [("Request ID", req["request_id"]), ("Category", req["category"]), ("Subject", req["subject"]),
            ("Status", req["status"].title()), ("HR comment", req.get("admin_comment", "")),
            ("Leave balance", req.get("balance_note", ""))]
    text = (f"Hello {req['user_name']},\n\nYour request {req['request_id']} ({req['subject']}) was {word}.\n\n"
            + "\n".join(f"{k}: {v}" for k, v in rows if v) + f"\n\nOpen {APP_NAME}: {APP_URL}\n")
    html = (f"<div style='font-family:Arial,sans-serif'><p>Hello {escape(req['user_name'])},</p>"
            f"<p>Your request <b>{escape(req['request_id'])}</b> was <b>{word}</b>.</p>{_html_table(rows)}</div>")
    return send_email([req["user_email"]], subject, text, html, req["request_id"])


def notify_hr_new_account(user):
    """Tell HR that an employee created an account (HR can disable it in Admin -> Employees)."""
    subject = f"[{APP_NAME}] New employee account: {user['full_name']}"
    rows = [("Name", user["full_name"]), ("Email", user["email"]), ("Department", user.get("department", "")),
            ("Designation", user.get("designation", ""))]
    text = (f"A new employee account was created in {APP_NAME}.\n\n"
            + "\n".join(f"{k}: {v}" for k, v in rows if v)
            + f"\n\nIf you don't recognise this person, disable the account in Admin > Employees: {APP_URL}\n")
    html = (f"<div style='font-family:Arial,sans-serif'><h2 style='color:#123d2c'>New employee account</h2>"
            f"{_html_table(rows)}<p>If you don't recognise this person, disable the account in "
            f"<b>Admin → Employees</b>.</p></div>")
    return send_email(hr_recipients(), subject, text, html, "ACCOUNT")


def send_test_email(to_address):
    return send_email([to_address], f"[{APP_NAME}] Test email",
                      f"This is a test email from {APP_NAME}. Email notifications are working.",
                      request_id="TEST")
