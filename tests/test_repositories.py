from datetime import date

from registry.models import Community, Donation, User, Weight
from registry.repositories import (CommunityRepository, DonationRepository, MeasurementRepository,
                                   UserRepository)
from tests.fakes import FakeConnection


def test_donation_insert_uses_percent_s_and_ordered_params():
    conn = FakeConnection()
    new_id = DonationRepository(conn).add(Donation(7, date(2026, 1, 5), "Hospital", "Drive", 3))
    sql, params = conn.executed[0]
    assert sql.startswith("INSERT INTO donations") and sql.count("%s") == 5
    assert params == (7, date(2026, 1, 5), "Hospital", "Drive", 3)
    assert new_id == conn.next_id


def test_user_input_never_ends_up_inside_sql_text():
    conn = FakeConnection()
    evil = "x' OR '1'='1"
    UserRepository(conn).get_by_username(evil)
    sql, params = conn.executed[0]
    assert evil not in sql and params == (evil,)


def test_get_returns_none_when_no_row():
    assert UserRepository(FakeConnection()).get(1) is None


def test_get_by_email_builds_a_user():
    row = {"id": 4, "username": "ana", "email": "ana@mail.com", "password_hash": "h", "created_at": None}
    user = UserRepository(FakeConnection([("FROM users", [row])])).get_by_email("ANA@mail.com")
    assert isinstance(user, User) and user.id == 4


def test_latest_measurement_is_polymorphic_object():
    row = {"id": 1, "user_id": 2, "kind": "weight", "value": 61.5, "date_measured": date(2026, 1, 1)}
    m = MeasurementRepository(FakeConnection([("FROM measurements", [row])])).latest(2, "weight")
    assert isinstance(m, Weight) and m.describe() == "61.5 kg"


def test_membership_queries_are_parameterised():
    conn = FakeConnection([("FROM community_members", [{"id": 1}])])
    repo = CommunityRepository(conn)
    assert repo.is_member(1, 2) is True
    repo.remove_member(1, 2)
    assert all("%s" in sql for sql, _ in conn.executed)


def test_community_insert():
    conn = FakeConnection()
    CommunityRepository(conn).add(Community("Donors", "desc", created_by=1))
    assert conn.executed[0][1] == ("Donors", "desc", 1)
