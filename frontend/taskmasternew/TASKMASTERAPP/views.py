from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.utils import timezone
from datetime import timedelta, datetime
from .forms import CustomUserCreationForm, TaskForm
from .models import Task, Feedback, CustomUser
from .api_client import api_client
from .utils import (
    sync_flask_tasks, 
    sync_flask_users, 
    get_cached_tasks, 
    get_tasks_from_both_sources,
    sync_task_to_flask
)
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

def index(request):
    return render(request, 'index.html')

def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST, request.FILES)
        if form.is_valid():
            # First create user in Django database
            user = form.save(commit=False)
            user.user_type = form.cleaned_data.get('user_type', 'user')
            user.save()
            
            # Then register with Flask API
            data = {
                'username': form.cleaned_data['username'],
                'email': form.cleaned_data['email'],
                'password': form.cleaned_data['password1'],
                'phone_number': form.cleaned_data.get('phone_number', ''),
                'date_of_birth': form.cleaned_data.get('date_of_birth', '').strftime('%Y-%m-%d'),
                'user_type': user.user_type
            }
            
            response = api_client.register(data)
            if response.get('message') == 'User registered successfully':
                messages.success(request, 'Account created successfully! Please login to continue.')
                return redirect('login')
            else:
                # If Flask registration fails, delete Django user and show error
                user.delete()
                messages.error(request, response.get('message', 'Registration failed'))
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = CustomUserCreationForm()
    return render(request, 'users/register.html', {'form': form})

def user_login(request):
    if request.user.is_authenticated:
        if request.user.user_type == 'admin':
            return redirect('admin_dashboard')
        return redirect('dashboard')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user_type = request.POST.get('user_type', 'user')
        
        # First try to authenticate with Django database
        user = authenticate(request, username=username, password=password)
        
        if user is None:
            # If Django authentication fails, try Flask API
            response = api_client.login({
                'username': username,
                'password': password,
                'user_type': user_type
            })
            
            if response.get('message') == 'Login successful':
                # Create or update user in Django database
                user, created = CustomUser.objects.get_or_create(
                    username=username,
                    defaults={
                        'email': response['user']['email'],
                        'user_type': user_type
                    }
                )
                
                # Update user data from Flask if needed
                if not created:
                    user.email = response['user']['email']
                    user.user_type = user_type
                    user.save()
                
                # Set password for future Django authentication
                user.set_password(password)
                user.save()
                
                # Login the user
                login(request, user)
                messages.success(request, 'Logged in successfully!')
                
                if user_type == 'admin':
                    return redirect('admin_dashboard')
                return redirect('dashboard')
            else:
                messages.error(request, response.get('message', 'Invalid credentials'))
        else:
            # Django authentication successful
            if user.user_type != user_type:
                messages.error(request, f'Invalid user type. Please login as {user.user_type}')
                return render(request, 'users/login.html')
            
            login(request, user)
            messages.success(request, 'Logged in successfully!')
            
            # Notify Flask of successful login
            flask_response = api_client.login({
                'username': username,
                'password': password,
                'user_type': user_type
            })

            if flask_response.get('message') == 'Login successful':
                messages.success(request, 'Logged in successfully on both Django and Flask!')
            else:
                messages.warning(request, 'Logged in locally, but failed to log in on Flask backend.')
            
            if user_type == 'admin':
                return redirect('admin_dashboard')
            return redirect('dashboard')
    
    return render(request, 'users/login.html')

def user_logout(request):
    api_client.logout()
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('index')

