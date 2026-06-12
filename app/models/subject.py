from datetime import datetime

from app.extensions import db


class Subject(db.Model):
    __tablename__ = "subjects"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(30), unique=True, nullable=False, index=True)
    name = db.Column(db.String(150), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id", ondelete="SET NULL"))
    department = db.Column(db.String(100))
    semester = db.Column(db.String(30))
    teacher_id = db.Column(db.Integer, db.ForeignKey("teachers.id", ondelete="SET NULL"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    teacher = db.relationship("Teacher", back_populates="subjects")
    department_ref = db.relationship("Department", back_populates="subjects")
    enrollments = db.relationship("Enrollment", back_populates="subject", cascade="all, delete-orphan")
    schedules = db.relationship("Schedule", back_populates="subject", cascade="all, delete-orphan")
    attendance_records = db.relationship("Attendance", back_populates="subject", cascade="all, delete-orphan")
