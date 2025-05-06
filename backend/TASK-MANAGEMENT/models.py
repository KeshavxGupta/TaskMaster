# models.py
from datetime import datetime, date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from extensions import db

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    phone_number = db.Column(db.String(15), nullable=False)
    date_of_birth = db.Column(db.Date, nullable=False)
    user_type = db.Column(db.String(10), nullable=False, default="user")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

    def update_profile(self, data):
        for key, value in data.items():
            if hasattr(self, key) and value is not None:
                setattr(self, key, value)
        self.updated_at = datetime.utcnow()

class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)
    
    def __repr__(self):
        return f"Feedback('{self.name}', '{self.email}', '{self.message}')"

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    priority = db.Column(db.String(20), nullable=False, default='medium')
    category = db.Column(db.String(50), nullable=False, default='general')
    tags = db.Column(db.JSON, default=list)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    def __init__(self, **kwargs):
        super(Task, self).__init__(**kwargs)
        if not self.priority:
            self.priority = 'medium'
        if not self.category:
            self.category = 'general'
        if not self.status:
            self.status = 'pending'
        if not self.tags:
            self.tags = []

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'due_date': self.due_date.strftime('%Y-%m-%d'),
            'priority': self.priority,
            'category': self.category,
            'tags': self.tags,
            'status': self.status,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }
