from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    profile = db.relationship("Profile", backref="user", uselist=False, cascade="all, delete-orphan")
    donations = db.relationship("Donation", backref="user", lazy=True)
    measurements = db.relationship("Measurement", backref="user", lazy=True)
    health_statuses = db.relationship("HealthStatus", backref="user", lazy=True)

class Profile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    full_name = db.Column(db.String(100))
    location = db.Column(db.String(100))
    sex = db.Column(db.String(20))
    birthdate = db.Column(db.Date)
    blood_type = db.Column(db.String(10))
    bio = db.Column(db.Text)
    picture_filename = db.Column(db.String(255), default="default.jpg")
    is_public = db.Column(db.Boolean, default=True)

class Measurement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    type = db.Column(db.String(50), nullable=False)  # weight, height, bmi
    value = db.Column(db.Float, nullable=False)
    date_measured = db.Column(db.Date, nullable=False, default=datetime.utcnow)

class HealthStatus(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    status = db.Column(db.String(50), nullable=False)  # healthy / not healthy
    notes = db.Column(db.Text)
    date_checked = db.Column(db.Date, nullable=False, default=datetime.utcnow)

class Donation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    date_donated = db.Column(db.Date, nullable=False)
    location = db.Column(db.String(150), nullable=False)
    event_name = db.Column(db.String(150))
    community_id = db.Column(db.Integer, db.ForeignKey("community.id"), nullable=True)

class Community(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    members = db.relationship("CommunityMember", backref="community", lazy=True)
    donations = db.relationship("Donation", backref="community", lazy=True)

class CommunityMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    community_id = db.Column(db.Integer, db.ForeignKey("community.id"), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

class TriviaFact(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    body = db.Column(db.Text, nullable=False)
    source = db.Column(db.String(100))