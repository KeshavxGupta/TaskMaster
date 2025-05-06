from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, DateField, SelectField, HiddenField, TextAreaField, FileField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional

class TaskForm(FlaskForm):
    id = HiddenField('Task ID')
    title = StringField('Task Title', validators=[DataRequired()])
    due_date = DateField('Due Date', validators=[DataRequired()])
    priority = SelectField('Priority', 
                         choices=[('low', 'Low'), 
                                ('medium', 'Medium'), 
                                ('high', 'High')],
                         validators=[DataRequired()])
    category = SelectField('Category',
                         choices=[        ('work', 'Work'),
        ('personal', 'Personal'),
        ('shopping', 'Shopping'),
        ('health', 'Health'),
        ('other', 'Other'),
],
                         validators=[DataRequired()])
    tags = StringField('Tags')

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=2, max=20)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    phone_number = StringField('Phone Number', validators=[DataRequired(), Length(min=10, max=15)])
    date_of_birth = DateField('Date of Birth', validators=[DataRequired()], format='%Y-%m-%d')
    bio = TextAreaField('Bio', validators=[Optional(), Length(max=500)])
    profile_picture = FileField('Profile Picture', validators=[Optional()])

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    user_type = SelectField('User Type', 
                          choices=[('user', 'Regular User'), 
                                 ('admin', 'Administrator')],
                          validators=[DataRequired()])