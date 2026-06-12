from datetime import datetime

from flask_login import UserMixin

from app.extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum("admin", "teacher", "student"), nullable=False, index=True)
    is_active_user = db.Column(db.Boolean, default=True, nullable=False)
    last_login_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    student_profile = db.relationship("Student", back_populates="user", uselist=False, cascade="all, delete-orphan")
    teacher_profile = db.relationship("Teacher", back_populates="user", uselist=False, cascade="all, delete-orphan")
    logs = db.relationship("ActivityLog", back_populates="user", lazy=True)

    @property
    def is_active(self):
        return self.is_active_user