@login_required
def dashboard(request):
    # Fetch only Flask tasks
    flask_tasks = api_client.get_tasks() or []
    # If Flask returns a dict with 'tasks' key, adjust accordingly
    if isinstance(flask_tasks, dict) and 'tasks' in flask_tasks:
        flask_tasks = flask_tasks['tasks']

    # Filter tasks based on status
    filter_param = request.GET.get('filter', 'all')
    filtered_tasks = [
    task for task in flask_tasks
    if isinstance(task, dict) and (filter_param == 'all' or task.get('status') == filter_param)
]

    # Ensure due_date is a string in 'YYYY-MM-DD' format for each task
    for task in filtered_tasks:
        due_date = task.get('due_date')
        if due_date:
            if not isinstance(due_date, str):
                try:
                    # Try to format if it's a date or datetime object
                    task['due_date'] = due_date.strftime('%Y-%m-%d')
                except Exception:
                    # If it's not a date object, just cast to string
                    task['due_date'] = str(due_date)

    # Calculate statistics
    total_tasks = len(filtered_tasks)
    completed_tasks = len([t for t in filtered_tasks if t.get('status') == 'completed'])
    pending_tasks = len([t for t in filtered_tasks if t.get('status') == 'pending'])
    overdue_tasks = len([t for t in filtered_tasks if t.get('status') == 'overdue'])

    context = {
        'user': request.user,
        'tasks': filtered_tasks,
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'pending_tasks': pending_tasks,
        'overdue_tasks': overdue_tasks,
    }
    return render(request, 'users/dashboard.html', context)

@login_required
def profile_view(request):
    user = request.user

    if request.method == 'POST':
        # Handle profile picture upload first
        if 'profile_picture' in request.FILES:
            # Delete the old profile picture if it exists and is not the default
            if user.profile_picture and 'default-profile.jpg' not in user.profile_picture.name:
                user.profile_picture.delete(save=False)
            user.profile_picture = request.FILES['profile_picture']

        # Update other user fields
        user.username = request.POST.get('username', user.username)
        user.email = request.POST.get('email', user.email)
        user.phone_number = request.POST.get('phone', user.phone_number)
        user.gender = request.POST.get('gender', user.gender)
        user.date_of_birth = request.POST.get('dob', user.date_of_birth)
        user.address = request.POST.get('address', user.address)
        user.bio = request.POST.get('bio', user.bio)
        user.social = request.POST.get('social', user.social)

        # Handle password change if provided
        if request.POST.get('password'):
            user.set_password(request.POST.get('password'))
            user.save()
            login(request, user)  # Re-login the user
            messages.success(request, "Profile updated and re-authenticated due to password change.")
        else:
            user.save()
            messages.success(request, "Profile updated successfully.")

        return redirect('dashboard')

    return render(request, 'users/profile.html', {'user': user})

@login_required
def add_task(request):
    if request.method == 'POST':
        form = TaskForm(request.POST)
        if form.is_valid():
            # Check if the task already exists in Django database
            existing_task = Task.objects.filter(
                user=request.user,
                title=form.cleaned_data['title'],
                due_date=form.cleaned_data['due_date'],
                priority=form.cleaned_data['priority'],
                category=form.cleaned_data['category']
            ).first()

            if existing_task:
                messages.warning(request, 'Task already exists.')
                return redirect('dashboard')

            # Create task in Django database
            task = Task.objects.create(
                user=request.user,
                title=form.cleaned_data['title'],
                due_date=form.cleaned_data['due_date'],
                priority=form.cleaned_data['priority'],
                category=form.cleaned_data['category'],
                tags=form.cleaned_data.get('tags', ''),
            )

            # Sync to Flask
            task_data = {
                'title': task.title,
                'due_date': task.due_date.strftime('%Y-%m-%d'),
                'priority': task.priority,
                'category': task.category,
                'tags': task.tags,
                'username': request.user.username
            }

            response = api_client.create_task(task_data)
            if response.get('message') == 'Task created successfully':
                messages.success(request, 'Task added successfully!')
            else:
                messages.warning(request, 'Task added locally but failed to sync with Flask.')
            return redirect('dashboard')
        else:
            # Show form errors on dashboard
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
            return redirect('dashboard')
    else:
        form = TaskForm()
    return render(request, 'add_task.html', {'form': form})

