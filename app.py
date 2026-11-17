import os
import secrets

from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, render_template, redirect, url_for, flash, request
from models import db, User, Profile, Measurement, HealthStatus, Donation, Community
from datetime import datetime, date, timedelta

app = Flask(__name__)

def get_secret_key():
    """Uses the SECRET_KEY environment variable if set, otherwise a random key
    generated once and saved in instance/secret_key (gitignored)."""
    env_key = os.environ.get('SECRET_KEY')
    if env_key:
        return env_key
    os.makedirs(app.instance_path, exist_ok=True)
    key_path = os.path.join(app.instance_path, 'secret_key')
    if os.path.exists(key_path):
        with open(key_path) as f:
            return f.read().strip()
    key = secrets.token_hex(32)
    with open(key_path, 'w') as f:
        f.write(key)
    return key

# Configure SQLite database file and secret key
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///registry.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = get_secret_key()

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    """Loads a user object from the database by user ID for Flask-Login."""
    return User.query.get(int(user_id))

# Automatically create database tables on startup
with app.app_context():
    db.create_all()

def calculate_age(born):
    """Helper function to calculate a user's current age based on birthdate."""
    if not born:
        return None
    today = date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))

BLOOD_TYPES = {'A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'}

def validate_profile_form(form):
    """Validates the edit-profile form. Returns (cleaned_values, errors)."""
    errors = []
    full_name = (form.get('full_name') or '').strip()
    location = (form.get('location') or '').strip()
    sex = (form.get('sex') or '').strip()
    bio = (form.get('bio') or '').strip()
    blood_type = (form.get('blood_type') or '').strip()

    if len(full_name) > 100:
        errors.append('Full name must be 100 characters or fewer.')
    if len(location) > 100:
        errors.append('Location must be 100 characters or fewer.')
    if len(sex) > 20:
        errors.append('Sex must be 20 characters or fewer.')
    if len(bio) > 1000:
        errors.append('Bio must be 1000 characters or fewer.')
    if blood_type and blood_type not in BLOOD_TYPES:
        errors.append('Please choose a valid blood type.')

    birthdate = None
    birthdate_str = (form.get('birthdate') or '').strip()
    if birthdate_str:
        try:
            birthdate = date.fromisoformat(birthdate_str)
        except ValueError:
            errors.append('Birthdate is not a valid date.')
        else:
            if birthdate > date.today():
                errors.append('Birthdate cannot be in the future.')
            elif calculate_age(birthdate) > 120:
                errors.append('Please enter a realistic birthdate.')

    cleaned = {
        'full_name': full_name or None,
        'location': location or None,
        'sex': sex or None,
        'bio': bio or None,
        'blood_type': blood_type or None,
        'birthdate': birthdate,  # None clears the birthdate
        'is_public': form.get('is_public') == 'on',
    }
    return cleaned, errors

def get_badge(total):
    """Returns the credential badge name for a given number of donations."""
    if total >= 10:
        return "Champion"
    elif total >= 5:
        return "Lifesaver"
    elif total >= 3:
        return "Regular"
    elif total >= 1:
        return "First Drop"
    return "Newcomer"

def donation_stats(donations):
    """Returns (donations in the last 12 months, average days between donations)."""
    one_year_ago = date.today() - timedelta(days=365)
    last_12_months = sum(1 for d in donations if d.date_donated >= one_year_ago)

    avg_gap = None
    if len(donations) >= 2:
        dates = sorted(d.date_donated for d in donations)
        gaps = [(dates[i] - dates[i - 1]).days for i in range(1, len(dates))]
        avg_gap = round(sum(gaps) / len(gaps))
    return last_12_months, avg_gap

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Handles new user registration, password hashing, and profile initialization."""
    if request.method == 'POST':
        cleaned, errors = validate_profile_form(request.form)
        if errors:
            for message in errors:
                flash(message, 'error')
            return render_template('edit_profile.html', profile=user_profile)

        for field, value in cleaned.items():
            setattr(user_profile, field, value)
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile'))
            
        hashed_password = generate_password_hash(password)
        new_user = User(username=username, email=email, password_hash=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        
        new_profile = Profile(user_id=new_user.id)
        db.session.add(new_profile)
        db.session.commit()
        
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route("/")
def home():
    """Renders the home page."""
    return render_template("index.html")

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handles user login credentials verification and session creation."""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash('Logged in successfully!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid email or password.', 'error')
            
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    """Logs out the current active user and ends their session."""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))

