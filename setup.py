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


import os
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, User
from passlib.context import CryptContext

# Configure argon2 for password hashing
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto", argon2__rounds=10, argon2__memory_cost=1024, argon2__parallelism=2)

def get_password_hash(password):
    # Truncate password to 72 bytes if needed to be compatible with bcrypt
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > 72:
        # Truncate to 72 bytes and decode back to string
        password = password_bytes[:72].decode('utf-8', errors='ignore')
    return pwd_context.hash(password)

def setup_database():
    """Create database and initialize with admin user"""
    # Create SQLite database
    engine = create_engine('sqlite:///users.db')
    Base.metadata.create_all(engine)
    
    # Create session
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        # Check if admin user already exists
        admin_user = db.query(User).filter(User.username == "admin").first()
        if not admin_user:
            # Create admin user
            hashed_password = get_password_hash("admin")
            db_user = User(username="admin", hashed_password=hashed_password, role="teacher")
            db.add(db_user)
            db.commit()
            db.refresh(db_user)
            print("Admin user created successfully.")
        else:
            print("Admin user already exists.")
    except Exception as e:
        print(f"Error setting up database: {e}")
    finally:
        db.close()

def create_config_file():
    """Create config.json file with default settings"""
    config_data = {
        "language": "ru",
        "grading_system": "5-point",
        "admin_username": "admin",
        "admin_password": "admin"
    }
    
    with open("config.json", "w", encoding="utf-8") as f:
        json.dump(config_data, f, ensure_ascii=False, indent=4)
    
    print("Config file created successfully.")

def main():
    """Main setup function"""
    print("Starting setup process...")
    
    # Create config file if it doesn't exist
    if not os.path.exists("config.json"):
        create_config_file()
    
    # Create database if it doesn't exist
    if not os.path.exists("users.db"):
        setup_database()
    
    print("Setup completed successfully!")

if __name__ == "__main__":
    main()