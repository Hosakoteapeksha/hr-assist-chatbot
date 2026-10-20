"""Business actions used by both the UI and the chatbot."""
from .database import create_request, decide_request
from .notifications import notify_employee_decision, notify_hr_new_request


def submit_request(user, category, subject, details="", priority="Medium", leave_type="",
                   start_date=None, end_date=None, days=0, source="form"):
    """Save a request and email HR. Returns (request, email_ok, email_message)."""
    req = create_request(user, category, subject, details, priority, leave_type,
                         start_date, end_date, days, source)
    try:
        ok, msg = notify_hr_new_request(req)
    except Exception as exc:  # never lose a request because of email problems
        ok, msg = False, f"Email could not be sent ({exc})."
    return req, ok, msg


def decide_and_notify(pk, status, comment, admin_email):
    """Approve/reject a request and email the employee. Returns (request, email_ok, email_message)."""
    req = decide_request(pk, status, comment, admin_email)
    try:
        ok, msg = notify_employee_decision(req)
    except Exception as exc:
        ok, msg = False, f"Email could not be sent ({exc})."
    return req, ok, msg
