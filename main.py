# OpenSchool - Электронный дневник
# Copyright (C) 2026 (linuxdev)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.


from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from database import engine
from models import Base
from router_auth import router as auth_router
from router_views import router as views_router
from crud_ops import create_user, get_user_by_username, create_subject, get_subject_by_name, get_user
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import traceback
from starlette.exceptions import HTTPException
from fastapi.exceptions import RequestValidationError
import os
import json
import bleach
from sqlalchemy.orm import Session
from database import SessionLocal as DatabaseSessionLocal

app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Create templates object for rendering (moved before it's used)
templates = Jinja2Templates(directory="templates")

# Include auth router (always needed)
app.include_router(auth_router, prefix="")

# Dynamic route for home page that handles both setup and authentication
@app.get("/")
async def home(request: Request):
    # Check if config.json and users.db exist
    config_exists = os.path.exists("config.json")
    db_exists = os.path.exists("users.db")
    
    if not config_exists or not db_exists:
        # If either file is missing, show setup page
        return templates.TemplateResponse("first_start.html", {"request": request})
    else:
        # Files exist, check if user is authenticated
        user_id = request.cookies.get("user_id")
        user_role = request.cookies.get("user_role")
        
        if not user_id or not user_role:
            # User not authenticated, redirect to login
            return RedirectResponse(url="/login")
        
        # User is authenticated, validate the user exists in database
        db = DatabaseSessionLocal()
        try:
            from models import User
            try:
                user = db.query(User).filter(User.id == int(user_id)).first()
                if not user:
                    # User doesn't exist in database, redirect to login
                    return RedirectResponse(url="/login")
            except ValueError:
                # Invalid user_id in cookie, redirect to login
                return RedirectResponse(url="/login")
        finally:
            db.close()
        
        # User is authenticated and valid, show dashboard
        from router_auth import get_current_user
        from sqlalchemy.orm import sessionmaker
        from database import SessionLocal
        
        db = SessionLocal()
        try:
            current_user = get_current_user(request, db)
            if not current_user:
                return RedirectResponse(url="/login")
                
            # Add Russian role translation
            if current_user.role == "teacher":
                current_user.role_ru = "учитель"
            elif current_user.role == "student":
                current_user.role_ru = "ученик"
            else:
                current_user.role_ru = current_user.role

            if current_user.role == "teacher":
                # Teacher view - show all grades
                from crud_ops import get_all_grades, get_subjects
                all_grades = get_all_grades(db)
                students = db.query(User).filter(User.role == "student").all()
                subjects = get_subjects(db)
                
                # Check if user is admin
                is_admin = False
                if os.path.exists("config.json"):
                    with open("config.json", "r", encoding="utf-8") as f:
                        config = json.load(f)
                        admin_username = config.get("admin_username", "admin")
                    is_admin = current_user.username == admin_username

                return templates.TemplateResponse("dashboard.html", {
                    "request": request,
                    "current_user": current_user,
                    "grades": all_grades,
                    "students": students,
                    "subjects": subjects,
                    "is_admin": is_admin
                })
            elif current_user.role == "student":
                # Student view - show only their grades
                from crud_ops import get_grades_for_student, get_average_grade_for_student, get_subjects
                student_grades = get_grades_for_student(db, current_user.id)
                avg_grade = get_average_grade_for_student(db, current_user.id)
                subjects = get_subjects(db)
                
                return templates.TemplateResponse("student.html", {
                    "request": request,
                    "current_user": current_user,
                    "grades": student_grades,
                    "average_grade": avg_grade,
                    "subjects": subjects
                })
            else:
                return RedirectResponse(url="/login")
        except Exception as e:
            error = str(e)
            return templates.TemplateResponse("alert.html", {
                "request": request,
                "error": error
            })
        finally:
            db.close()

# Include views router - this will only handle routes other than "/"
# The "/" route is handled by the main app
app.include_router(views_router, prefix="")

# Create database tables
Base.metadata.create_all(bind=engine)

# Initialize default users and subjects
def init_db():
    db = DatabaseSessionLocal()
    try:
        # Get admin credentials from config.json
        if os.path.exists("config.json"):
            with open("config.json", "r", encoding="utf-8") as f:
                config = json.load(f)
                admin_username = bleach.clean(config.get("admin_username", "admin"))
                admin_password = config.get("admin_password", "admin")
        else:
            # Default values if config doesn't exist
            admin_username = "admin"
            admin_password = "admin"
        
        # Create default admin user if doesn't exist
        admin_user = get_user_by_username(db, admin_username)
        if not admin_user:
            create_user(db, admin_username, admin_password, "teacher")
        
        # Create default student user if doesn't exist
        student_user = get_user_by_username(db, "user")
        if not student_user:
            create_user(db, "user", "user", "student")
        
        # Create default subjects if they don't exist
        subjects = ["Math", "Science", "English", "History"]
        for subject_name in subjects:
            subject = get_subject_by_name(db, subject_name)
            if not subject:
                create_subject(db, subject_name)
    finally:
        db.close()

# Check if config.json and users.db exist and initialize db if they exist
config_exists = os.path.exists("config.json")
db_exists = os.path.exists("users.db")

if config_exists and db_exists:
    # Initialize the database when the app starts (only if files exist)
    init_db()


@app.middleware("http")
async def error_handler(request: Request, call_next):
    try:
        response = await call_next(request)
        return response
    except Exception as exc:
        # Create JavaScript that will show the alert as a modal on the current page
        js_alert = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Error - OpenSchool</title>
            <link rel="stylesheet" type="text/css" href="/static/style.css">
        </head>
        <body>
            <div class="modal-overlay"></div>
            <div class="alert-modal">
                <div class="alert-header">
                    <span>Внимание!</span>
                    <button onclick="closeAlert()" style="background: none; border: none; color: white; cursor: pointer;">×</button>
                </div>
                <div class="alert-body">
                    <p>{bleach.clean(str(exc))}</p>
                </div>
                <div class="alert-footer">
                    <button onclick="closeAlert()" class="btn">ОК</button>
                </div>
            </div>
            <script>
                function closeAlert() {{
                    // Remove the modal and redirect to home
                    window.location.href = '/';
                }}
            </script>
        </body>
        </html>
        """
        
        return HTMLResponse(content=js_alert, status_code=500)

# Handle HTTP exceptions (like 404)
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    # Create JavaScript that will show the alert as a modal on the current page
    js_alert = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Error - OpenSchool</title>
        <link rel="stylesheet" type="text/css" href="/static/style.css">
    </head>
    <body>
        <div class="modal-overlay"></div>
        <div class="alert-modal">
            <div class="alert-header">
                <span>Внимание!</span>
                <button onclick="closeAlert()" style="background: none; border: none; color: white; cursor: pointer;">×</button>
            </div>
            <div class="alert-body">
                <p>HTTP Error {exc.status_code}: {bleach.clean(str(exc.detail))}</p>
            </div>
            <div class="alert-footer">
                <button onclick="closeAlert()" class="btn">ОК</button>
            </div>
        </div>
        <script>
            function closeAlert() {{
                // Remove the modal and redirect to home
                window.location.href = '/';
            }}
        </script>
    </body>
    </html>
    """
    
    return HTMLResponse(content=js_alert, status_code=exc.status_code)

# Handle request validation errors
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Create JavaScript that will show the alert as a modal on the current page
    js_alert = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Error - OpenSchool</title>
        <link rel="stylesheet" type="text/css" href="/static/style.css">
    </head>
    <body>
        <div class="modal-overlay"></div>
        <div class="alert-modal">
            <div class="alert-header">
                <span>Внимание!</span>
                <button onclick="closeAlert()" style="background: none; border: none; color: white; cursor: pointer;">×</button>
            </div>
            <div class="alert-body">
                <p>Validation Error: {bleach.clean(str(exc))}</p>
            </div>
            <div class="alert-footer">
                <button onclick="closeAlert()" class="btn">ОК</button>
            </div>
        </div>
        <script>
            function closeAlert() {{
                // Remove the modal and redirect to home
                window.location.href = '/';
            }}
        </script>
    </body>
    </html>
    """
    
    return HTMLResponse(content=js_alert, status_code=400)

@app.exception_handler(404)
async def custom_http_exception_handler(request: Request, exc):
    # Create JavaScript that will show the alert as a modal on the current page
    js_alert = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Error - OpenSchool</title>
        <link rel="stylesheet" type="text/css" href="/static/style.css">
    </head>
    <body>
        <div class="modal-overlay"></div>
        <div class="alert-modal">
            <div class="alert-header">
                <span>Внимание!</span>
                <button onclick="closeAlert()" style="background: none; border: none; color: white; cursor: pointer;">×</button>
            </div>
            <div class="alert-body">
                <p>HTTP Error 404: Page not found</p>
            </div>
            <div class="alert-footer">
                <button onclick="closeAlert()" class="btn">ОК</button>
            </div>
        </div>
        <script>
            function closeAlert() {{
                // Remove the modal and redirect to home
                window.location.href = '/';
            }}
        </script>
    </body>
    </html>
    """
    
    return HTMLResponse(content=js_alert, status_code=404)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8002)  # Changed port to 8002