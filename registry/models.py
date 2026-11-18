"""Domain classes. They hold data AND enforce their own rules (encapsulation):
setters validate, so an invalid object can never exist.

OOP map:
  * abstraction + inheritance + polymorphism : Measurement -> Weight / Height, BadgeTier -> 5 tiers
  * composition                              : User has a Profile, DonationHistory has Donations
  * encapsulation with validation            : properties / BoundedText descriptors
  * Strategy design pattern (bonus)          : BadgePolicy chooses among BadgeTier strategies
"""
import re
from abc import ABC, abstractmethod
from datetime import date, timedelta

from flask_login import UserMixin

from .exceptions import ValidationError

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,30}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
BLOOD_TYPES = {"A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"}
DONATION_GAP = timedelta(weeks=8)
POINTS_PER_DONATION = 10


def _not_future(value, label):
    if value > date.today():
        raise ValidationError(f"{label} cannot be in the future.")
    return value


class BoundedText:
    """Descriptor: trims text, stores blank as None and enforces a maximum length."""

    def __init__(self, label, max_len, required=False):
        self.label, self.max_len, self.required = label, max_len, required

    def __set_name__(self, owner, name):
        self.attr = "_" + name

    def __get__(self, obj, objtype=None):
        return self if obj is None else getattr(obj, self.attr, None)

    def __set__(self, obj, value):
        text = (value or "").strip()
        if self.required and not text:
            raise ValidationError(f"{self.label} is required.")
        if len(text) > self.max_len:
            raise ValidationError(f"{self.label} must be {self.max_len} characters or fewer.")
        setattr(obj, self.attr, text or None)


# --------------------------------------------------------------------------- measurements
class Measurement(ABC):
    """Abstract base for a body measurement. Subclasses only declare their limits and
    how they describe themselves; callers treat every measurement the same way."""

    KIND = ""
    LABEL = ""
    UNIT = ""
    MIN = 0.0
    MAX = 0.0

    def __init__(self, value, date_measured=None, user_id=None, id=None):
        self.id = id
        self.user_id = user_id
        self.value = value
        self.date_measured = date_measured or date.today()

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, v):
        v = float(v)
        if not (self.MIN <= v <= self.MAX):      # also rejects NaN
            raise ValidationError(f"{self.LABEL} must be between {self.MIN:g} and {self.MAX:g} {self.UNIT}.")
        self._value = v

    @property
    def date_measured(self):
        return self._date_measured

    @date_measured.setter
    def date_measured(self, d):
        self._date_measured = _not_future(d, "Measurement date")

    @abstractmethod
    def describe(self):
        """Human readable text, e.g. '65 kg'."""


class Weight(Measurement):
    KIND, LABEL, UNIT, MIN, MAX = "weight", "Weight", "kg", 1, 500

    def describe(self):
        return f"{self.value:g} kg"


class Height(Measurement):
    KIND, LABEL, UNIT, MIN, MAX = "height", "Height", "cm", 30, 280

    def describe(self):
        return f"{self.value:g} cm"


MEASUREMENT_TYPES = {cls.KIND: cls for cls in (Weight, Height)}


def make_measurement(kind, value, date_measured=None, user_id=None, id=None):
    """Factory: builds the right Measurement subclass from a stored 'kind' string."""
    try:
        return MEASUREMENT_TYPES[kind](value, date_measured, user_id, id)
    except KeyError:
        raise ValidationError(f"Unknown measurement type: {kind}.") from None


def calculate_bmi(weight, height):
    """BMI from a Weight and a Height object (rounded to 1 decimal)."""
    metres = height.value / 100.0
    return round(weight.value / (metres ** 2), 1)


# --------------------------------------------------------------------------- people
class Profile:
    full_name = BoundedText("Full name", 100)
    location = BoundedText("Location", 100)
    sex = BoundedText("Sex", 20)
    bio = BoundedText("Bio", 1000)

    def __init__(self, user_id, full_name=None, location=None, sex=None, birthdate=None,
                 blood_type=None, bio=None, picture_filename="default.jpg", is_public=True, id=None):
        self.id = id
        self.user_id = user_id
        self.full_name = full_name
        self.location = location
        self.sex = sex
        self.birthdate = birthdate
        self.blood_type = blood_type
        self.bio = bio
        self.picture_filename = picture_filename or "default.jpg"
        self.is_public = bool(is_public)

    @property
    def blood_type(self):
        return self._blood_type

    @blood_type.setter
    def blood_type(self, value):
        value = (value or "").strip()
        if value and value not in BLOOD_TYPES:
            raise ValidationError("Please choose a valid blood type.")
        self._blood_type = value or None

    @property
    def birthdate(self):
        return self._birthdate

    @birthdate.setter
    def birthdate(self, value):
        if value is not None:
            _not_future(value, "Birthdate")
            if self._age_on(value) > 120:
                raise ValidationError("Please enter a realistic birthdate.")
        self._birthdate = value

    @staticmethod
    def _age_on(born, today=None):
        today = today or date.today()
        return today.year - born.year - ((today.month, today.day) < (born.month, born.day))

    @property
    def age(self):
        return self._age_on(self._birthdate) if self._birthdate else None


