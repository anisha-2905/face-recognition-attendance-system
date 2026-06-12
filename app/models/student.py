from datetime import datetime

from app.extensions import db


class Student(db.Model):
    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    roll_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    admission_number = db.Column(db.String(50), unique=True)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id", ondelete="SET NULL"))
    department = db.Column(db.String(100))
    semester = db.Column(db.String(30))
    section = db.Column(db.String(30))
    phone = db.Column(db.String(30))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = db.relationship("User", back_populates="student_profile")
    department_ref = db.relationship("Department", back_populates="students")
    enrollments = db.relationship("Enrollment", back_populates="student", cascade="all, delete-orphan")
    attendance_records = db.relationship("Attendance", back_populates="student", lazy=True)
    face_profile = db.relationship("FaceProfile", back_populates="student", uselist=False, cascade="all, delete-orphan")