@login_required
def edit_task(request, task_id):
    # Get tasks from both sources
    all_tasks = get_tasks_from_both_sources(request.user)
    task_info = all_tasks.get(task_id)

    if not task_info:
        messages.error(request, 'Task not found')
        return redirect('dashboard')

    task_data = task_info.get('flask_data', task_info['data'])

    if request.method == 'POST':
        form = TaskForm(request.POST)
        if form.is_valid():
            # Update in Django database if the task is from Django
            if task_info['source'] in ['django', 'both']:
                task = get_object_or_404(Task, id=task_id, user=request.user)
                task.title = form.cleaned_data['title']
                task.due_date = form.cleaned_data['due_date']
                task.priority = form.cleaned_data['priority']
                task.category = form.cleaned_data['category']
                task.tags = form.cleaned_data.get('tags', '')
                task.save()

            # Sync to Flask if the task is from Flask or both
            task_data = {
                'id': task_id,
                'title': form.cleaned_data['title'],
                'due_date': form.cleaned_data['due_date'].strftime('%Y-%m-%d'),
                'priority': form.cleaned_data['priority'],
                'category': form.cleaned_data['category'],
                'tags': form.cleaned_data.get('tags', ''),
                'username': request.user.username
            }

            if sync_task_to_flask(task_data):
                messages.success(request, 'Task updated successfully!')
            else:
                messages.warning(request, 'Task updated locally but failed to sync with Flask.')

            return redirect('dashboard')
    else:
        form = TaskForm(initial={
            'title': task_data['title'],
            'due_date': task_data['due_date'],
            'priority': task_data['priority'],
            'category': task_data['category'],
            'tags': task_data.get('tags', ''),
        })

    return render(request, 'edit_task.html', {'form': form, 'task_id': task_id})

@login_required
def delete_task(request, task_id):
    # Delete from Django database if the task exists locally
    try:
        task = Task.objects.get(id=task_id, user=request.user)
        task.delete()
    except Task.DoesNotExist:
        pass

    # Delete from Flask
    response = api_client.delete_task(task_id)
    if response.get('message') == 'Task deleted successfully':
        messages.success(request, 'Task deleted successfully!')
    else:
        messages.warning(request, 'Task deleted locally but failed to delete from Flask.')
    return redirect('dashboard')

@login_required
def toggle_task(request, task_id):
    # Get task from both sources
    all_tasks = get_tasks_from_both_sources(request.user)
    task_info = all_tasks.get(task_id)

    if not task_info:
        messages.error(request, 'Task not found')
        return redirect('dashboard')

    # Toggle in Django database if the task exists locally
    try:
        task = Task.objects.get(id=task_id, user=request.user)
        task.status = 'completed' if task.status != 'completed' else 'pending'
        task.save()
    except Task.DoesNotExist:
        pass

    # Toggle in Flask
    response = api_client.toggle_task(task_id)
    if response.get('message') == 'Task status updated successfully':
        messages.success(request, 'Task status updated successfully!')
    else:
        messages.warning(request, 'Task status updated locally but failed to sync with Flask.')
    return redirect('dashboard')

@login_required
def calendar_view(request):
    return render(request, 'calendar.html')

@login_required
@require_GET
def calendar_events(request):
    # Fetch only Flask tasks
    flask_tasks = api_client.get_tasks({'username': request.user.username}) or []
    if isinstance(flask_tasks, dict) and 'tasks' in flask_tasks:
        flask_tasks = flask_tasks['tasks']
    events = []
    for task in flask_tasks:
        events.append({
            'id': task['id'],
            'title': task['title'],
            'start': task['due_date'],
            'priority': task['priority'],
            'status': task['status'],
            'category': task['category'],
            'tags': task.get('tags', ''),
            'url': f"/edit-task/{task['id']}/",
            'backgroundColor': {
                'high': '#fecaca',
                'medium': '#fef08a',
                'low': '#bbf7d0',
            }[task['priority']]
        })
    return JsonResponse(events, safe=False)

