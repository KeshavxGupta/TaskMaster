# app.py
from flask import Flask, render_template, redirect, url_for, flash, request, current_app
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from forms import TaskForm, RegistrationForm, LoginForm  # Ensure your forms are defined appropriately
from models import User, Feedback, Task
from admin import admin as admin_blueprint
from api import api as api_blueprint
from extensions import db  # Use the single SQLAlchemy instance
from datetime import datetime
import os
from werkzeug.utils import secure_filename
import requests

app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(basedir, "data.sqlite")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = "my-secret-key"  # Or use an environment variable
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize the SQLAlchemy instance with the Flask app.
db.init_app(app)

bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def create_admin_user():
    admin_email = "admin@example.com"
    admin_password = "admin123"
    admin_user = User.query.filter_by(email=admin_email).first()
    if not admin_user:
        admin_user = User(
            username="admin",
            email=admin_email,
            phone_number="1234567890",  # Adding required phone number
            date_of_birth=datetime(1990, 1, 1).date()  # Adding required date of birth
        )
        admin_user.user_type = "admin"  # Changed from role to user_type
        admin_user.password = admin_password  # Uses the password setter
        db.session.add(admin_user)
        db.session.commit()
        print("Admin user created with email:", admin_email, "and password:", admin_password)
    else:
        print("Admin user already exists.")

with app.app_context():
    db.create_all()  # Creates fresh tables since data.sqlite is deleted
    create_admin_user()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/about")
def about():
    return render_template("about.html")

@app.route('/feedback', methods=['GET', 'POST'])
def feedback():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        message = request.form['message']
        new_feedback = Feedback(name=name, email=email, message=message)
        db.session.add(new_feedback)
        db.session.commit()
        flash("Thank you for your feedback!", "success")
        return redirect(url_for("dashboard"))
    return render_template('feedback.html')

