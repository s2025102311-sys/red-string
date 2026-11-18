"""Repositories: the ONLY place SQL lives. Every query uses %s placeholders and passes
its values as a separate tuple - values are never formatted into the SQL text."""
from abc import ABC, abstractmethod

from .models import (Community, Donation, HealthStatus, Profile, TriviaFact, User,
                     make_measurement)

# Columns used whenever a page needs a user together with their profile (joins)
USER_PROFILE_COLUMNS = (
    "u.id AS u_id, u.username, u.email, "
    "p.id AS p_id, p.full_name AS p_full_name, p.location AS p_location, p.sex AS p_sex, "
    "p.birthdate AS p_birthdate, p.blood_type AS p_blood_type, p.bio AS p_bio, "
    "p.picture_filename AS p_picture, p.is_public AS p_is_public"
)


def user_with_profile(row):
    """Builds a User (with Profile attached) from a row that used USER_PROFILE_COLUMNS."""
    profile = None
    if row.get("p_id") is not None:
        profile = Profile(
            user_id=row["u_id"], full_name=row["p_full_name"], location=row["p_location"],
            sex=row["p_sex"], birthdate=row["p_birthdate"], blood_type=row["p_blood_type"],
            bio=row["p_bio"], picture_filename=row["p_picture"],
            is_public=row["p_is_public"], id=row["p_id"])
    return User(username=row["username"], email=row["email"], id=row["u_id"], profile=profile)


class BaseRepository(ABC):
    """Shared helpers. Subclasses must say how to turn a row into a domain object."""

    def __init__(self, conn):
        self.conn = conn

    @abstractmethod
    def _to_object(self, row):
        """Row (dict) -> domain object."""

    def _fetch_all(self, sql, params=()):
        with self.conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            return list(cur.fetchall())

    def _fetch_one(self, sql, params=()):
        with self.conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            return cur.fetchone()

    def _insert(self, sql, params=()):
        with self.conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            return cur.lastrowid

    def _execute(self, sql, params=()):
        with self.conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            return cur.rowcount

    def _object_or_none(self, row):
        return self._to_object(row) if row else None


class UserRepository(BaseRepository):
    def _to_object(self, row):
        return User(username=row["username"], email=row["email"],
                    password_hash=row["password_hash"], id=row["id"], created_at=row["created_at"])

    def add(self, user):
        return self._insert(
            "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)",
            (user.username, user.email, user.password_hash))

    def get(self, user_id):
        return self._object_or_none(self._fetch_one("SELECT * FROM users WHERE id = %s", (user_id,)))

    def get_by_email(self, email):
        return self._object_or_none(
            self._fetch_one("SELECT * FROM users WHERE LOWER(email) = LOWER(%s)", (email,)))

    def get_by_username(self, username):
        return self._object_or_none(
            self._fetch_one("SELECT * FROM users WHERE username = %s", (username,)))

    def username_or_email_taken(self, username, email):
        row = self._fetch_one(
            "SELECT id FROM users WHERE LOWER(username) = LOWER(%s) OR LOWER(email) = LOWER(%s)",
            (username, email))
        return row is not None

    def list_for_community(self, community_id):
        rows = self._fetch_all(
            "SELECT " + USER_PROFILE_COLUMNS + " FROM community_members cm "
            "JOIN users u ON u.id = cm.user_id "
            "LEFT JOIN profiles p ON p.user_id = u.id "
            "WHERE cm.community_id = %s ORDER BY cm.joined_at, u.id", (community_id,))
        return [user_with_profile(r) for r in rows]


class ProfileRepository(BaseRepository):
    def _to_object(self, row):
        return Profile(user_id=row["user_id"], full_name=row["full_name"], location=row["location"],
                       sex=row["sex"], birthdate=row["birthdate"], blood_type=row["blood_type"],
                       bio=row["bio"], picture_filename=row["picture_filename"],
                       is_public=row["is_public"], id=row["id"])

    def add_blank(self, user_id):
        return self._insert("INSERT INTO profiles (user_id) VALUES (%s)", (user_id,))

    def get_by_user(self, user_id):
        return self._object_or_none(
            self._fetch_one("SELECT * FROM profiles WHERE user_id = %s", (user_id,)))

    def update(self, p):
        return self._execute(
            "UPDATE profiles SET full_name = %s, location = %s, sex = %s, birthdate = %s, "
            "blood_type = %s, bio = %s, picture_filename = %s, is_public = %s WHERE user_id = %s",
            (p.full_name, p.location, p.sex, p.birthdate, p.blood_type, p.bio,
             p.picture_filename, p.is_public, p.user_id))


class MeasurementRepository(BaseRepository):
    def _to_object(self, row):
        return make_measurement(row["kind"], row["value"], row["date_measured"],
                                row["user_id"], row["id"])

    def add(self, m):
        return self._insert(
            "INSERT INTO measurements (user_id, kind, value, date_measured) VALUES (%s, %s, %s, %s)",
            (m.user_id, m.KIND, m.value, m.date_measured))

    def latest(self, user_id, kind):
        return self._object_or_none(self._fetch_one(
            "SELECT * FROM measurements WHERE user_id = %s AND kind = %s "
            "ORDER BY date_measured DESC, id DESC LIMIT 1", (user_id, kind)))


