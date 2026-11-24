"""Input validation helpers. Each returns a list of error strings (empty list = valid)."""
import re

_USERNAME = re.compile(r"^[A-Za-z0-9_]{3,30}$")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def check_username(u: str) -> list[str]:
    return [] if _USERNAME.match(u or "") else ["Username must be 3-30 characters: letters, digits or underscore."]


def check_email(e: str) -> list[str]:
    return [] if _EMAIL.match(e or "") else ["Enter a valid email address."]


def check_password(p: str) -> list[str]:
    errs = []
    if len(p or "") < 8:
        errs.append("Password must be at least 8 characters.")
    if not re.search(r"[A-Za-z]", p or "") or not re.search(r"\d", p or ""):
        errs.append("Password must contain at least one letter and one digit.")
    return errs


def check_range(name: str, value, lo: float, hi: float, required: bool = False) -> list[str]:
    if value is None:
        return [f"{name} is required."] if required else []
    if not (lo <= value <= hi):
        return [f"{name} must be between {lo:g} and {hi:g}."]
    return []
