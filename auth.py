"""Lightweight session-scoped authentication for the iSpaza demo.

This is intentionally "good enough" for a hackathon demo, not a
production identity system. The threat model assumed:

* App is hosted on Streamlit Community Cloud (ephemeral filesystem)
* A judge / demo viewer should be gated behind a login screen so the
  UX matches what a real product would do.
* Anyone can self-serve a new account (one click), so no friction.

What this gives you:

* SHA-256 password hashing with a fresh per-user 16-byte salt
* Constant-time comparison via ``hmac.compare_digest``
* No plaintext passwords stored anywhere
* A pure-Python user list that can be persisted to JSON for local
  runs (``users.json`` is gitignored), or kept entirely in-session
  on cloud deployments where the filesystem doesn't survive restarts.

What this deliberately doesn't give you:

* Server-side session tokens, CSRF protection, rate limiting, 2FA,
  email verification, OAuth, or anything else a real product needs.
  The login state lives in ``st.session_state`` and resets when the
  browser tab refreshes — that's an explicit choice.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

USERS_PATH = Path(__file__).parent / "data" / "users.json"

# How many bytes of random per password — 16 (= 128 bits) is plenty here.
_SALT_BYTES = 16


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------


def hash_password(password: str, salt_hex: str | None = None) -> tuple[str, str]:
    """Return ``(salt_hex, hash_hex)`` for ``password``.

    ``salt_hex`` is generated when not provided; pass an existing salt
    when re-hashing for verification.
    """
    if salt_hex is None:
        salt = secrets.token_bytes(_SALT_BYTES)
    else:
        salt = bytes.fromhex(salt_hex)
    digest = hashlib.sha256(salt + password.encode("utf-8")).hexdigest()
    return salt.hex(), digest


def verify_password(password: str, salt_hex: str, expected_hash: str) -> bool:
    """Constant-time check that ``password`` rehashes to ``expected_hash``."""
    _, candidate = hash_password(password, salt_hex=salt_hex)
    return hmac.compare_digest(candidate, expected_hash)


# ---------------------------------------------------------------------------
# Domain type
# ---------------------------------------------------------------------------


@dataclass
class User:
    """One registered user. ``password_hash`` and ``salt`` are hex strings."""

    username: str
    salt: str
    password_hash: str
    created: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "username": self.username,
            "salt": self.salt,
            "password_hash": self.password_hash,
            "created": self.created.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "User":
        created = d.get("created")
        return cls(
            username=str(d["username"]),
            salt=str(d["salt"]),
            password_hash=str(d["password_hash"]),
            created=(
                datetime.fromisoformat(created)
                if isinstance(created, str)
                else datetime.now()
            ),
        )


# ---------------------------------------------------------------------------
# CRUD-ish helpers (pure — they return new lists, never mutate)
# ---------------------------------------------------------------------------


class AuthError(ValueError):
    """Raised when create/authenticate has a domain-level failure (taken username, wrong password, etc.)."""


def find_user(users: Iterable[User], username: str) -> User | None:
    """Look up by case-insensitive username. ``None`` if missing."""
    target = (username or "").strip().lower()
    for u in users:
        if u.username.lower() == target:
            return u
    return None


def create_user(
    users: list[User], username: str, password: str, now: datetime | None = None
) -> list[User]:
    """Return a copy of ``users`` with the new account appended.

    Raises ``AuthError`` for blank / too-short input or duplicate usernames.
    """
    clean = (username or "").strip()
    if len(clean) < 3:
        raise AuthError("Username must be at least 3 characters.")
    if " " in clean:
        raise AuthError("Username can't contain spaces.")
    if len(password or "") < 4:
        raise AuthError("Password must be at least 4 characters.")
    if find_user(users, clean) is not None:
        raise AuthError("That username is already taken.")

    salt, digest = hash_password(password)
    new = User(
        username=clean,
        salt=salt,
        password_hash=digest,
        created=now or datetime.now(),
    )
    return [*users, new]


def authenticate(users: Iterable[User], username: str, password: str) -> User | None:
    """Return the matching User on success, ``None`` otherwise."""
    user = find_user(users, username)
    if user is None:
        return None
    if not verify_password(password, user.salt, user.password_hash):
        return None
    return user


# ---------------------------------------------------------------------------
# Persistence (used locally; on Streamlit Cloud the file resets per restart)
# ---------------------------------------------------------------------------


def load_users(path: Path | str | None = None) -> list[User]:
    """Load users from JSON. Missing file → empty list (fresh install)."""
    target = Path(path) if path else USERS_PATH
    if not target.exists():
        return []
    with target.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    users = raw.get("users", []) if isinstance(raw, dict) else raw
    return [User.from_dict(u) for u in users]


def save_users(users: Iterable[User], path: Path | str | None = None) -> None:
    """Write users to JSON. Creates the parent directory if needed."""
    target = Path(path) if path else USERS_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {"users": [u.to_dict() for u in users]}
    with target.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Demo seed — one ready-to-use account so judges can sign in immediately
# ---------------------------------------------------------------------------


def seed_demo_users(now: datetime | None = None) -> list[User]:
    """One pre-baked account: ``demo`` / ``spazi2026``.

    Used when the JSON store is empty or unavailable so the login screen
    always has a working credential displayed under the form.
    """
    salt, digest = hash_password("spazi2026")
    return [
        User(
            username="demo",
            salt=salt,
            password_hash=digest,
            created=now or datetime.now(),
        )
    ]