@app.route('/profile')
@login_required
def profile():
    """Renders the private user dashboard containing personal details, health metrics, BMI, and Phase 7 donation history/badges."""
    uid = current_user.id

    # Fetch profile and calculate age
    user_profile = Profile.query.filter_by(user_id=uid).first()
    age = calculate_age(user_profile.birthdate) if user_profile and user_profile.birthdate else None

    # Fetch latest body and health stats
    latest_weight = Measurement.query.filter_by(user_id=uid, type="weight") \
        .order_by(Measurement.date_measured.desc(), Measurement.id.desc()).first()

    latest_height = Measurement.query.filter_by(user_id=uid, type="height") \
        .order_by(Measurement.date_measured.desc(), Measurement.id.desc()).first()

    latest_health = HealthStatus.query.filter_by(user_id=uid) \
        .order_by(HealthStatus.date_checked.desc(), HealthStatus.id.desc()).first()

    # Calculate BMI
    bmi = None
    bmi_date = None
    if latest_weight and latest_height and latest_height.value > 0:
        height_m = latest_height.value / 100.0
        bmi = round(latest_weight.value / (height_m ** 2), 1)
        bmi_date = max(latest_weight.date_measured, latest_height.date_measured)

    # Phase 7: Fetch donations, calculate points, determine credential badges & eligibility
    donations = Donation.query.filter_by(user_id=uid).order_by(Donation.date_donated.desc()).all()
    total_donations = len(donations)
    points = total_donations * 10
    
    badge = get_badge(total_donations)
    last_12_months, avg_gap = donation_stats(donations) 
        
    last_donated = donations[0].date_donated if donations else None
    next_eligible = last_donated + timedelta(weeks=8) if last_donated else None

    return render_template(
        'profile.html',
        user=current_user,
        profile=user_profile,
        age=age,
        latest_weight=latest_weight,
        latest_height=latest_height,
        latest_health=latest_health,
        bmi=bmi,
        bmi_date=bmi_date,
        donations=donations,
        total_donations=total_donations,
        points=points,
        badge=badge,
        last_donated=last_donated,
        next_eligible=next_eligible,
        last_12_months=last_12_months,
        avg_gap=avg_gap
    )
    

@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    """Allows users to edit and update their profile bio, blood type, location, and privacy status."""
    user_profile = Profile.query.filter_by(user_id=current_user.id).first()
    if not user_profile:
        user_profile = Profile(user_id=current_user.id)
        db.session.add(user_profile)
        db.session.commit()

    if request.method == 'POST':
        user_profile.full_name = request.form.get('full_name')
        user_profile.location = request.form.get('location')
        user_profile.blood_type = request.form.get('blood_type')
        user_profile.sex = request.form.get('sex')
        
        birthdate_str = request.form.get('birthdate')
        if birthdate_str:
            user_profile.birthdate = date.fromisoformat(birthdate_str)
            
        user_profile.bio = request.form.get('bio')
        user_profile.is_public = True if request.form.get('is_public') == 'on' else False
        
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile'))

    return render_template('edit_profile.html', profile=user_profile)

@app.route('/u/<username>')
def public_profile(username):
    """Renders a public profile page for a given username if public visibility is enabled."""
    user = User.query.filter_by(username=username).first_or_404()
    profile = Profile.query.filter_by(user_id=user.id).first()

    if not profile or (not profile.is_public and current_user != user):
        flash('This profile is private.', 'warning')
        return redirect(url_for('home'))

    age = calculate_age(profile.birthdate) if profile else None

    donations = Donation.query.filter_by(user_id=user.id).order_by(Donation.date_donated.desc()).all()
    total_donations = len(donations)
    last_12_months, avg_gap = donation_stats(donations)

    return render_template(
        'public_profile.html',
        user=user,
        profile=profile,
        age=age,
        donations=donations,
        total_donations=total_donations,
        points=total_donations * 10,
        badge=get_badge(total_donations),
        last_12_months=last_12_months,
        avg_gap=avg_gap
    )

@app.route('/health-info', methods=['GET', 'POST'])
@login_required
def health_info():
    """Handles submission forms for updating body measurements (weight/height) and health check-up status."""
    if request.method == 'POST':
        form_type = request.form.get('form_type')

        if form_type == 'measurement':
            weight = request.form.get('weight')
            height = request.form.get('height')
            date_str = request.form.get('date_measured')
            date_measured = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else date.today()
    
            if weight:
                db.session.add(Measurement(
                    user_id=current_user.id,
                    type="weight",
                    value=float(weight),
                    date_measured=date_measured
                ))
            if height:
                db.session.add(Measurement(
                    user_id=current_user.id,
                    type="height",
                    value=float(height),
                    date_measured=date_measured
                ))
            db.session.commit()
            flash('Body measurements saved!', 'success')

        elif form_type == 'health_status':
            is_healthy_val = "Healthy" if request.form.get('is_healthy') == 'y' else "Not Healthy"
            notes = request.form.get('notes')
            checkup_str = request.form.get('checkup_date')
            checkup_date = datetime.strptime(checkup_str, '%Y-%m-%d').date() if checkup_str else date.today()

            db.session.add(HealthStatus(
                user_id=current_user.id,
                status=is_healthy_val,
                notes=notes,
                date_checked=checkup_date
            ))
            db.session.commit()
            flash('Health status updated!', 'success')

        return redirect(url_for('profile'))
    return render_template('health_info.html')

@app.route('/add_donation', methods=['GET', 'POST'])
@login_required
def add_donation():
    """Handles logging new blood donation records to update user credentials, point counts, and timelines."""
    if request.method == 'POST':
        date_str = request.form.get('date_donated')
        location = request.form.get('location')
        event_name = request.form.get('event_name')
        
        try:
            date_donated = datetime.strptime(date_str, '%Y-%m-%d').date()
            new_donation = Donation(
                user_id=current_user.id,
                date_donated=date_donated,
                location=location,
                event_name=event_name,
                community_id=None
            )
            db.session.add(new_donation)
            db.session.commit()
            flash('Donation record added successfully!', 'success')
            return redirect(url_for('profile'))
        except Exception as e:
            flash(f'Error adding donation: {e}', 'danger')
        
    return render_template('add_donation.html')

if __name__ == '__main__':
    app.run(debug=True)