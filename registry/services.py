"""Services: business rules. They validate input (through the domain classes), call
repositories, and wrap multi-step writes in a Transaction. No SQL in here and no Flask
objects except the uploaded file the web layer hands over."""
from datetime import date

from werkzeug.security import check_password_hash, generate_password_hash

from .db import Transaction
from .exceptions import (AuthError, DuplicateError, NotFoundError, PrivateProfileError,
                         ValidationError)
from .models import (Community, Donation, DonationHistory, HealthStatus, Height, Profile, User,
                     Weight, calculate_bmi)
from .parsing import parse_date, to_float
from .repositories import (CommunityRepository, DonationRepository, HealthStatusRepository,
                           MeasurementRepository, ProfileRepository, TriviaRepository,
                           UserRepository)
from .storage import DEFAULT_PICTURE

LEARN_CATEGORIES = ["Blood types", "Donation tips", "Myths"]


class AuthService:
    def __init__(self, conn, users, profiles):
        self.conn, self.users, self.profiles = conn, users, profiles

    def register(self, username, email, password, confirm_password):
        """Creates the user AND their blank profile in ONE transaction (two tables)."""
        user = User(username=username, email=email)          # validates both
        User.check_new_password(password, confirm_password)
        if self.users.username_or_email_taken(user.username, user.email):
            raise DuplicateError("Username or email already taken.")
        user.password_hash = generate_password_hash(password)
        with Transaction(self.conn, "Could not create your account. Please try again.",
                         duplicate_message="Username or email already taken."):
            user.id = self.users.add(user)
            self.profiles.add_blank(user.id)
        return user

    def authenticate(self, email, password):
        user = self.users.get_by_email((email or "").strip())
        if user is None or not check_password_hash(user.password_hash, password or ""):
            raise AuthError("Invalid email or password.")
        return user


class ProfileService:
    def __init__(self, conn, users, profiles, measurements, health, donations, communities, store):
        self.conn, self.users, self.profiles = conn, users, profiles
        self.measurements, self.health = measurements, health
        self.donations, self.communities, self.store = donations, communities, store

    def memberships(self, user_id):
        """[(community, number of this user's donations in it)] sorted by name."""
        counts = self.donations.counts_by_community(user_id)
        return [(c, counts.get(c.id, 0)) for c in self.communities.for_member(user_id)]

    def dashboard(self, user):
        profile = self.profiles.get_by_user(user.id)
        weight = self.measurements.latest(user.id, Weight.KIND)
        height = self.measurements.latest(user.id, Height.KIND)
        history = DonationHistory(self.donations.for_user(user.id))

        bmi = bmi_date = None
        if weight and height:
            bmi = calculate_bmi(weight, height)
            bmi_date = max(weight.date_measured, height.date_measured)

        return {
            "profile": profile,
            "age": profile.age if profile else None,
            "latest_weight": weight,
            "latest_height": height,
            "latest_health": self.health.latest(user.id),
            "bmi": bmi,
            "bmi_date": bmi_date,
            **self._history_context(history),
            "user_communities": self.memberships(user.id),
        }

    def public_view(self, username, viewer_id=None):
        user = self.users.get_by_username(username)
        if user is None:
            raise NotFoundError("That user does not exist.")
        profile = self.profiles.get_by_user(user.id)
        if profile is None or (not profile.is_public and viewer_id != user.id):
            raise PrivateProfileError("This profile is private.")
        history = DonationHistory(self.donations.for_user(user.id))
        return {
            "user": user,
            "profile": profile,
            "age": profile.age,
            **self._history_context(history),
            "user_communities": self.memberships(user.id),
        }

    @staticmethod
    def _history_context(history):
        return {
            "donations": history.donations,
            "total_donations": history.total,
            "points": history.points,
            "badge": history.badge,
            "last_donated": history.last_donated,
            "next_eligible": history.next_eligible,
            "last_12_months": history.last_12_months,
            "avg_gap": history.avg_gap,
        }

    def get_or_create(self, user_id):
        profile = self.profiles.get_by_user(user_id)
        if profile is None:
            with Transaction(self.conn, "Could not load your profile. Please try again."):
                self.profiles.add_blank(user_id)
            profile = self.profiles.get_by_user(user_id)
        return profile

    def update(self, user_id, form, picture=None, remove_picture=False):
        profile = self.get_or_create(user_id)
        old_picture = profile.picture_filename

        # Setters validate; the first bad field raises a ValidationError.
        profile.full_name = form.get("full_name")
        profile.location = form.get("location")
        profile.sex = form.get("sex")
        profile.bio = form.get("bio")
        profile.blood_type = form.get("blood_type")
        profile.birthdate = parse_date(form.get("birthdate"), None, "Birthdate")
        profile.is_public = form.get("is_public") == "on"

        new_picture = None
        if picture is not None and picture.filename:
            new_picture = self.store.save(picture, user_id)
            profile.picture_filename = new_picture
        elif remove_picture:
            profile.picture_filename = DEFAULT_PICTURE

        try:
            with Transaction(self.conn, "Could not save your profile. Please try again."):
                self.profiles.update(profile)
        except Exception:
            if new_picture:
                self.store.delete(new_picture)        # don't leave an orphan file behind
            raise
        if profile.picture_filename != old_picture:
            self.store.delete(old_picture)
        return profile