class User(UserMixin):
    """A registered donor. Owns one Profile (composition)."""

    def __init__(self, username, email, password_hash=None, id=None, created_at=None, profile=None):
        self.id = id
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self.created_at = created_at
        self.profile = profile

    @property
    def username(self):
        return self._username

    @username.setter
    def username(self, value):
        value = (value or "").strip()
        if not USERNAME_RE.match(value):
            raise ValidationError("Username must be 3-30 characters: letters, numbers and underscores only.")
        self._username = value

    @property
    def email(self):
        return self._email

    @email.setter
    def email(self, value):
        value = (value or "").strip().lower()
        if len(value) > 120 or not EMAIL_RE.match(value):
            raise ValidationError("Please enter a valid email address.")
        self._email = value

    @staticmethod
    def check_new_password(password, confirm):
        if len(password or "") < 8:
            raise ValidationError("Password must be at least 8 characters.")
        if password != confirm:
            raise ValidationError("Passwords do not match.")


# --------------------------------------------------------------------------- health
class HealthStatus:
    STATUSES = ("Healthy", "Not Healthy")
    notes = BoundedText("Notes", 1000)

    def __init__(self, user_id, status, notes=None, date_checked=None, id=None):
        self.id = id
        self.user_id = user_id
        if status not in self.STATUSES:
            raise ValidationError("Health status must be Healthy or Not Healthy.")
        self.status = status
        self.notes = notes
        self.date_checked = _not_future(date_checked or date.today(), "Check-up date")


# --------------------------------------------------------------------------- donations
class Donation:
    location = BoundedText("Location", 150, required=True)
    event_name = BoundedText("Event name", 150)

    def __init__(self, user_id, date_donated, location, event_name=None, community_id=None,
                 id=None, user=None, community=None):
        self.id = id
        self.user_id = user_id
        self.date_donated = _not_future(date_donated, "Donation date")
        self.location = location
        self.event_name = event_name
        self.community_id = community_id
        self.user = user                 # filled in by repositories when a page needs it
        self.community = community


class BadgeTier(ABC):
    """Strategy interface: one credential level."""
    name = ""
    threshold = 0

    def matches(self, total):
        return total >= self.threshold


class Newcomer(BadgeTier):
    name, threshold = "Newcomer", 0


class FirstDrop(BadgeTier):
    name, threshold = "First Drop", 1


class Regular(BadgeTier):
    name, threshold = "Regular", 3


class Lifesaver(BadgeTier):
    name, threshold = "Lifesaver", 5


class Champion(BadgeTier):
    name, threshold = "Champion", 10


class BadgePolicy:
    """Context of the Strategy pattern: asks each tier (highest first) if it matches."""

    def __init__(self, tiers=None):
        tiers = tiers or [Newcomer(), FirstDrop(), Regular(), Lifesaver(), Champion()]
        self.tiers = sorted(tiers, key=lambda t: t.threshold, reverse=True)

    def badge_for(self, total):
        for tier in self.tiers:
            if tier.matches(total):
                return tier.name
        return self.tiers[-1].name


class DonationHistory:
    """Composition: wraps a list of Donation objects and derives the dashboard numbers."""

    def __init__(self, donations, policy=None, today=None):
        self.donations = sorted(donations, key=lambda d: d.date_donated, reverse=True)
        self.policy = policy or BadgePolicy()
        self.today = today or date.today()

    @property
    def total(self):
        return len(self.donations)

    @property
    def points(self):
        return self.total * POINTS_PER_DONATION

    @property
    def badge(self):
        return self.policy.badge_for(self.total)

    @property
    def last_donated(self):
        return self.donations[0].date_donated if self.donations else None

    @property
    def next_eligible(self):
        return self.last_donated + DONATION_GAP if self.last_donated else None

    @property
    def last_12_months(self):
        cutoff = self.today - timedelta(days=365)
        return sum(1 for d in self.donations if d.date_donated >= cutoff)

    @property
    def avg_gap(self):
        if self.total < 2:
            return None
        dates = sorted(d.date_donated for d in self.donations)
        gaps = [(dates[i] - dates[i - 1]).days for i in range(1, len(dates))]
        return round(sum(gaps) / len(gaps))


# --------------------------------------------------------------------------- communities
class Community:
    name = BoundedText("Community name", 100, required=True)
    description = BoundedText("Description", 1000)

    def __init__(self, name, description=None, created_by=None, id=None, member_count=0):
        self.id = id
        self.name = name
        self.description = description
        self.created_by = created_by
        self.member_count = member_count
        self.donations = []


class TriviaFact:
    def __init__(self, category, title, body, source=None, id=None):
        self.id, self.category, self.title, self.body, self.source = id, category, title, body, source
