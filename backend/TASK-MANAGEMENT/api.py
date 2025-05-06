from flask import Blueprint, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash
from models import User, Task
from forms import RegistrationForm, LoginForm, TaskForm
from extensions import db, bcrypt
from datetime import datetime, date
from flask import current_app, Flask

app = Flask(__name__)
api = Blueprint('api', __name__)

# Global error handlers
@app.errorhandler(404)
def handle_404_error(e):
    return jsonify({'error': 'Not Found', 'message': str(e)}), 404

@app.errorhandler(500)
def handle_500_error(e):
    return jsonify({'error': 'Internal Server Error', 'message': str(e)}), 500

@app.errorhandler(Exception)
def handle_generic_error(e):
    return jsonify({'error': 'Unexpected Error', 'message': str(e)}), 500

# Authentication APIs
@api.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['username', 'email', 'password', 'phone_number', 'date_of_birth']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'message': f'Missing required field: {field}'}), 400
    
    # Check if user already exists
    if User.query.filter_by(email=data.get('email')).first():
        return jsonify({'message': 'Email already registered'}), 400
    
    if User.query.filter_by(username=data.get('username')).first():
        return jsonify({'message': 'Username already exists'}), 400
    
    try:
        user = User(
            username=data.get('username'),
            email=data.get('email'),
            phone_number=data.get('phone_number'),
            date_of_birth=datetime.strptime(data.get('date_of_birth'), '%Y-%m-%d').date(),
            user_type='user'
        )
        user.password = data.get('password')
        
        db.session.add(user)
        db.session.commit()
        
        return jsonify({
            'message': 'User registered successfully',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email
            }
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': str(e)}), 400

@api.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(username=data.get('username')).first()
    
    if user and user.verify_password(data.get('password')):
        if user.user_type != data.get('user_type'):
            return jsonify({'message': 'Invalid user type'}), 401
        
        login_user(user)
        return jsonify({
            'message': 'Login successful',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'user_type': user.user_type
            }
        }), 200
    
    return jsonify({'message': 'Invalid credentials'}), 401