def feedback_view(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        message = request.POST.get('message', '').strip()

        if name and email and message:
            Feedback.objects.create(
                name=name,
                email=email,
                message=message
            )
            messages.success(request, 'Thank you for your feedback!')
            return redirect('dashboard')
        else:
            messages.error(request, 'Please fill in all fields before submitting.')

    return render(request, 'feedback.html')

def about(request):
    return render(request, 'about.html')

def demo(request):
    return render(request, 'demo.html')

@login_required
def task_detail(request, task_id):
    task = get_object_or_404(Task, pk=task_id, user=request.user)
    return render(request, 'task_detail.html', {'task': task})

@login_required
def admin_feedback_view(request):
    if not request.user.is_admin():
        return redirect('index')

    feedbacks = Feedback.objects.all()
    return render(request, 'admin/feedback.html', {'feedbacks': feedbacks})

def is_admin(user):
    return user.is_authenticated and user.user_type == 'admin'

@user_passes_test(is_admin, login_url='login')
def admin_dashboard(request):
    # Get counts for dashboard cards
    total_users = CustomUser.objects.count()
    total_tasks = Task.objects.count()
    
    # Get today's counts
    today = timezone.now().date()
    new_users_today = CustomUser.objects.filter(date_joined__date=today).count()
    new_tasks_today = Task.objects.filter(created_at__date=today).count()
    
    # Get active users in last 24 hours
    last_24_hours = timezone.now() - timedelta(hours=24)
    active_users = CustomUser.objects.filter(last_login__gte=last_24_hours).count()
    
    # Get unread feedback count
    new_feedback = Feedback.objects.filter(is_read=False).count()
    
    # Get recent users and tasks
    recent_users = CustomUser.objects.order_by('-date_joined')[:5]
    recent_tasks = Task.objects.order_by('-created_at')[:5]
    
    context = {
        'total_users': total_users,
        'total_tasks': total_tasks,
        'new_users_today': new_users_today,
        'new_tasks_today': new_tasks_today,
        'active_users': active_users,
        'new_feedback': new_feedback,
        'recent_users': recent_users,
        'recent_tasks': recent_tasks,
    }
    
    return render(request, 'admin/dashboard.html', context)

@user_passes_test(is_admin, login_url='login')
def admin_users(request):
    users = CustomUser.objects.all().order_by('-date_joined')
    return render(request, 'admin/users.html', {'users': users})

@user_passes_test(is_admin, login_url='login')
def admin_tasks(request):
    tasks = Task.objects.all().order_by('-created_at')
    
    # Apply filters if provided
    status_filter = request.GET.get('status')
    priority_filter = request.GET.get('priority')
    category_filter = request.GET.get('category')
    
    if status_filter and status_filter != 'all':
        tasks = tasks.filter(status=status_filter)
    
    if priority_filter and priority_filter != 'all':
        tasks = tasks.filter(priority=priority_filter)
    
    if category_filter and category_filter != 'all':
        tasks = tasks.filter(category=category_filter)
    
    context = {
        'tasks': tasks,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'category_filter': category_filter,
    }
    
    return render(request, 'admin/tasks.html', context)

@user_passes_test(is_admin, login_url='login')
def admin_feedback(request):
    feedbacks = Feedback.objects.all().order_by('-created_at')
    # Mark all feedback as read
    Feedback.objects.filter(is_read=False).update(is_read=True)
    return render(request, 'admin/feedback.html', {'feedbacks': feedbacks})

@user_passes_test(is_admin, login_url='login')
def admin_settings(request):
    if request.method == 'POST':
        # Handle settings update
        # Add your settings logic here
        messages.success(request, 'Settings updated successfully!')
        return redirect('admin_settings')
    return render(request, 'admin/settings.html')

@user_passes_test(is_admin, login_url='login')
def toggle_user_status(request, user_id):
    user = get_object_or_404(CustomUser, id=user_id)
    user.is_active = not user.is_active
    user.save()
    messages.success(request, f"User {user.username}'s status has been updated.")
    return redirect('admin_users')

@user_passes_test(is_admin, login_url='login')
def delete_user(request, user_id):
    user = get_object_or_404(CustomUser, id=user_id)
    username = user.username
    user.delete()
    messages.success(request, f"User {username} has been deleted.")
    return redirect('admin_users')

class TaskListAPIView(APIView):
    """
    DRF APIView that fetches tasks from the Flask backend and returns them as JSON.
    """
    def get(self, request):
        try:
            tasks = api_client.get_tasks()  # Use the APIClient method
            return Response(tasks, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)

