# admin.py
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from models import User, Task, Feedback
from forms import TaskForm, RegistrationForm 
from extensions import db

admin = Blueprint('admin', __name__)

@admin.route('/dashboard')
@login_required
def admindashboard():
    if current_user.user_type != 'admin':
        flash('Unauthorized access!', 'error')
        return redirect(url_for('index'))
    total_users = User.query.count()
    total_tasks = Task.query.count()
    completed_tasks = Task.query.filter_by(status='completed').count()
    pending_tasks = Task.query.filter_by(status='pending').count()
    return render_template('admindashboard.html', 
                           user=current_user,
                           total_users=total_users, 
                           total_tasks=total_tasks, 
                           completed_tasks=completed_tasks, 
                           pending_tasks=pending_tasks)

@admin.route('/users')
@login_required
def manage_users():
    if current_user.user_type != 'admin':
        flash('Unauthorized access!', 'error')
        return redirect(url_for('admin.admindashboard'))
    users = User.query.all()
    return render_template('manage_users.html', users=users)

@admin.route('/tasks')
@login_required
def manage_tasks():
    if current_user.user_type != 'admin':
        flash('Unauthorized access!', 'error')
        return redirect(url_for('admin.admindashboard'))
    
    tasks = db.session.query(Task, User).join(User).all()

    return render_template('manage_tasks.html', tasks=tasks)

@admin.route('/feedback')
@login_required
def feedback():
    if current_user.user_type != 'admin':
        flash('Unauthorized access!', 'error')
        return redirect(url_for('admin.admindashboard'))
    feedbacks = Feedback.query.all()
    return render_template('manage_feedback.html', feedbacks=feedbacks)

@admin.route('/user/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    if current_user.user_type != 'admin':
        flash('Unauthorized access!', 'error')
        return redirect(url_for('admin.admindashboard'))
    user = User.query.get_or_404(user_id)
    form = RegistrationForm()
    if form.validate_on_submit():
        user.username = form.username.data
        user.email = form.email.data
        if form.password.data:
            from flask_bcrypt import Bcrypt
            bcrypt = Bcrypt()
            user.password_hash = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        db.session.commit()
        flash('User has been updated!', 'success')
        return redirect(url_for('admin.manage_users'))
    elif request.method == 'GET':
        form.username.data = user.username
        form.email.data = user.email
    return render_template('edit_user.html', title='Edit User', form=form, user=user)

@admin.route('/user/delete/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if current_user.user_type != 'admin':
        flash('Unauthorized access!', 'error')
        return redirect(url_for('admin.admindashboard'))
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash('User has been deleted!', 'success')
    return redirect(url_for('admin.manage_users'))

@admin.route('/task/edit/<int:task_id>', methods=['GET', 'POST'])
@login_required
def edit_task(task_id):
    if current_user.user_type != 'admin':
        flash('Unauthorized access!', 'error')
        return redirect(url_for('admin.admindashboard'))
    task = Task.query.get_or_404(task_id)
    form = TaskForm()
    if form.validate_on_submit():
        task.title = form.title.data
        task.due_date = form.due_date.data
        task.priority = form.priority.data
        task.category = form.category.data
        task.tags = [tag.strip() for tag in form.tags.data.split(',') if tag.strip()]
        task.status = form.status.data
        db.session.commit()
        flash('Task has been updated!', 'success')
        return redirect(url_for('admin.manage_tasks'))
    elif request.method == 'GET':
        form.title.data = task.title
        form.due_date.data = task.due_date
        form.priority.data = task.priority
        form.category.data = task.category
        form.tags.data = ', '.join(task.tags) if task.tags else ''
        form.status.data = task.status
    return render_template('edit_task.html', title='Edit Task', form=form, task=task)

@admin.route('/task/delete/<int:task_id>', methods=['POST'])
@login_required
def delete_task(task_id):
    if current_user.user_type != 'admin':
        flash('Unauthorized access!', 'error')
        return redirect(url_for('admin.admindashboard'))
    task = Task.query.get_or_404(task_id)
    db.session.delete(task)
    db.session.commit()
    flash('Task has been deleted!', 'success')
    return redirect(url_for('admin.manage_tasks'))

@admin.route('/feedback/delete/<int:feedback_id>', methods=['POST'])
@login_required
def delete_feedback(feedback_id):
    if current_user.user_type != 'admin':
        flash('Unauthorized access!', 'error')
        return redirect(url_for('admin.admindashboard'))
    feedback_item = Feedback.query.get_or_404(feedback_id)
    db.session.delete(feedback_item)
    db.session.commit()
    flash('Feedback has been deleted!', 'success')
    return redirect(url_for('admin.feedback'))
