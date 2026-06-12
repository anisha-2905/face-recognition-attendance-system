from datetime import datetime

from app.extensions import db


class Teacher(db.Model):
    __tablename__ = "teachers"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    employee_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id", ondelete="SET NULL"))
    department = db.Column(db.String(100))
    designation = db.Column(db.String(100))
    phone = db.Column(db.String(30))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = db.relationship("User", back_populates="teacher_profile")
    department_ref = db.relationship("Department", back_populates="teachers")
    subjects = db.relationship("Subject", back_populates="teacher", lazy=True)
    attendance_marked = db.relationship("Attendance", back_populates="marked_by_teacher", lazy=True)
