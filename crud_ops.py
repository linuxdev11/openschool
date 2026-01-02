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

from sqlalchemy.orm import Session
from sqlalchemy import func
from models import User, Subject, Grade
from passlib.context import CryptContext
import hashlib

# Configure argon2 for password hashing
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto", argon2__rounds=10, argon2__memory_cost=1024, argon2__parallelism=2)


def get_password_hash(password):
    # Truncate password to 72 bytes if needed to be compatible with bcrypt
    if len(password.encode('utf-8')) > 72:
        # Truncate to 72 bytes and decode back to string
        password = password.encode('utf-8')[:72].decode('utf-8', errors='ignore')
    return pwd_context.hash(password)


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_user_by_username(db: Session, username: str):
    return db.query(User).filter(User.username == username).first()


def get_user(db: Session, user_id: int):
    return db.query(User).filter(User.id == user_id).first()


def create_user(db: Session, username: str, password: str, role: str):
    hashed_password = get_password_hash(password)
    db_user = User(username=username, hashed_password=hashed_password, role=role)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def get_subject_by_name(db: Session, name: str):
    return db.query(Subject).filter(Subject.name == name).first()


def create_subject(db: Session, name: str):
    db_subject = Subject(name=name)
    db.add(db_subject)
    db.commit()
    db.refresh(db_subject)
    return db_subject


def get_subject(db: Session, subject_id: int):
    return db.query(Subject).filter(Subject.id == subject_id).first()


def get_subjects(db: Session):
    return db.query(Subject).all()


def create_grade(db: Session, value: float, student_id: int, subject_id: int):
    # Validate that the grade is between 1 and 5 for the Russian 5-point system
    if value < 1 or value > 5:
        raise ValueError("Оценка должна быть от 1 до 5")
    
    db_grade = Grade(value=value, student_id=student_id, subject_id=subject_id)
    db.add(db_grade)
    db.commit()
    db.refresh(db_grade)
    return db_grade


def get_grades_for_student(db: Session, student_id: int):
    return db.query(Grade).filter(Grade.student_id == student_id).all()


def get_grades_for_subject(db: Session, subject_id: int):
    return db.query(Grade).filter(Grade.subject_id == subject_id).all()


def get_grades_for_student_and_subject(db: Session, student_id: int, subject_id: int):
    return db.query(Grade).filter(Grade.student_id == student_id, Grade.subject_id == subject_id).all()


def get_all_grades(db: Session):
    return db.query(Grade).order_by(Grade.date.desc()).all()


def get_average_grade_for_student(db: Session, student_id: int):
    result = db.query(func.avg(Grade.value)).filter(Grade.student_id == student_id).scalar()
    return result if result is not None else 0.0


def get_average_grade_for_student_by_subject(db: Session, student_id: int, subject_id: int):
    result = db.query(func.avg(Grade.value)).filter(
        Grade.student_id == student_id,
        Grade.subject_id == subject_id
    ).scalar()
    return result if result is not None else 0.0