class HealthStatusRepository(BaseRepository):
    def _to_object(self, row):
        return HealthStatus(row["user_id"], row["status"], row["notes"], row["date_checked"], row["id"])

    def add(self, h):
        return self._insert(
            "INSERT INTO health_statuses (user_id, status, notes, date_checked) VALUES (%s, %s, %s, %s)",
            (h.user_id, h.status, h.notes, h.date_checked))

    def latest(self, user_id):
        return self._object_or_none(self._fetch_one(
            "SELECT * FROM health_statuses WHERE user_id = %s "
            "ORDER BY date_checked DESC, id DESC LIMIT 1", (user_id,)))


class DonationRepository(BaseRepository):
    def _to_object(self, row):
        community = None
        if row.get("community_id") is not None and row.get("community_name"):
            community = Community(name=row["community_name"], id=row["community_id"])
        return Donation(user_id=row["user_id"], date_donated=row["date_donated"],
                        location=row["location"], event_name=row["event_name"],
                        community_id=row["community_id"], id=row["id"], community=community)

    def add(self, d):
        return self._insert(
            "INSERT INTO donations (user_id, date_donated, location, event_name, community_id) "
            "VALUES (%s, %s, %s, %s, %s)",
            (d.user_id, d.date_donated, d.location, d.event_name, d.community_id))

    def for_user(self, user_id):
        rows = self._fetch_all(
            "SELECT d.*, c.name AS community_name FROM donations d "
            "LEFT JOIN communities c ON c.id = d.community_id "
            "WHERE d.user_id = %s ORDER BY d.date_donated DESC, d.id DESC", (user_id,))
        return [self._to_object(r) for r in rows]

    def for_community(self, community_id):
        rows = self._fetch_all(
            "SELECT d.*, " + USER_PROFILE_COLUMNS + " FROM donations d "
            "JOIN users u ON u.id = d.user_id "
            "LEFT JOIN profiles p ON p.user_id = u.id "
            "WHERE d.community_id = %s ORDER BY d.date_donated DESC, d.id DESC", (community_id,))
        donations = []
        for r in rows:
            donation = self._to_object(r)
            donation.user = user_with_profile(r)
            donations.append(donation)
        return donations

    def counts_by_community(self, user_id):
        rows = self._fetch_all(
            "SELECT community_id, COUNT(*) AS total FROM donations "
            "WHERE user_id = %s AND community_id IS NOT NULL GROUP BY community_id", (user_id,))
        return {r["community_id"]: r["total"] for r in rows}


class CommunityRepository(BaseRepository):
    _SELECT = ("SELECT c.*, (SELECT COUNT(*) FROM community_members cm "
               "WHERE cm.community_id = c.id) AS member_count FROM communities c ")

    def _to_object(self, row):
        return Community(name=row["name"], description=row["description"],
                         created_by=row["created_by"], id=row["id"],
                         member_count=row.get("member_count", 0))

    def add(self, c):
        return self._insert(
            "INSERT INTO communities (name, description, created_by) VALUES (%s, %s, %s)",
            (c.name, c.description, c.created_by))

    def get(self, community_id):
        return self._object_or_none(
            self._fetch_one(self._SELECT + "WHERE c.id = %s", (community_id,)))

    def find_by_name(self, name):
        return self._object_or_none(
            self._fetch_one(self._SELECT + "WHERE LOWER(c.name) = LOWER(%s)", (name,)))

    def list_all(self):
        return [self._to_object(r) for r in self._fetch_all(self._SELECT + "ORDER BY c.name")]

    def recent(self, limit):
        return [self._to_object(r) for r in
                self._fetch_all(self._SELECT + "ORDER BY c.id DESC LIMIT %s", (limit,))]

    def for_member(self, user_id):
        rows = self._fetch_all(
            self._SELECT + "JOIN community_members m ON m.community_id = c.id "
            "WHERE m.user_id = %s ORDER BY c.name", (user_id,))
        return [self._to_object(r) for r in rows]

    # membership lives in its own table (community_members)
    def add_member(self, user_id, community_id):
        return self._insert(
            "INSERT INTO community_members (user_id, community_id) VALUES (%s, %s)",
            (user_id, community_id))

    def remove_member(self, user_id, community_id):
        return self._execute(
            "DELETE FROM community_members WHERE user_id = %s AND community_id = %s",
            (user_id, community_id))

    def is_member(self, user_id, community_id):
        return self._fetch_one(
            "SELECT id FROM community_members WHERE user_id = %s AND community_id = %s",
            (user_id, community_id)) is not None


class TriviaRepository(BaseRepository):
    def _to_object(self, row):
        return TriviaFact(row["category"], row["title"], row["body"], row["source"], row["id"])

    def random(self):
        return self._object_or_none(self._fetch_one("SELECT * FROM trivia_facts ORDER BY RAND() LIMIT 1"))

    def all(self):
        return [self._to_object(r) for r in self._fetch_all("SELECT * FROM trivia_facts ORDER BY id")]