class HealthService:
    def __init__(self, conn, measurements, health):
        self.conn, self.measurements, self.health = conn, measurements, health

    def record_measurements(self, user_id, weight_text, height_text, date_text):
        measured = parse_date(date_text, date.today(), "Measurement date")
        weight_text, height_text = (weight_text or "").strip(), (height_text or "").strip()
        if not weight_text and not height_text:
            raise ValidationError("Please enter a weight or a height.")
        items = []
        if weight_text:
            items.append(Weight(to_float(weight_text, "Weight"), measured, user_id))
        if height_text:
            items.append(Height(to_float(height_text, "Height"), measured, user_id))
        with Transaction(self.conn, "Could not save your measurements. Please try again."):
            for item in items:
                self.measurements.add(item)
        return items

    def record_status(self, user_id, is_healthy, notes, date_text):
        status = HealthStatus(
            user_id, "Healthy" if is_healthy else "Not Healthy", notes,
            parse_date(date_text, date.today(), "Check-up date"))
        with Transaction(self.conn, "Could not save your health status. Please try again."):
            self.health.add(status)
        return status


class DonationService:
    def __init__(self, conn, donations, communities):
        self.conn, self.donations, self.communities = conn, donations, communities

    def my_communities(self, user_id):
        return self.communities.for_member(user_id)

    def log(self, user_id, date_text, location, event_name, community_id_text):
        donated = parse_date(date_text, None, "Donation date")
        if donated is None:
            raise ValidationError("Please enter a valid donation date.")

        community_id = None
        if community_id_text:
            if not str(community_id_text).isdigit() or \
                    not self.communities.is_member(user_id, int(community_id_text)):
                raise ValidationError("Please choose one of your own communities.")
            community_id = int(community_id_text)

        donation = Donation(user_id, donated, location, event_name, community_id)
        with Transaction(self.conn, "Could not save the donation. Please try again."):
            donation.id = self.donations.add(donation)
        return donation


class CommunityService:
    def __init__(self, conn, communities, users, donations):
        self.conn, self.communities, self.users, self.donations = conn, communities, users, donations

    def list_all(self):
        return self.communities.list_all()

    def recent(self, limit=3):
        return self.communities.recent(limit)

    def _require(self, community_id):
        community = self.communities.get(community_id)
        if community is None:
            raise NotFoundError("That community does not exist.")
        return community

    def detail(self, community_id, viewer_id=None):
        community = self._require(community_id)
        members = self.users.list_for_community(community_id)
        community.donations = self.donations.for_community(community_id)
        is_member = viewer_id is not None and any(m.id == viewer_id for m in members)
        return community, members, is_member

    def create(self, user_id, name, description):
        """Community row + creator's membership row: ONE transaction, two tables."""
        community = Community(name, description, created_by=user_id)       # validates
        if self.communities.find_by_name(community.name):
            raise DuplicateError("A community with that name already exists.")
        with Transaction(self.conn, "Could not create the community. Please try again.",
                         duplicate_message="A community with that name already exists."):
            community.id = self.communities.add(community)
            self.communities.add_member(user_id, community.id)
        return community

    def join(self, user_id, community_id):
        community = self._require(community_id)
        if self.communities.is_member(user_id, community_id):
            return community, False
        with Transaction(self.conn, "Could not join the community. Please try again."):
            self.communities.add_member(user_id, community_id)
        return community, True

    def leave(self, user_id, community_id):
        community = self._require(community_id)
        if community.created_by == user_id:
            raise ValidationError("The creator cannot leave their own community.")
        if not self.communities.is_member(user_id, community_id):
            return community, False
        with Transaction(self.conn, "Could not leave the community. Please try again."):
            self.communities.remove_member(user_id, community_id)
        return community, True


class ContentService:
    def __init__(self, trivia):
        self.trivia = trivia

    def random_fact(self):
        return self.trivia.random()

    def grouped_facts(self):
        facts = self.trivia.all()
        categories = LEARN_CATEGORIES + sorted({f.category for f in facts} - set(LEARN_CATEGORIES))
        grouped = [(c, [f for f in facts if f.category == c]) for c in categories]
        return [(c, fs) for c, fs in grouped if fs]


class Services:
    """Wires one connection to every repository and service (the app builds one per request)."""

    def __init__(self, conn, picture_store=None):
        self.conn = conn
        self.users = UserRepository(conn)
        profiles = ProfileRepository(conn)
        measurements = MeasurementRepository(conn)
        health = HealthStatusRepository(conn)
        donations = DonationRepository(conn)
        communities = CommunityRepository(conn)
        self.auth = AuthService(conn, self.users, profiles)
        self.profiles = ProfileService(conn, self.users, profiles, measurements, health,
                                       donations, communities, picture_store)
        self.health = HealthService(conn, measurements, health)
        self.donations = DonationService(conn, donations, communities)
        self.communities = CommunityService(conn, communities, self.users, donations)
        self.content = ContentService(TriviaRepository(conn))
