from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, render_template, redirect, url_for, flash, request
from models import db, User, Profile, Measurement, HealthStatus, Donation, Community
from datetime import datetime, date, timedelta

app = Flask(__name__)

# Configure SQLite database file and secret key
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///registry.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'super-secret-key-change-later'

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

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Handles new user registration, password hashing, and profile initialization."""
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('register'))
            
        user_exists = User.query.filter((User.username == username) | (User.email == email)).first()
        if user_exists:
            flash('Username or email already taken.', 'error')
            return redirect(url_for('register'))
            
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
    
    if total_donations >= 10:
        badge = "Champion"
    elif total_donations >= 5:
        badge = "Lifesaver"
    elif total_donations >= 3:
        badge = "Regular"
    elif total_donations >= 1:
        badge = "First Drop"
    else:
        badge = "Newcomer"
        
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
        next_eligible=next_eligible
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
    return render_template('public_profile.html', user=user, profile=profile, age=age)

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