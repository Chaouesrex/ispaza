"""Unit tests for the auth module."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from auth import (
    AuthError,
    User,
    authenticate,
    create_user,
    find_user,
    hash_password,
    load_users,
    save_users,
    seed_demo_users,
    verify_password,
)


# ---------------------------------------------------------------------------
# hash_password / verify_password
# ---------------------------------------------------------------------------


def test_hash_password_returns_hex_salt_and_hex_digest():
    salt, digest = hash_password("hunter2")
    assert len(salt) == 32  # 16 bytes hex-encoded
    assert len(digest) == 64  # sha256 hex
    int(salt, 16)  # parseable hex
    int(digest, 16)


def test_hash_password_is_deterministic_given_a_salt():
    salt, digest1 = hash_password("hunter2")
    _, digest2 = hash_password("hunter2", salt_hex=salt)
    assert digest1 == digest2


def test_hash_password_different_salts_produce_different_digests():
    salt_a, digest_a = hash_password("hunter2")
    salt_b, digest_b = hash_password("hunter2")
    assert salt_a != salt_b
    assert digest_a != digest_b


def test_verify_password_returns_true_for_correct_password():
    salt, digest = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", salt, digest)


def test_verify_password_returns_false_for_wrong_password():
    salt, digest = hash_password("real")
    assert not verify_password("imposter", salt, digest)


def test_verify_password_returns_false_for_wrong_salt():
    salt_a, digest_a = hash_password("hunter2")
    salt_b, _ = hash_password("hunter2")
    # Different salt should not verify even with the same password.
    assert not verify_password("hunter2", salt_b, digest_a)


# ---------------------------------------------------------------------------
# User dataclass roundtrip
# ---------------------------------------------------------------------------


def test_user_to_dict_and_from_dict_roundtrip():
    when = datetime(2026, 5, 20, 12, 30, 0)
    u = User(username="ada", salt="abcd1234" * 4, password_hash="ff" * 32, created=when)
    re = User.from_dict(u.to_dict())
    assert re.username == "ada"
    assert re.salt == u.salt
    assert re.password_hash == u.password_hash
    assert re.created == when


# ---------------------------------------------------------------------------
# find_user
# ---------------------------------------------------------------------------


def test_find_user_is_case_insensitive():
    users = create_user([], "Ada", "pw1234")
    assert find_user(users, "ada") is not None
    assert find_user(users, "ADA") is not None


def test_find_user_returns_none_when_missing():
    assert find_user([], "ghost") is None


# ---------------------------------------------------------------------------
# create_user
# ---------------------------------------------------------------------------


def test_create_user_appends_to_list():
    users = create_user([], "ada", "secret")
    assert len(users) == 1
    assert users[0].username == "ada"


def test_create_user_strips_username_whitespace():
    users = create_user([], "  ada  ", "secret")
    assert users[0].username == "ada"


def test_create_user_does_not_mutate_input():
    initial: list[User] = []
    create_user(initial, "ada", "secret")
    assert initial == []


def test_create_user_rejects_short_username():
    with pytest.raises(AuthError):
        create_user([], "ab", "secret")


def test_create_user_rejects_username_with_spaces():
    with pytest.raises(AuthError):
        create_user([], "ada lovelace", "secret")


def test_create_user_rejects_short_password():
    with pytest.raises(AuthError):
        create_user([], "ada", "123")


def test_create_user_rejects_duplicate_username_case_insensitively():
    users = create_user([], "ada", "secret")
    with pytest.raises(AuthError):
        create_user(users, "ADA", "anotherpw")


# ---------------------------------------------------------------------------
# authenticate
# ---------------------------------------------------------------------------


def test_authenticate_returns_user_for_correct_credentials():
    users = create_user([], "ada", "secret")
    u = authenticate(users, "ada", "secret")
    assert u is not None
    assert u.username == "ada"


def test_authenticate_is_case_insensitive_on_username():
    users = create_user([], "ada", "secret")
    assert authenticate(users, "ADA", "secret") is not None


def test_authenticate_returns_none_for_wrong_password():
    users = create_user([], "ada", "secret")
    assert authenticate(users, "ada", "wrongpw") is None


def test_authenticate_returns_none_for_missing_user():
    assert authenticate([], "ghost", "any") is None


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def test_load_users_returns_empty_when_file_missing(tmp_path: Path):
    assert load_users(tmp_path / "nope.json") == []


def test_save_then_load_roundtrips(tmp_path: Path):
    users = create_user([], "ada", "secret")
    target = tmp_path / "users.json"
    save_users(users, target)
    # File should be valid JSON
    assert json.loads(target.read_text(encoding="utf-8"))["users"][0]["username"] == "ada"
    loaded = load_users(target)
    assert len(loaded) == 1
    assert loaded[0].username == "ada"
    # And the round-tripped user still authenticates with the original password.
    assert authenticate(loaded, "ada", "secret") is not None


def test_save_users_writes_no_plaintext_password(tmp_path: Path):
    users = create_user([], "ada", "super-secret-passphrase")
    target = tmp_path / "users.json"
    save_users(users, target)
    text = target.read_text(encoding="utf-8")
    assert "super-secret-passphrase" not in text


# ---------------------------------------------------------------------------
# Seed
# ---------------------------------------------------------------------------


def test_seed_demo_users_creates_one_working_account():
    users = seed_demo_users()
    assert len(users) == 1
    assert authenticate(users, "demo", "spaza2026") is not None
    assert authenticate(users, "demo", "wrong") is None
