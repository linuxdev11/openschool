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


from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from database import SessionLocal
from models import User
from schemas import LoginRequest
from crud_ops import get_user_by_username, verify_password, create_user, get_password_hash
from typing import Optional
from fastapi import Form
import json
import os
import bleach

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(request: Request, db: Session = Depends(get_db)):
    user_id = request.cookies.get("user_id")
    user_role = request.cookies.get("user_role")
    
    if not user_id or not user_role:
        return None
    
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        return None
    
    return user


@router.post("/login")
async def login(request: Request, db: Session = Depends(get_db)):
    form_data = await request.form()
    username = bleach.clean(form_data.get("username", ""))
    password = form_data.get("password", "")
    
    try:
        user = None  # Initialize user variable
        
        # Check if this is admin login by checking config.json
        if os.path.exists("config.json"):
            with open("config.json", "r", encoding="utf-8") as f:
                config = json.load(f)
                admin_username = config.get("admin_username", "admin")
                admin_password = config.get("admin_password", "meow")
            
            # Check if login matches admin credentials from config
            if username == admin_username and password == admin_password:
                # Find or create admin user in database
                user = get_user_by_username(db, username)
                if not user:
                    # Create admin user if doesn't exist
                    user = create_user(db, username, password, "teacher")
                else:
                    # Update admin password if changed
                    user.hashed_password = get_password_hash(password)
                    db.commit()
            else:
                # Fallback to database check for non-admin users
                user = get_user_by_username(db, username)
                if not user or not verify_password(password, user.hashed_password):
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid credentials"
                    )
        else:
            # Fallback to database check if config.json doesn't exist
            user = get_user_by_username(db, username)
            if not user or not verify_password(password, user.hashed_password):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid credentials"
                )
        
        # Check if user was found/created
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        # Create response with cookies and redirect to dashboard
        response = RedirectResponse(url="/", status_code=302)
        response.set_cookie(key="user_id", value=str(user.id), httponly=True)
        response.set_cookie(key="user_role", value=user.role, httponly=True)
        return response
    except Exception as e:
        # Return error to be handled by middleware
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/login-cookie")
async def login_cookie(request: Request, db: Session = Depends(get_db)):
    form_data = await request.form()
    username = bleach.clean(form_data.get("username", ""))
    password = form_data.get("password", "")
    
    try:
        user = None  # Initialize user variable
        
        # Check if this is admin login by checking config.json
        if os.path.exists("config.json"):
            with open("config.json", "r", encoding="utf-8") as f:
                config = json.load(f)
                admin_username = config.get("admin_username", "admin")
                admin_password = config.get("admin_password", "meow")
            
            # Check if login matches admin credentials from config
            if username == admin_username and password == admin_password:
                # Find or create admin user in database
                user = get_user_by_username(db, username)
                if not user:
                    # Create admin user if doesn't exist
                    user = create_user(db, username, password, "teacher")
                else:
                    # Update admin password if changed
                    user.hashed_password = get_password_hash(password)
                    db.commit()
            else:
                # Fallback to database check for non-admin users
                user = get_user_by_username(db, username)
                if not user or not verify_password(password, user.hashed_password):
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid credentials"
                    )
        else:
            # Fallback to database check if config.json doesn't exist
            user = get_user_by_username(db, username)
            if not user or not verify_password(password, user.hashed_password):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid credentials"
                )
        
        # Check if user was found/created
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        response = RedirectResponse(url="/", status_code=302)
        response.set_cookie(key="user_id", value=str(user.id), httponly=True)
        response.set_cookie(key="user_role", value=user.role, httponly=True)
        return response
    except Exception as e:
        # Return error to be handled by middleware
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("user_id")
    response.delete_cookie("user_role")
    return response