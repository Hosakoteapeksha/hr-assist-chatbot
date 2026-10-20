"""Login: password hashing (PBKDF2-SHA256, Python standard library) and authentication."""
import base64
import hashlib
import hmac
import os

_ITERATIONS = 120_000


def hash_password(password):
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    return "pbkdf2_sha256${}${}${}".format(
        _ITERATIONS, base64.b64encode(salt).decode(), base64.b64encode(digest).decode())


def verify_password(password, stored):
    try:
        _, iterations, salt_b64, digest_b64 = stored.split("$")
        digest = hashlib.pbkdf2_hmac("sha256", (password or "").encode("utf-8"),
                                     base64.b64decode(salt_b64), int(iterations))
        return hmac.compare_digest(digest, base64.b64decode(digest_b64))
    except Exception:
        return False


def authenticate(email, password):
    """Return (user_dict, error_message)."""
    from .database import get_user_record, record_login, user_dict
    email = (email or "").strip().lower()
    if not email or not password:
        return None, "Please enter your email and password."
    record = get_user_record(email)
    if record is None or not verify_password(password, record.password_hash):
        return None, "Incorrect email or password."
    if not record.is_active:
        return None, "Your account is disabled. Please contact HR."
    record_login(email)
    return user_dict(record), ""


def change_password(email, current_password, new_password):
    from .database import get_user_record, set_password
    record = get_user_record(email)
    if record is None or not verify_password(current_password, record.password_hash):
        raise ValueError("Your current password is incorrect.")
    set_password(email, new_password)