@app.route("/signup", methods=["GET", "POST"])
def signup():
    form = RegistrationForm()
    if form.validate_on_submit():
        # Check if email already exists
        if User.query.filter_by(email=form.email.data).first():
            flash('Email already exists!', 'error')
            return render_template("signup.html", form=form)
        
        # Check if username already exists
        if User.query.filter_by(username=form.username.data).first():
            flash('Username already taken!', 'error')
            return render_template("signup.html", form=form)
        
        user = User(
            username=form.username.data,
            email=form.email.data,
            phone_number=form.phone_number.data,
            date_of_birth=form.date_of_birth.data,
            user_type="user"  # Default to regular user
        )
        user.password = form.password.data  # Uses the password setter
        
        db.session.add(user)
        db.session.commit()
        flash("Account created successfully", "success")
        return redirect(url_for("login"))
    return render_template("signup.html", form=form)

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        if current_user.user_type == 'admin':
            return redirect(url_for("admin.admindashboard"))
        return redirect(url_for("dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.verify_password(form.password.data):
            # Check if the user type matches
            if user.user_type != form.user_type.data:
                flash(f'Invalid user type. Please select {user.user_type}.', 'error')
                return render_template("login.html", form=form)
            
            login_user(user)
            flash("Login successful", "success")
            if user.user_type == 'admin':
                return redirect(url_for("admin.admindashboard"))
            return redirect(url_for("dashboard"))
        flash("Invalid username or password", "error")
    return render_template("login.html", form=form)

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.user_type == 'admin':
        return redirect(url_for('admin.admindashboard'))
    
    form = TaskForm()
    tasks = Task.query.filter_by(user_id=current_user.id).all()
    filter_type = request.args.get('filter', 'all')
    if filter_type == 'pending':
        tasks = Task.query.filter_by(user_id=current_user.id, status='pending').all()
    elif filter_type == 'completed':
        tasks = Task.query.filter_by(user_id=current_user.id, status='completed').all()
    elif filter_type == 'overdue':
        tasks = Task.query.filter(
            Task.user_id == current_user.id,
            Task.due_date < datetime.utcnow(),
            Task.status != 'completed'
        ).all()
    total_tasks = Task.query.filter_by(user_id=current_user.id).count()
    completed_tasks = Task.query.filter_by(user_id=current_user.id, status='completed').count()
    pending_tasks = Task.query.filter_by(user_id=current_user.id, status='pending').count()
    overdue_tasks = Task.query.filter(
        Task.user_id == current_user.id,
        Task.due_date < datetime.utcnow(),
        Task.status != 'completed'
    ).count()
    return render_template('dashboard.html',
                           user=current_user,
                           tasks=tasks,
                           form=form,
                           total_tasks=total_tasks,
                           completed_tasks=completed_tasks,
                           pending_tasks=pending_tasks,
                           overdue_tasks=overdue_tasks)

@app.route('/task/add', methods=['POST'])
@login_required
def add_task():
    form = TaskForm()
    if form.validate_on_submit():
        try:
            # Check for duplicate tasks
            existing_task = Task.query.filter_by(
                user_id=current_user.id,
                title=form.title.data,
                due_date=form.due_date.data,
                priority=form.priority.data,
                category=form.category.data
            ).first()

            if existing_task:
                flash('A task with the same details already exists.', 'warning')
                return redirect(url_for('dashboard'))

            # Create new task if no duplicate is found
            tags = [tag.strip() for tag in form.tags.data.split(',') if tag.strip()]
            task = Task(
                title=form.title.data,
                due_date=form.due_date.data,
                priority=form.priority.data,
                category=form.category.data,
                tags=tags,
                user_id=current_user.id
            )
            db.session.add(task)
            db.session.commit()
            flash('Task created successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating task: {str(e)}', 'error')
    return redirect(url_for('dashboard'))

@app.route('/task/edit/<int:task_id>', methods=['GET', 'POST'])
@login_required
def edit_task(task_id):
    task = Task.query.get_or_404(task_id)
    if task.user_id != current_user.id:
        flash('Unauthorized access!', 'error')
        return redirect(url_for('dashboard'))

    form = TaskForm(obj=task)

    if request.method == 'GET':
        form.tags.data = ', '.join(task.tags) if task.tags else ''
        return render_template('edit_task.html', form=form, task=task)

    if form.validate_on_submit():
        try:
            task.title = form.title.data
            task.due_date = form.due_date.data
            task.priority = form.priority.data
            task.category = form.category.data
            task.tags = [tag.strip() for tag in form.tags.data.split(',') if tag.strip()]
            db.session.commit()
            flash('Task updated successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating task: {str(e)}', 'error')
        return redirect(url_for('dashboard'))

    # If form validation fails, re-render the form with errors
    flash('Please correct the errors in the form.', 'error')
    return render_template('edit_task.html', form=form, task=task)

@app.route('/task/delete/<int:task_id>')
@login_required
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    if task.user_id != current_user.id:
        flash('Unauthorized access!', 'error')
        return redirect(url_for('dashboard'))
    try:
        db.session.delete(task)
        db.session.commit()
        flash('Task deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting task: {str(e)}', 'error')
    return redirect(url_for('dashboard'))

@app.route('/task/toggle/<int:task_id>')
@login_required
def toggle_task(task_id):
    task = Task.query.get_or_404(task_id)
    if task.user_id != current_user.id:
        flash('Unauthorized access!', 'error')
        return redirect(url_for('dashboard'))

    try:
        current_app.logger.info(f"Toggling task ID: {task_id}, Current Status: {task.status}")
        task.status = 'completed' if task.status == 'pending' else 'pending'
        db.session.commit()
        current_app.logger.info(f"Task ID: {task_id} toggled successfully to {task.status}")
        flash('Task status updated successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error toggling task ID: {task_id}: {str(e)}")
        flash(f'Error updating task status: {str(e)}', 'error')

    return redirect(url_for('dashboard'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        try:
            if 'profile_picture' in request.files:
                file = request.files['profile_picture']
                if file and file.filename and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    filename = f"{datetime.now().timestamp()}_{filename}"
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(file_path)
                    current_user.profile_picture = os.path.join('uploads', filename)
            new_email = request.form.get('email')
            if new_email != current_user.email:
                existing_user = User.query.filter_by(email=new_email).first()
                if existing_user:
                    flash('Email already exists!', 'error')
                    return redirect(url_for('profile'))
                current_user.email = new_email
            current_user.username = request.form.get('username')
            current_user.phone = request.form.get('phone')
            current_user.gender = request.form.get('gender')
            dob = request.form.get('dob')
            if dob:
                try:
                    current_user.dob = datetime.strptime(dob, '%Y-%m-%d').date()
                except ValueError:
                    pass
            current_user.address = request.form.get('address')
            current_user.bio = request.form.get('bio')
            current_user.social = request.form.get('social')
            new_password = request.form.get('password')
            if new_password:
                current_user.password = new_password
            db.session.commit()
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred: {str(e)}', 'error')
            return redirect(url_for('profile'))
    return render_template('profile.html', user=current_user)

@app.route("/demo")
def demo():
    return render_template("demo.html")

@app.route("/logout")
def logout():
    # Log out from Flask
    logout_user()
    flash("Logout successful", "success")

    # Log out from Django
    try:
        django_logout_url = "http://127.0.0.1:8000/logout/"  # Update with the correct Django URL
        requests.get(django_logout_url)
    except requests.RequestException as e:
        flash("Failed to log out from Django: " + str(e), "danger")

    return redirect(url_for("index"))

app.register_blueprint(admin_blueprint, url_prefix='/admin')
app.register_blueprint(api_blueprint)  # Register the API blueprint

if __name__ == "__main__":
    app.run(debug=True, port=8080)
