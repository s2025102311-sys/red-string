from datetime import date, timedelta

import pytest
from werkzeug.security import generate_password_hash

from registry.exceptions import (AuthError, DatabaseError, DuplicateError, NotFoundError,
                                 PrivateProfileError, ValidationError)
from registry.services import Services
from tests.fakes import FakeConnection


def services(conn):
    return Services(conn, picture_store=None)


# ---------------------------------------------------------------- registration (2 tables, 1 transaction)
def test_register_inserts_user_and_profile_in_one_commit():
    conn = FakeConnection()
    user = services(conn).auth.register("maria", "Maria@Mail.com", "password123", "password123")
    assert conn.statements("INSERT INTO users") and conn.statements("INSERT INTO profiles")
    assert conn.commits == 1 and conn.rollbacks == 0
    assert user.email == "maria@mail.com" and user.password_hash != "password123"


def test_register_rolls_back_when_profile_insert_fails():
    conn = FakeConnection(fail_on="INSERT INTO profiles")
    with pytest.raises(DatabaseError):
        services(conn).auth.register("maria", "maria@mail.com", "password123", "password123")
    assert conn.rollbacks == 1 and conn.commits == 0


def test_register_rejects_duplicate_user():
    conn = FakeConnection([("SELECT id FROM users", [{"id": 1}])])
    with pytest.raises(DuplicateError):
        services(conn).auth.register("maria", "maria@mail.com", "password123", "password123")
    assert conn.commits == 0


@pytest.mark.parametrize("pw,confirm", [("short", "short"), ("password123", "password124")])
def test_register_rejects_bad_passwords(pw, confirm):
    with pytest.raises(ValidationError):
        services(FakeConnection()).auth.register("maria", "maria@mail.com", pw, confirm)


# ---------------------------------------------------------------- login
def user_row(password="password123"):
    return {"id": 1, "username": "maria", "email": "maria@mail.com",
            "password_hash": generate_password_hash(password), "created_at": None}


def test_authenticate_success_and_failure():
    conn = FakeConnection([("FROM users", [user_row()])])
    assert services(conn).auth.authenticate("maria@mail.com", "password123").id == 1
    with pytest.raises(AuthError):
        services(conn).auth.authenticate("maria@mail.com", "wrong-password")
    with pytest.raises(AuthError):
        services(FakeConnection()).auth.authenticate("nobody@mail.com", "whatever1")


# ---------------------------------------------------------------- communities (2 tables, 1 transaction)
def test_create_community_commits_both_rows_once():
    conn = FakeConnection()
    community = services(conn).communities.create(5, "Naga Donors", "Bicol blood donors")
    assert conn.statements("INSERT INTO communities") and conn.statements("INSERT INTO community_members")
    assert conn.commits == 1 and conn.rollbacks == 0
    assert community.name == "Naga Donors"


def test_create_community_rolls_back_everything_if_membership_fails():
    conn = FakeConnection(fail_on="INSERT INTO community_members")
    with pytest.raises(DatabaseError) as info:
        services(conn).communities.create(5, "Naga Donors", None)
    assert conn.rollbacks == 1 and conn.commits == 0
    assert "Could not create the community" in str(info.value)       # friendly, no SQL leaked


def test_create_community_rejects_duplicate_name():
    conn = FakeConnection([("LOWER(c.name)", [{"id": 1, "name": "Naga Donors", "description": None,
                                               "created_by": 1, "member_count": 1}])])
    with pytest.raises(DuplicateError):
        services(conn).communities.create(5, "naga donors", None)
    assert conn.commits == 0


def test_creator_cannot_leave_own_community():
    row = {"id": 1, "name": "A", "description": None, "created_by": 5, "member_count": 1}
    conn = FakeConnection([("WHERE c.id", [row])])
    with pytest.raises(ValidationError):
        services(conn).communities.leave(5, 1)


def test_missing_community_raises_not_found():
    with pytest.raises(NotFoundError):
        services(FakeConnection()).communities.detail(999)


# ---------------------------------------------------------------- donations & health
def test_log_donation_saves_with_commit():
    conn = FakeConnection()
    services(conn).donations.log(1, "2026-01-10", "Red Cross", "Drive", "")
    assert conn.commits == 1 and conn.statements("INSERT INTO donations")


def test_log_donation_rejects_future_date_and_foreign_community():
    future = (date.today() + timedelta(days=2)).isoformat()
    with pytest.raises(ValidationError):
        services(FakeConnection()).donations.log(1, future, "Red Cross", None, "")
    with pytest.raises(ValidationError):                      # not a member of community 9
        services(FakeConnection()).donations.log(1, "2026-01-10", "Red Cross", None, "9")


def test_record_measurements_saves_both_and_validates():
    conn = FakeConnection()
    saved = services(conn).health.record_measurements(1, "60", "165", "2026-01-01")
    assert [m.describe() for m in saved] == ["60 kg", "165 cm"] and conn.commits == 1
    with pytest.raises(ValidationError):
        services(FakeConnection()).health.record_measurements(1, "0", "", "2026-01-01")
    with pytest.raises(ValidationError):
        services(FakeConnection()).health.record_measurements(1, "abc", "", "2026-01-01")


def test_private_profile_is_hidden_from_others_but_not_the_owner():
    conn = FakeConnection([
        ("FROM users", [user_row()]),
        ("FROM profiles", [{"id": 1, "user_id": 1, "full_name": None, "location": None, "sex": None,
                            "birthdate": None, "blood_type": None, "bio": None,
                            "picture_filename": "default.jpg", "is_public": 0}]),
    ])
    with pytest.raises(PrivateProfileError):
        services(conn).profiles.public_view("maria", viewer_id=99)
    assert services(conn).profiles.public_view("maria", viewer_id=1)["user"].id == 1
