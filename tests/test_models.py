from datetime import date, timedelta

import pytest

from registry.exceptions import ValidationError
from registry.models import (BadgePolicy, Donation, DonationHistory, Height, Measurement, Profile,
                             User, Weight, calculate_bmi, make_measurement)

TODAY = date(2026, 11, 18)


def donation(days_ago):
    return Donation(1, date.today() - timedelta(days=days_ago), "Red Cross")


# ---- abstraction / polymorphism
def test_measurement_is_abstract():
    with pytest.raises(TypeError):
        Measurement(60)


def test_polymorphic_describe_needs_no_type_checks():
    items = [Weight(65), Height(170.5)]
    assert [m.describe() for m in items] == ["65 kg", "170.5 cm"]


def test_factory_builds_the_right_subclass():
    assert isinstance(make_measurement("weight", 70), Weight)
    assert isinstance(make_measurement("height", 170), Height)
    with pytest.raises(ValidationError):
        make_measurement("shoe_size", 9)


# ---- encapsulation with validation
@pytest.mark.parametrize("bad", [0, 501, float("nan")])
def test_weight_rejects_out_of_range(bad):
    with pytest.raises(ValidationError):
        Weight(bad)


def test_height_rejects_out_of_range():
    with pytest.raises(ValidationError):
        Height(29)


def test_measurement_date_cannot_be_future():
    with pytest.raises(ValidationError):
        Weight(60, date.today() + timedelta(days=1))


def test_user_normalises_email_and_rejects_bad_username():
    assert User("juan_01", "  JUAN@Mail.COM ").email == "juan@mail.com"
    with pytest.raises(ValidationError):
        User("no spaces!", "juan@mail.com")
    with pytest.raises(ValidationError):
        User("juan", "not-an-email")


def test_password_rules():
    with pytest.raises(ValidationError):
        User.check_new_password("short", "short")
    with pytest.raises(ValidationError):
        User.check_new_password("longenough1", "different1")
    User.check_new_password("longenough1", "longenough1")        # no error


def test_profile_rules():
    p = Profile(user_id=1)
    with pytest.raises(ValidationError):
        p.blood_type = "Z+"
    with pytest.raises(ValidationError):
        p.bio = "x" * 1001
    with pytest.raises(ValidationError):
        p.birthdate = date.today() + timedelta(days=1)
    p.birthdate = date(2000, 1, 1)
    assert p.age >= 26


def test_donation_requires_location_and_past_date():
    with pytest.raises(ValidationError):
        Donation(1, date.today(), "   ")
    with pytest.raises(ValidationError):
        Donation(1, date.today() + timedelta(days=1), "Hospital")


# ---- composition + strategy
@pytest.mark.parametrize("total,badge", [(0, "Newcomer"), (1, "First Drop"), (2, "First Drop"),
                                         (3, "Regular"), (5, "Lifesaver"), (10, "Champion")])
def test_badge_boundaries(total, badge):
    assert BadgePolicy().badge_for(total) == badge


def test_donation_history_numbers():
    history = DonationHistory([donation(10), donation(100), donation(500)])
    assert history.total == 3 and history.points == 30
    assert history.badge == "Regular"
    assert history.last_donated == date.today() - timedelta(days=10)
    assert history.next_eligible == history.last_donated + timedelta(weeks=8)
    assert history.last_12_months == 2
    assert history.avg_gap == round((90 + 400) / 2)


def test_empty_history():
    history = DonationHistory([])
    assert history.next_eligible is None and history.avg_gap is None and history.badge == "Newcomer"


def test_bmi():
    assert calculate_bmi(Weight(70), Height(175)) == 22.9
