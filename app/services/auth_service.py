from flask import session
from flask_login import login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models import Student, Teacher, User


def authenticate(email, password, role=None):
    user = User.query.filter_by(email=email, is_active_user=True).first()
    if not user:
        return None
    if role and user.role != role:
        return None
    if check_password_hash(user.password_hash, password):
        return user
    return None


def login_user_with_session(user, remember=False):
    session.clear()
    login_user(user, remember=remember)
    session["user_id"] = user.id
    session["role"] = user.role
    session["name"] = user.name
    if user.student_profile:
        session["student_id"] = user.student_profile.id
    if user.teacher_profile:
        session["teacher_id"] = user.teacher_profile.id


def logout_current_user():
    logout_user()
    session.clear()


def create_user(name, email, password, role, roll_number=None):
    user = User(
        name=name,
        email=email,
        password_hash=generate_password_hash(password),
        role=role,
    )
    db.session.add(user)
    db.session.flush()

    if role == "student":
        db.session.add(Student(user_id=user.id, roll_number=roll_number or f"STU{user.id:04d}"))
    elif role == "teacher":
        db.session.add(Teacher(user_id=user.id, employee_number=roll_number or f"TCH{user.id:04d}"))

    db.session.commit()
    return user
