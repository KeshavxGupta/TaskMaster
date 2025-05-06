import unittest
import json
from datetime import datetime, date, timedelta
from app import app
from models import User, Task
from extensions import db

class TestAPI(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.client = app.test_client()
        
        with app.app_context():
            # Drop all tables and recreate them
            db.drop_all()
            db.create_all()
            
            # Create a test user
            user = User(
                username='testuser',
                email='test@example.com',
                user_type='user',
                phone_number='1234567890',
                date_of_birth=date(1990, 1, 1)
            )
            user.password = 'password123'
            db.session.add(user)
            db.session.commit()
            self.user_id = user.id
            
        # Set future date for tasks
        self.future_date = (date.today() + timedelta(days=365)).strftime('%Y-%m-%d')

    def tearDown(self):
        with app.app_context():
            # Drop all tables to clean up
            db.session.remove()
            db.drop_all()

    def test_register(self):
        data = {
            'username': 'newuser',
            'email': 'new@example.com',
            'password': 'password123',
            'phone_number': '1234567890',
            'date_of_birth': '1990-01-01'
        }
        response = self.client.post('/api/auth/register',
                                  data=json.dumps(data),
                                  content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.assertIn('User registered successfully', response.json['message'])

    def test_register_existing_user(self):
        # Try to register with existing username
        data = {
            'username': 'testuser',  # This username already exists
            'email': 'another@example.com',
            'password': 'password123',
            'phone_number': '1234567890',
            'date_of_birth': '1990-01-01'
        }
        response = self.client.post('/api/auth/register',
                                  data=json.dumps(data),
                                  content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('Username already exists', response.json['message'])

    def test_register_invalid_data(self):
        # Missing required fields
        data = {
            'username': 'newuser',
            'password': 'password123'
        }
        response = self.client.post('/api/auth/register',
                                  data=json.dumps(data),
                                  content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_login(self):
        data = {
            'username': 'testuser',
            'password': 'password123',
            'user_type': 'user'
        }
        response = self.client.post('/api/auth/login',
                                  data=json.dumps(data),
                                  content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Login successful', response.json['message'])

    def test_login_invalid_credentials(self):
        data = {
            'username': 'testuser',
            'password': 'wrongpassword',
            'user_type': 'user'
        }
        response = self.client.post('/api/auth/login',
                                  data=json.dumps(data),
                                  content_type='application/json')
        self.assertEqual(response.status_code, 401)
        self.assertIn('Invalid credentials', response.json['message'])

    def test_login_invalid_user_type(self):
        data = {
            'username': 'testuser',
            'password': 'password123',
            'user_type': 'admin'  # User is not an admin
        }
        response = self.client.post('/api/auth/login',
                                  data=json.dumps(data),
                                  content_type='application/json')
        self.assertEqual(response.status_code, 401)
        self.assertIn('Invalid user type', response.json['message'])

    def test_create_task(self):
        # First login
        login_data = {
            'username': 'testuser',
            'password': 'password123',
            'user_type': 'user'
        }
        self.client.post('/api/auth/login',
                        data=json.dumps(login_data),
                        content_type='application/json')

        # Create task
        task_data = {
            'title': 'Test Task',
            'due_date': self.future_date,
            'priority': 'high',
            'category': 'work',
            'tags': ['test', 'api']
        }
        response = self.client.post('/api/tasks',
                                  data=json.dumps(task_data),
                                  content_type='application/json')
        print("Create Task Response:", response.json)  # Debug print
        self.assertEqual(response.status_code, 201)
        self.assertIn('Task created successfully', response.json['message'])
        self.assertIn('task', response.json)
        self.assertEqual(response.json['task']['title'], 'Test Task')

    def test_create_task_invalid_data(self):
        # First login
        login_data = {
            'username': 'testuser',
            'password': 'password123',
            'user_type': 'user'
        }
        self.client.post('/api/auth/login',
                        data=json.dumps(login_data),
                        content_type='application/json')

        # Create task with invalid data
        task_data = {
            'title': '',  # Empty title
            'due_date': self.future_date,
            'priority': 'invalid_priority',  # Invalid priority
            'category': 'work'
        }
        response = self.client.post('/api/tasks',
                                  data=json.dumps(task_data),
                                  content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_create_task_past_due_date(self):
        # First login
        login_data = {
            'username': 'testuser',
            'password': 'password123',
            'user_type': 'user'
        }
        self.client.post('/api/auth/login',
                        data=json.dumps(login_data),
                        content_type='application/json')

        # Create task with past due date
        task_data = {
            'title': 'Past Due Task',
            'due_date': '2020-01-01',  # Past date
            'priority': 'high',
            'category': 'work'
        }
        response = self.client.post('/api/tasks',
                                  data=json.dumps(task_data),
                                  content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('Due date cannot be in the past', response.json['message'])

    def test_get_tasks(self):
        # First login
        login_data = {
            'username': 'testuser',
            'password': 'password123',
            'user_type': 'user'
        }
        self.client.post('/api/auth/login',
                        data=json.dumps(login_data),
                        content_type='application/json')

        # Create multiple tasks
        task_data1 = {
            'title': 'Task 1',
            'due_date': self.future_date,
            'priority': 'high',
            'category': 'work',
            'tags': ['test']
        }
        task_data2 = {
            'title': 'Task 2',
            'due_date': self.future_date,
            'priority': 'low',
            'category': 'personal',
            'tags': ['api']
        }
        self.client.post('/api/tasks',
                        data=json.dumps(task_data1),
                        content_type='application/json')
        self.client.post('/api/tasks',
                        data=json.dumps(task_data2),
                        content_type='application/json')

        # Get all tasks
        response = self.client.get('/api/tasks')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json['tasks']), 2)

        # Test filtering by priority
        response = self.client.get('/api/tasks?priority=high')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json['tasks']), 1)
        self.assertEqual(response.json['tasks'][0]['priority'], 'high')

        # Test filtering by category
        response = self.client.get('/api/tasks?category=personal')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json['tasks']), 1)
        self.assertEqual(response.json['tasks'][0]['category'], 'personal')

    def test_update_task(self):
        # First login
        login_data = {
            'username': 'testuser',
            'password': 'password123',
            'user_type': 'user'
        }
        self.client.post('/api/auth/login',
                        data=json.dumps(login_data),
                        content_type='application/json')

        # Create a task
        task_data = {
            'title': 'Test Task',
            'due_date': self.future_date,
            'priority': 'high',
            'category': 'work',
            'tags': ['test', 'api']
        }
        create_response = self.client.post('/api/tasks',
                                         data=json.dumps(task_data),
                                         content_type='application/json')
        task_id = create_response.json['task']['id']

        # Update task
        update_data = {
            'title': 'Updated Task',
            'priority': 'medium'
        }
        response = self.client.put(f'/api/tasks/{task_id}',
                                 data=json.dumps(update_data),
                                 content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['task']['title'], 'Updated Task')
        self.assertEqual(response.json['task']['priority'], 'medium')

    def test_update_nonexistent_task(self):
        # First login
        login_data = {
            'username': 'testuser',
            'password': 'password123',
            'user_type': 'user'
        }
        self.client.post('/api/auth/login',
                        data=json.dumps(login_data),
                        content_type='application/json')

        # Try to update non-existent task
        update_data = {
            'title': 'Updated Task',
            'priority': 'medium'
        }
        response = self.client.put('/api/tasks/999',
                                 data=json.dumps(update_data),
                                 content_type='application/json')
        self.assertEqual(response.status_code, 404)

    def test_delete_task(self):
        # First login
        login_data = {
            'username': 'testuser',
            'password': 'password123',
            'user_type': 'user'
        }
        self.client.post('/api/auth/login',
                        data=json.dumps(login_data),
                        content_type='application/json')

        # Create a task
        task_data = {
            'title': 'Test Task',
            'due_date': self.future_date,
            'priority': 'high',
            'category': 'work',
            'tags': ['test', 'api']
        }
        create_response = self.client.post('/api/tasks',
                                         data=json.dumps(task_data),
                                         content_type='application/json')
        task_id = create_response.json['task']['id']

        # Delete task
        response = self.client.delete(f'/api/tasks/{task_id}')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Task deleted successfully', response.json['message'])

        # Verify task is deleted
        get_response = self.client.get(f'/api/tasks/{task_id}')
        self.assertEqual(get_response.status_code, 404)

    def test_toggle_task(self):
        # First login
        login_data = {
            'username': 'testuser',
            'password': 'password123',
            'user_type': 'user'
        }
        self.client.post('/api/auth/login',
                        data=json.dumps(login_data),
                        content_type='application/json')

        # Create a task
        task_data = {
            'title': 'Test Task',
            'due_date': self.future_date,
            'priority': 'high',
            'category': 'work',
            'tags': ['test', 'api']
        }
        create_response = self.client.post('/api/tasks',
                                         data=json.dumps(task_data),
                                         content_type='application/json')
        task_id = create_response.json['task']['id']

        # Toggle task status
        response = self.client.post(f'/api/tasks/{task_id}/toggle')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Task status updated successfully', response.json['message'])

        # Verify task is completed
        get_response = self.client.get(f'/api/tasks/{task_id}')
        self.assertEqual(get_response.json['task']['status'], 'completed')

        # Toggle back to pending
        response = self.client.post(f'/api/tasks/{task_id}/toggle')
        self.assertEqual(response.status_code, 200)
        get_response = self.client.get(f'/api/tasks/{task_id}')
        self.assertEqual(get_response.json['task']['status'], 'pending')

if __name__ == '__main__':
    unittest.main() 