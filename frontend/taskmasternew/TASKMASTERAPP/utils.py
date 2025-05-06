from django.core.cache import cache
from .models import Task, CustomUser
from .api_client import api_client
from django.utils import timezone
from datetime import datetime

def sync_flask_tasks(user=None):
    """Synchronize tasks from Flask to Django database"""
    try:
        # Fetch tasks from Flask
        params = {}
        if user:
            params['username'] = user.username
        response = api_client.get_tasks(params)
        tasks = response.get('tasks', [])
        
        # Update Django database
        for task_data in tasks:
            # Get or create user
            task_user, _ = CustomUser.objects.get_or_create(
                username=task_data.get('username', 'default_user'),
                defaults={
                    'email': task_data.get('email', ''),
                    'user_type': 'user'
                }
            )
            
            # Convert date string to date object if needed
            due_date = task_data['due_date']
            if isinstance(due_date, str):
                due_date = datetime.strptime(due_date, '%Y-%m-%d').date()
            
            # Update or create task
            Task.objects.update_or_create(
                id=task_data['id'],
                defaults={
                    'user': task_user,
                    'title': task_data['title'],
                    'description': task_data.get('description', ''),
                    'due_date': due_date,
                    'priority': task_data['priority'],
                    'status': task_data['status'],
                    'category': task_data['category'],
                    'tags': task_data.get('tags', ''),
                    'created_at': task_data.get('created_at', timezone.now()),
                    'updated_at': task_data.get('updated_at', timezone.now())
                }
            )
        return True
    except Exception as e:
        print(f"Error syncing tasks: {str(e)}")
        return False

def get_tasks_from_both_sources(user=None):
    """Get tasks from both Django database and Flask API, ensuring no duplicates"""
    try:
        # Get tasks from Django database
        django_tasks = Task.objects.all()
        if user:
            django_tasks = django_tasks.filter(user=user)
        django_tasks = list(django_tasks.values())

        # Get tasks from Flask API
        params = {}
        if user:
            params['username'] = user.username
        flask_response = api_client.get_tasks(params)

        # Check if Flask response is valid JSON
        if not flask_response or not isinstance(flask_response, dict):
            print("Error: Invalid response from Flask API. Expected JSON but received something else.")
            flask_tasks = []  # Default to an empty list if the response is invalid
        else:
            flask_tasks = flask_response.get('tasks', [])

        # Combine and deduplicate tasks
        all_tasks = {}

        # Add Django tasks
        for task in django_tasks:
            all_tasks[task['id']] = {
                'source': 'django',
                'data': task
            }

        # Add or update with Flask tasks
        for task in flask_tasks:
            # Check for duplicates based on title, due_date, and user
            duplicate = next((t for t in all_tasks.values() if t['data']['title'] == task['title'] and t['data']['due_date'] == task['due_date']), None)
            if duplicate:
                # If a duplicate exists, prefer Django data
                duplicate['source'] = 'both'
                duplicate['flask_data'] = task
            else:
                all_tasks[task['id']] = {
                    'source': 'flask',
                    'data': task
                }

        # Ensure all tasks have a 'data' key
        for task_id, task_info in all_tasks.items():
            if 'data' not in task_info:
                task_info['data'] = task_info.get('flask_data', {})

        return all_tasks
    except Exception as e:
        print(f"Error getting tasks from both sources: {str(e)}")
        return {}

def sync_flask_users():
    """Synchronize users from Flask to Django database"""
    try:
        # Fetch all users from Flask
        response = api_client.get_users()
        users = response.get('users', [])
        
        # Update Django database
        for user_data in users:
            CustomUser.objects.update_or_create(
                username=user_data['username'],
                defaults={
                    'email': user_data.get('email', ''),
                    'user_type': user_data.get('user_type', 'user'),
                    'phone_number': user_data.get('phone_number', ''),
                    'date_of_birth': user_data.get('date_of_birth'),
                    'gender': user_data.get('gender'),
                    'address': user_data.get('address', ''),
                    'bio': user_data.get('bio', ''),
                    'social': user_data.get('social', '')
                }
            )
        return True
    except Exception as e:
        print(f"Error syncing users: {str(e)}")
        return False

def get_cached_tasks(user=None):
    """Get tasks with caching from both sources"""
    cache_key = f'all_tasks_{user.username}' if user else 'all_tasks'
    cached_tasks = cache.get(cache_key)
    if cached_tasks is None:
        # Get tasks from both sources
        tasks = get_tasks_from_both_sources(user)
        # Cache for 5 minutes
        cache.set(cache_key, tasks, 300)
        return tasks
    return cached_tasks

def sync_task_to_flask(task_data):
    """Sync a single task to Flask"""
    try:
        if 'id' in task_data:
            # Update existing task
            response = api_client.update_task(task_data['id'], task_data)
        else:
            # Create new task
            response = api_client.create_task(task_data)
        return response.get('message') == 'Task created successfully' or response.get('message') == 'Task updated successfully'
    except Exception as e:
        print(f"Error syncing task to Flask: {str(e)}")
        return False