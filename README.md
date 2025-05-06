# Task Management Application

A full-stack productivity platform for managing tasks, users, and shop products. The backend is built with Flask (REST API), and the frontend is a Django web application. The project includes a shop module, admin dashboard, and a responsive UI.

---

## Table of Contents
- [Features](#features)
- [Architecture Overview](#architecture-overview)
- [Project Structure](#project-structure)
- [Backend (Flask)](#backend-flask)
  - [Tech Stack](#tech-stack)
  - [Setup & Run](#setup--run)
  - [Main Files & Folders](#main-files--folders)
  - [API Endpoints](#api-endpoints)
- [Frontend (Django)](#frontend-django)
  - [Tech Stack](#tech-stack-1)
  - [Setup & Run](#setup--run-1)
  - [Main Files & Folders](#main-files--folders-1)
  - [Key URLs](#key-urls)
- [Frontend & Backend Communication](#frontend--backend-communication)
- [Usage](#usage)
- [Customization](#customization)
- [Troubleshooting & FAQ](#troubleshooting--faq)
- [Contributing](#contributing)
- [License](#license)

---

## Features
- User registration, login, and profile management
- Task CRUD (create, read, update, delete) with filtering, search, and calendar view
- Admin dashboard for managing users, tasks, feedback, and shop items
- Feedback submission and management
- Shop module: product catalog, cart, checkout, order management
- Responsive UI with custom templates and static assets
- REST API for user and task data (Flask backend)
- Integration between Django frontend and Flask backend

## Architecture Overview
- **Backend:** Flask REST API (task/user management, authentication)
- **Frontend:** Django web app (UI, shop, admin, API client)
- **Communication:** Django frontend calls Flask API for user/task operations

## Project Structure
```
backend/
  myenv/                # Python virtual environment for backend
  TASK-MANAGEMENT/      # Flask app: API, models, templates, static
    app.py
    api.py
    models.py
    ...
frontend/
  myenv/                # Python virtual environment for frontend
  taskmasternew/
    manage.py
    requirements.txt
    TASKMASTER/         # Django project settings
    TASKMASTERAPP/      # Main app: users, tasks, feedback
    shop/               # E-commerce module
    media/              # Uploaded files
    templates/          # HTML templates
    static/             # CSS, JS, images
README.md
```

---

## Backend (Flask)
### Tech Stack
- Python 3
- Flask
- Flask-Login, Flask-Bcrypt, SQLAlchemy
- SQLite (default)

### Setup & Run
1. Open a terminal and navigate to the backend directory:
   ```bash
   cd backend/TASK-MANAGEMENT
   ```
2. Activate the virtual environment:
   ```bash
   ..\myenv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the Flask app:
   ```bash
   python app.py
   ```
   The API will be available at `http://127.0.0.1:5000/` (default).

### Main Files & Folders
- `app.py` – Main Flask app
- `api.py` – REST API endpoints
- `models.py` – Database models
- `forms.py` – WTForms for user/task input
- `templates/` – Jinja2 HTML templates
- `static/` – CSS, JS, images, uploads

### API Endpoints (examples)
- `POST /api/auth/register` – Register user
- `POST /api/auth/login` – Login
- `POST /api/auth/logout` – Logout
- `GET /api/tasks` – List tasks
- `POST /api/tasks` – Create task
- `PUT /api/tasks/<id>` – Update task
- `DELETE /api/tasks/<id>` – Delete task

---

## Frontend (Django)
### Tech Stack
- Python 3
- Django
- Django REST Framework (for API consumption)
- SQLite (default)

### Setup & Run
1. Open a terminal and navigate to the frontend directory:
   ```bash
   cd frontend/taskmasternew
   ```
2. Activate the virtual environment:
   ```bash
   ..\myenv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run migrations:
   ```bash
   python manage.py migrate
   ```
5. Create a superuser (for admin access):
   ```bash
   python manage.py createsuperuser
   ```
6. Start the development server:
   ```bash
   python manage.py runserver
   ```
   The app will be available at `http://127.0.0.1:8000/` (default).

### Main Files & Folders
- `TASKMASTERAPP/` – Main Django app (users, tasks, feedback, API client)
- `shop/` – E-commerce module (products, orders)
- `media/` – Uploaded files (profile pics, product images)
- `templates/` – HTML templates
- `static/` – CSS, JS, images

### Key URLs
- `/` – Home
- `/register/` – User registration
- `/login/` – User login
- `/dashboard/` – User dashboard
- `/admin/dashboard/` – Admin dashboard
- `/shop/` – Shop home

---

## Frontend & Backend Communication
- The Django frontend uses `TASKMASTERAPP/api_client.py` to make HTTP requests to the Flask backend for user and task operations.
- Ensure both servers are running for full functionality.

---

## Usage
1. Start both backend and frontend servers as described above.
2. Register a new user or log in as admin.
3. Use the dashboard to manage your tasks.
4. Admins: visit `/admin/dashboard/` for advanced management.
5. Shop: visit `/shop/` to browse and purchase products.

---

## Customization
- **Templates:** Edit HTML in `frontend/taskmasternew/TASKMASTERAPP/templates/` and `shop/templates/`
- **Static assets:** Update CSS/JS in `static/`
- **API URLs:** Update Flask API URLs in `api_client.py` if backend changes
- **Models/Forms:** Extend as needed for new features

---

## Troubleshooting & FAQ
- **Both servers must be running:** Start Flask backend and Django frontend
- **API errors:** Check Flask server logs and API URLs
- **Static/media issues:** Check Django `settings.py` for `STATIC_URL`, `MEDIA_URL`, and `MEDIA_ROOT`
- **Database issues:** Run migrations and check for errors
- **Admin access:** Use `createsuperuser` to make an admin account

---

## Contributing

We welcome contributions to this project! To help us maintain a high-quality codebase, please follow these guidelines:

### How to Contribute
1. **Fork the repository** and create your branch from `main`.
2. **Clone your fork** to your local machine.
3. **Create a new branch** for your feature or bugfix:
   ```bash
   git checkout -b feature/your-feature-name
   ```
4. **Make your changes** with clear, descriptive commit messages.
5. **Test your changes** locally (run both backend and frontend, and ensure all features work as expected).
6. **Push to your fork** and submit a pull request (PR) to the `main` branch.

### Code Style
- Use clear, descriptive variable and function names.
- Follow PEP8 for Python code.
- Keep code modular and add comments where necessary.
- For Django: follow Django best practices for apps, models, and views.
- For Flask: keep API endpoints RESTful and well-documented.

### Issues & Feature Requests
- Use [GitHub Issues](https://github.com/your-repo/issues) to report bugs or request features.
- Please provide as much detail as possible, including steps to reproduce bugs.

### Pull Request Checklist
- [ ] Code compiles and runs without errors
- [ ] All tests pass (if applicable)
- [ ] Code is well-documented
- [ ] No sensitive data or credentials are included
- [ ] The PR description clearly explains the changes

Thank you for helping improve this project!

---

## License
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

---

_For more details, see the code and comments in each app._
