"""Web layer (Flask). Routes only read the request, call a service, and render/redirect.
All rules live in registry/services.py, all SQL in registry/repositories.py."""
import os
import secrets
from datetime import date
from urllib.parse import urlparse

from flask import Flask, flash, g, redirect, render_template, request, url_for
from flask_login import (LoginManager, current_user, login_required, login_user,
                         logout_user)
from werkzeug.exceptions import HTTPException

from registry.db import get_connection
from registry.exceptions import DatabaseError, RegistryError
from registry.services import Services
from registry.storage import ProfilePictureStore


def load_secret_key(app):
    """SECRET_KEY from the environment/.env, otherwise a random key saved in instance/ (gitignored)."""
    env_key = os.environ.get("SECRET_KEY")
    if env_key:
        return env_key
    os.makedirs(app.instance_path, exist_ok=True)
    key_path = os.path.join(app.instance_path, "secret_key")
    if os.path.exists(key_path):
        with open(key_path) as f:
            return f.read().strip()
    key = secrets.token_hex(32)
    with open(key_path, "w") as f:
        f.write(key)
    return key


def create_app(conn_factory=None, upload_folder=None):
    app = Flask(__name__)
    app.config["SECRET_KEY"] = load_secret_key(app)
    app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024       # profile pictures: 2 MB max

    conn_factory = conn_factory or get_connection
    store = ProfilePictureStore(upload_folder or os.path.join(app.static_folder, "uploads"))

    # ------------------------------------------------------------ per-request services
    def get_services():
        """Opens the database connection lazily, once per request."""
        if "services" not in g:
            g.conn = conn_factory()
            g.services = Services(g.conn, store)
        return g.services

    @app.teardown_appcontext
    def close_connection(exc):
        conn = g.pop("conn", None)
        g.pop("services", None)
        if conn is not None:
            try:
                if exc:
                    conn.rollback()
                conn.close()
            except Exception:
                pass

    login_manager = LoginManager(app)
    login_manager.login_view = "login"

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return get_services().users.get(int(user_id))
        except (RegistryError, ValueError):
            return None

    @app.context_processor
    def template_helpers():
        def avatar_url(profile):
            name = getattr(profile, "picture_filename", None)
            if store.exists(name):
                return url_for("static", filename="uploads/" + name)
            return url_for("static", filename="images/default_avatar.svg")
        return {"today": date.today().isoformat(), "avatar_url": avatar_url}

    # ------------------------------------------------------------ error handling
    def safe_back():
        """Where to send the user after an error: the page they came from (same site only)."""
        ref = request.referrer
        if ref and urlparse(ref).netloc == request.host:
            return ref
        return url_for("home")

    @app.errorhandler(RegistryError)
    def handle_registry_error(error):
        if isinstance(error, DatabaseError):
            app.logger.error("Database error: %s", error.__cause__ or error)
            return render_template("error.html", message=str(error)), 503
        flash(str(error), error.category)
        return redirect(safe_back())

    @app.errorhandler(413)
    def file_too_large(error):
        flash("That file is too large. Please upload an image under 2 MB.", "error")
        return redirect(url_for("edit_profile"))

    @app.errorhandler(Exception)
    def handle_unexpected(error):
        if isinstance(error, HTTPException):
            return error                                  # normal 404 / 405 pages
        app.logger.exception("Unexpected error")
        return render_template("error.html",
                               message="Something went wrong. Please try again."), 500

    # ------------------------------------------------------------ public pages
    @app.route("/")
    def home():
        s = get_services()
        return render_template("index.html", fact=s.content.random_fact(),
                               recent_communities=s.communities.recent(3))

    @app.route("/learn")
    def learn():
        return render_template("learn.html", grouped=get_services().content.grouped_facts())

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            get_services().auth.register(
                request.form.get("username"), request.form.get("email"),
                request.form.get("password"), request.form.get("confirm_password"))
            flash("Registration successful! Please log in.", "success")
            return redirect(url_for("login"))
        return render_template("register.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            user = get_services().auth.authenticate(request.form.get("email"),
                                                    request.form.get("password"))
            login_user(user)
            flash("Logged in successfully!", "success")
            return redirect(url_for("home"))
        return render_template("login.html")

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        flash("You have been logged out.", "info")
        return redirect(url_for("home"))

    # ------------------------------------------------------------ profile
    @app.route("/profile")
    @login_required
    def profile():
        data = get_services().profiles.dashboard(current_user)
        return render_template("profile.html", user=current_user, **data)

    @app.route("/profile/edit", methods=["GET", "POST"])
    @login_required
    def edit_profile():
        s = get_services()
        if request.method == "POST":
            s.profiles.update(current_user.id, request.form,
                              picture=request.files.get("picture"),
                              remove_picture=request.form.get("remove_picture") == "on")
            flash("Profile updated successfully!", "success")
            return redirect(url_for("profile"))
        return render_template("edit_profile.html", profile=s.profiles.get_or_create(current_user.id))

    @app.route("/u/<username>")
    def public_profile(username):
        viewer = current_user.id if current_user.is_authenticated else None
        data = get_services().profiles.public_view(username, viewer)
        return render_template("public_profile.html", **data)

    @app.route("/health-info", methods=["GET", "POST"])
    @login_required
    def health_info():
        if request.method == "POST":
            s = get_services()
            if request.form.get("form_type") == "measurement":
                s.health.record_measurements(current_user.id, request.form.get("weight"),
                                             request.form.get("height"),
                                             request.form.get("date_measured"))
                flash("Body measurements saved!", "success")
            elif request.form.get("form_type") == "health_status":
                s.health.record_status(current_user.id, request.form.get("is_healthy") == "y",
                                       request.form.get("notes"), request.form.get("checkup_date"))
                flash("Health status updated!", "success")
            return redirect(url_for("profile"))
        return render_template("health_info.html")

    # ------------------------------------------------------------ donations
    @app.route("/add_donation", methods=["GET", "POST"])
    @login_required
    def add_donation():
        s = get_services()
        if request.method == "POST":
            s.donations.log(current_user.id, request.form.get("date_donated"),
                            request.form.get("location"), request.form.get("event_name"),
                            request.form.get("community_id"))
            flash("Donation record added successfully!", "success")
            return redirect(url_for("profile"))
        return render_template("add_donation.html",
                               my_communities=s.donations.my_communities(current_user.id))

    # ------------------------------------------------------------ communities
    @app.route("/communities")
    def communities():
        return render_template("communities.html", communities=get_services().communities.list_all())

    @app.route("/communities/new", methods=["GET", "POST"])
    @login_required
    def create_community():
        if request.method == "POST":
            community = get_services().communities.create(
                current_user.id, request.form.get("name"), request.form.get("description"))
            flash("Community created!", "success")
            return redirect(url_for("community_detail", community_id=community.id))
        return render_template("create_community.html")

    @app.route("/communities/<int:community_id>")
    def community_detail(community_id):
        viewer = current_user.id if current_user.is_authenticated else None
        community, members, is_member = get_services().communities.detail(community_id, viewer)
        return render_template("community_detail.html", community=community,
                               members=members, is_member=is_member)

    @app.route("/communities/<int:community_id>/join", methods=["POST"])
    @login_required
    def join_community(community_id):
        community, changed = get_services().communities.join(current_user.id, community_id)
        if changed:
            flash(f"You joined {community.name}!", "success")
        return redirect(url_for("community_detail", community_id=community_id))

    @app.route("/communities/<int:community_id>/leave", methods=["POST"])
    @login_required
    def leave_community(community_id):
        community, changed = get_services().communities.leave(current_user.id, community_id)
        if changed:
            flash(f"You left {community.name}.", "info")
        return redirect(url_for("community_detail", community_id=community_id))

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
