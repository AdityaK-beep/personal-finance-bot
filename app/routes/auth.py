import re
from urllib.parse import urlparse
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models.user import User

auth_bp = Blueprint('auth', __name__)

EMAIL_REGEX = re.compile(r"^[\w\.\+\-]+@[a-zA-Z0-9\-]+(\.[a-zA-Z0-9\-]+)+$")


def is_safe_redirect(target):
    """Ensure redirect URL is relative to prevent open-redirect vulnerabilities."""
    if not target:
        return False
    ref_url = urlparse(request.host_url)
    test_url = urlparse(target)
    return test_url.scheme in ('', ref_url.scheme) and test_url.netloc in ('', ref_url.netloc)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Handle new user registration."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard_view'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        # Server-side validation
        if not username or len(username) < 2 or len(username) > 80:
            flash("Username must be between 2 and 80 characters.", "danger")
            return render_template('register.html', username=username, email=email)

        if not email or not EMAIL_REGEX.match(email):
            flash("Please provide a valid email address.", "danger")
            return render_template('register.html', username=username, email=email)

        if not password or len(password) < 6:
            flash("Password must be at least 6 characters long.", "danger")
            return render_template('register.html', username=username, email=email)

        if password != confirm_password:
            flash("Passwords do not match. Please re-enter.", "danger")
            return render_template('register.html', username=username, email=email)

        # Check for existing user
        if User.query.filter_by(email=email).first():
            flash("An account with this email already exists. Please log in.", "warning")
            return render_template('register.html', username=username, email=email)

        if User.query.filter_by(username=username).first():
            flash("This username is already taken. Please choose another.", "warning")
            return render_template('register.html', username=username, email=email)

        try:
            user = User(username=username, email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()

            login_user(user)
            flash("Account created successfully! Welcome to your Personal Finance Advisor.", "success")
            return redirect(url_for('dashboard.dashboard_view'))
        except Exception as e:
            db.session.rollback()
            flash("An error occurred during registration. Please try again.", "danger")
            return render_template('register.html', username=username, email=email)

    return render_template('register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user authentication."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard_view'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = bool(request.form.get('remember'))

        if not email or not password:
            flash("Please enter both email and password.", "danger")
            return render_template('login.html', email=email)

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            login_user(user, remember=remember)
            flash(f"Welcome back, {user.username}!", "success")

            next_page = request.args.get('next')
            if next_page and is_safe_redirect(next_page):
                return redirect(next_page)
            return redirect(url_for('dashboard.dashboard_view'))
        else:
            flash("Invalid email or password. Please verify your credentials.", "danger")
            return render_template('login.html', email=email)

    return render_template('login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """Terminate the authenticated session."""
    logout_user()
    flash("You have been securely logged out.", "info")
    return redirect(url_for('auth.login'))