@api.route('/api/auth/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return jsonify({'message': 'Logout successful'}), 200

# Task Management APIs
@api.route('/api/tasks', methods=['GET'])
@login_required
def get_tasks():
    query = Task.query.filter_by(user_id=current_user.id)
    
    # Apply filters
    priority = request.args.get('priority')
    category = request.args.get('category')
    status = request.args.get('status')
    
    if priority:
        query = query.filter_by(priority=priority)
    if category:
        query = query.filter_by(category=category)
    if status:
        query = query.filter_by(status=status)
    
    tasks = query.all()
    return jsonify({
        'tasks': [{
            'id': task.id,
            'title': task.title,
            'due_date': task.due_date.strftime('%Y-%m-%d'),
            'priority': task.priority,
            'category': task.category,
            'tags': task.tags,
            'status': task.status
        } for task in tasks]
    }), 200

@api.route('/api/tasks/<int:task_id>', methods=['GET'])
@login_required
def get_task(task_id):
    task = Task.query.get_or_404(task_id)
    
    if task.user_id != current_user.id:
        return jsonify({'message': 'Unauthorized access'}), 403
    
    return jsonify({
        'task': {
            'id': task.id,
            'title': task.title,
            'due_date': task.due_date.strftime('%Y-%m-%d'),
            'priority': task.priority,
            'category': task.category,
            'tags': task.tags,
            'status': task.status
        }
    }), 200

@api.route('/api/tasks', methods=['POST'])
@login_required
def create_task():
    data = request.get_json()
    current_app.logger.debug(f"Received data: {data}")  # Using Flask's logger instead of print
    
    # Validate required fields
    if not data.get('title'):
        return jsonify({'message': 'Title is required'}), 400
    
    # Validate priority
    valid_priorities = ['low', 'medium', 'high']
    if data.get('priority') and data.get('priority') not in valid_priorities:
        return jsonify({'message': 'Invalid priority'}), 400
    
    # Validate due date
    try:
        due_date = datetime.strptime(data.get('due_date'), '%Y-%m-%d').date()
        today = date.today()
        current_app.logger.debug(f"Due date: {due_date}")  # Using Flask's logger
        current_app.logger.debug(f"Today: {today}")  # Using Flask's logger
        if due_date < today:
            return jsonify({'message': 'Due date cannot be in the past'}), 400
    except (ValueError, TypeError):
        return jsonify({'message': 'Invalid due date format'}), 400
    
    try:
        task = Task(
            title=data.get('title'),
            due_date=due_date,
            priority=data.get('priority', 'medium'),
            category=data.get('category', 'general'),
            tags=data.get('tags', []),
            user_id=current_user.id,
            status='pending'
        )
        
        db.session.add(task)
        db.session.commit()
        
        return jsonify({
            'message': 'Task created successfully',
            'task': {
                'id': task.id,
                'title': task.title,
                'due_date': task.due_date.strftime('%Y-%m-%d'),
                'priority': task.priority,
                'category': task.category,
                'tags': task.tags,
                'status': task.status
            }
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': str(e)}), 400

@api.route('/api/tasks/<int:task_id>', methods=['PUT'])
@login_required
def update_task(task_id):
    task = Task.query.get_or_404(task_id)

    if task.user_id != current_user.id:
        return jsonify({'message': 'Unauthorized access'}), 403

    data = request.get_json()

    # Validate priority if provided
    if data.get('priority'):
        valid_priorities = ['low', 'medium', 'high']
        if data.get('priority') not in valid_priorities:
            return jsonify({'message': 'Invalid priority'}), 400

    # Validate due date if provided
    if data.get('due_date'):
        try:
            due_date = datetime.strptime(data.get('due_date'), '%Y-%m-%d').date()
            if due_date < date.today():
                return jsonify({'message': 'Due date cannot be in the past'}), 400
        except ValueError:
            return jsonify({'message': 'Invalid due date format'}), 400

    try:
        if data.get('title'):
            task.title = data.get('title')
        if data.get('due_date'):
            task.due_date = datetime.strptime(data.get('due_date'), '%Y-%m-%d').date()
        if data.get('priority'):
            task.priority = data.get('priority')
        if data.get('category'):
            task.category = data.get('category')
        if 'tags' in data:
            task.tags = data.get('tags')

        db.session.commit()

        return jsonify({
            'message': 'Task updated successfully',
            'task': {
                'id': task.id,
                'title': task.title,
                'due_date': task.due_date.strftime('%Y-%m-%d'),
                'priority': task.priority,
                'category': task.category,
                'tags': task.tags,
                'status': task.status
            }
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': str(e)}), 400

@api.route('/api/tasks/<int:task_id>', methods=['DELETE'])
@login_required
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    
    if task.user_id != current_user.id:
        return jsonify({'message': 'Unauthorized access'}), 403
    
    try:
        db.session.delete(task)
        db.session.commit()
        return jsonify({'message': 'Task deleted successfully'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': str(e)}), 400

@api.route('/api/tasks/<int:task_id>/toggle', methods=['POST'])
@login_required
def toggle_task(task_id):
    task = Task.query.get_or_404(task_id)
    
    if task.user_id != current_user.id:
        return jsonify({'message': 'Unauthorized access'}), 403
    
    try:
        task.status = 'completed' if task.status == 'pending' else 'pending'
        db.session.commit()
        return jsonify({
            'message': 'Task status updated successfully',
            'task': {
                'id': task.id,
                'status': task.status
            }
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': str(e)}), 400

@api.route('/api/external-login', methods=['POST'])
def external_login():
    data = request.get_json()
    current_app.logger.debug(f"Request method: {request.method}")
    current_app.logger.debug(f"Request URL: {request.url}")
    current_app.logger.debug(f"Request headers: {dict(request.headers)}")
    current_app.logger.debug(f"Request data: {data}")

    if not data or 'username' not in data or 'password' not in data:
        current_app.logger.error("Invalid request data")
        return jsonify({'error': 'Invalid request'}), 400

    username = data['username']
    password = data['password']

    # Fetch user from the database
    user = User.query.filter_by(username=username).first()
    if not user or not user.verify_password(password):
        current_app.logger.error("Invalid credentials")
        return jsonify({'error': 'Invalid credentials'}), 401

    # Create a session for the user
    login_user(user)  # This creates a session for the user

    # Log successful login
    current_app.logger.info(f"User {username} logged in successfully")

    # Return session cookie in the response
    response = jsonify({'message': 'Login successful', 'user_id': user.id})
    response.headers['Set-Cookie'] = request.cookies.get('session')
    return response

# Register the API blueprint with the Flask app
app.register_blueprint(api)

# Ensure the app runs properly
if __name__ == '__main__':
    app.run(debug=True)