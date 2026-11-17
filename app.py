from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, render_template, redirect, url_for, flash, request
from flask import Flask, render_template
from models import db, User, Profile
from datetime import date

app = Flask(__name__)

# Configure SQLite database file and secret key[cite: 15]
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///registry.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'super-secret-key-change-later'

# Initialize SQLAlchemy with the app[cite: 15]
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' #redirect user if they arent logged in

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Automatically trigger table creation in the database[cite: 15]
with app.app_context():
    db.create_all()

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Check if passwords match
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('register'))
            
        # Check if username or email is already taken
        user_exists = User.query.filter((User.username == username) | (User.email == email)).first()
        if user_exists:
            flash('Username or email already taken.', 'error')
            return redirect(url_for('register'))
            
        # Hash password securely using werkzeug
        hashed_password = generate_password_hash(password)
        
        # Create user and empty profile
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
    return render_template("index.html")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        # Check user and password hash
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
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))

@app.route('/profile')
@login_required  # Protects this page
def profile():
    return render_template('profile.html')

def calculate_age(born):
    if not born:
        return None
    today = date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))

@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    profile = Profile.query.filter_by(user_id=current_user.id).first()
    if not profile:
        profile = Profile(user_id=current_user.id)
        db.session.add(profile)
        db.session.commit()

    if request.method == 'POST':
        profile.name = request.form.get('full_name')
        profile.location = request.form.get('location')
        profile.blood_type = request.form.get('blood_type')
        profile.sex = request.form.get('sex')
        
        birthdate_str = request.form.get('birthdate')
        if birthdate_str:
            profile.birthdate = date.fromisoformat(birthdate_str)
            
        profile.bio = request.form.get('bio')
        profile.is_public = True if request.form.get('is_public') == 'on' else False
        
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile'))

    return render_template('edit_profile.html', profile=profile)

@app.route('/u/<username>')
def public_profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    profile = Profile.query.filter_by(user_id=user.id).first()

    # Check if profile exists and is public (or if viewing own profile)
    if not profile or (not profile.is_public and current_user != user):
        flash('This profile is private.', 'warning')
        return redirect(url_for('home'))

    age = calculate_age(profile.birthdate) if profile else None
    return render_template('public_profile.html', user=user, profile=profile, age=age)

@app.route('/profile')
@login_required
def profile_page():
    # Fetch the profile linked to the current user
    user_profile = Profile.query.filter_by(user_id=current_user.id).first()
    age = calculate_age(user_profile.birthdate) if user_profile and user_profile.birthdate else None
    return render_template('profile.html', profile=user_profile, age=age)

if __name__ == '__main__':
    app.run(debug=True)