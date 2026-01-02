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


from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import SessionLocal
from router_auth import get_current_user
from crud_ops import get_grades_for_student, get_subjects, get_all_grades, get_average_grade_for_student, create_grade, get_grades_for_student_and_subject, get_average_grade_for_student_by_subject, get_user_by_username, create_user, get_password_hash
from models import User, Grade
from fastapi import Form
import json
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from passlib.context import CryptContext
from models import User, Grade, Base
import bleach

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def require_login(request: Request):
    user_id = request.cookies.get("user_id")
    user_role = request.cookies.get("user_role")
    
    if not user_id or not user_role:
        return RedirectResponse(url="/login", status_code=302)
    
    return None


def is_admin_user(current_user: User) -> bool:
    """Check if current user is the admin user defined in config.json"""
    if not os.path.exists("config.json"):
        return False
    
    with open("config.json", "r", encoding="utf-8") as f:
        config = json.load(f)
        admin_username = config.get("admin_username", "admin")
    
    # Admin is the user whose username matches the admin_username in config
    return current_user.username == admin_username


# Removed the home route since it's now handled in main.py
# @router.get("/")
# def home(request: Request, db: Session = Depends(get_db)):
#     redirect_response = require_login(request)
#     if redirect_response:
#         return redirect_response
#     
#     current_user = get_current_user(request, db)
#     if not current_user:
#         return RedirectResponse(url="/login", status_code=302)
#     
#     error = None
#     try:
#         # Add Russian role translation
#         if current_user.role == "teacher":
#             current_user.role_ru = "учитель"
#         elif current_user.role == "student":
#             current_user.role_ru = "ученик"
#         else:
#             current_user.role_ru = current_user.role
#     
#         if current_user.role == "teacher":
#             # Teacher view - show all grades
#             all_grades = get_all_grades(db)
#             students = db.query(User).filter(User.role == "student").all()
#             subjects = get_subjects(db)
#             
#             return templates.TemplateResponse("dashboard.html", {
#                 "request": request,
#                 "current_user": current_user,
#                 "grades": all_grades,
#                 "students": students,
#                 "subjects": subjects,
#                 "is_admin": is_admin_user(current_user)
#             })
#         elif current_user.role == "student":
#             # Student view - show only their grades
#             student_grades = get_grades_for_student(db, current_user.id)
#             avg_grade = get_average_grade_for_student(db, current_user.id)
#             subjects = get_subjects(db)
#             
#             return templates.TemplateResponse("student.html", {
#                 "request": request,
#                 "current_user": current_user,
#                 "grades": student_grades,
#                 "average_grade": avg_grade,
#                 "subjects": subjects
#             })
#         else:
#             return RedirectResponse(url="/login", status_code=302)
#     except Exception as e:
#         error = str(e)
#         return templates.TemplateResponse("alert.html", {
#             "request": request,
#             "error": error
#         })


@router.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/setup")
async def setup(request: Request, db: Session = Depends(get_db)):
    form_data = await request.form()
    language = bleach.clean(form_data.get("language", ""))
    grading_system = bleach.clean(form_data.get("grading_system", ""))
    admin_username = bleach.clean(form_data.get("admin_username", ""))
    admin_password = form_data.get("admin_password", "")
    
    try:
        # Create config file
        config_data = {
            "language": language,
            "grading_system": grading_system,
            "admin_username": admin_username,
            "admin_password": admin_password
        }
        
        with open("config.json", "w", encoding="utf-8") as f:
            json.dump(config_data, f, ensure_ascii=False, indent=4)
        
        # Create database if it doesn't exist
        if not os.path.exists("users.db"):
            engine = create_engine('sqlite:///users.db')
            Base.metadata.create_all(engine)
            
            # Create session
            SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
            db_session = SessionLocal()
            
            try:
                # Check if admin user already exists
                admin_user = db_session.query(User).filter(User.username == admin_username).first()
                if not admin_user:
                    # Create admin user
                    hashed_password = get_password_hash(admin_password)
                    db_user = User(username=admin_username, hashed_password=hashed_password, role="teacher")
                    db_session.add(db_user)
                    db_session.commit()
                    db_session.refresh(db_user)
                    print("Admin user created successfully.")
                else:
                    print("Admin user already exists.")
            except Exception as e:
                print(f"Error setting up database: {e}")
            finally:
                db_session.close()
        
        # Redirect to login page after setup
        return RedirectResponse(url="/login", status_code=302)
    except Exception as e:
        error = str(e)
        return templates.TemplateResponse("alert.html", {
            "request": request,
            "error": error
        })


@router.post("/grade")
async def add_grade(
    request: Request,
    student_id: int = Form(...),
    subject_id: int = Form(...),
    value: float = Form(...),
    db: Session = Depends(get_db)
):
    redirect_response = require_login(request)
    if redirect_response:
        return redirect_response
    
    current_user = get_current_user(request, db)
    if not current_user or current_user.role != "teacher":
        raise HTTPException(status_code=403, detail="Только учителя могут добавлять оценки")
    
    # Validate grade is between 1 and 5
    if value < 1 or value > 5:
        raise HTTPException(status_code=400, detail="Оценка должна быть от 1 до 5")
    
    try:
        create_grade(db, value, student_id, subject_id)
        return RedirectResponse(url="/", status_code=302)
    except Exception as e:
        error = str(e)
        return templates.TemplateResponse("alert.html", {
            "request": request,
            "error": error
        })

# User management routes
@router.get("/users")
def get_users(request: Request, db: Session = Depends(get_db)):
    redirect_response = require_login(request)
    if redirect_response:
        return redirect_response
    
    current_user = get_current_user(request, db)
    if not current_user or not is_admin_user(current_user):
        return RedirectResponse(url="/login", status_code=302)
    
    # Only show students and other teachers (not the current user in the list for deletion/modification)
    users = db.query(User).filter(User.id != current_user.id).all()
    
    # Add Russian role translation
    for user in users:
        if user.role == "teacher":
            user.role_ru = "учитель"
        elif user.role == "student":
            user.role_ru = "ученик"
        else:
            user.role_ru = user.role
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "current_user": current_user,
        "users": users,
        "show_users": True,
        "is_admin": True
    })

@router.post("/users/add")
async def add_user(request: Request, db: Session = Depends(get_db)):
    redirect_response = require_login(request)
    if redirect_response:
        return redirect_response
    
    current_user = get_current_user(request, db)
    if not current_user or not is_admin_user(current_user):
        return RedirectResponse(url="/login", status_code=302)
    
    form_data = await request.form()
    username = bleach.clean(form_data.get("username", ""))
    password = form_data.get("password", "")
    role = bleach.clean(form_data.get("role", "student"))  # Default to student
    
    # Validate role
    if role not in ["student", "teacher"]:
        role = "student"
    
    # Check if user already exists
    existing_user = get_user_by_username(db, username)
    if existing_user:
        return templates.TemplateResponse("alert.html", {
            "request": request,
            "error": "Пользователь с таким именем уже существует"
        })
    
    try:
        # Create new user
        create_user(db, username, password, role)
        return RedirectResponse(url="/", status_code=302)
    except Exception as e:
        error = str(e)
        return templates.TemplateResponse("alert.html", {
            "request": request,
            "error": error
        })
