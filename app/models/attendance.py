from datetime import datetime

from app.extensions import db


class Attendance(db.Model):
    __tablename__ = "attendance"
    __table_args__ = (
        db.UniqueConstraint("student_id", "subject_id", "attendance_date", name="uq_daily_attendance"),
    )

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=False)
    marked_by_teacher_id = db.Column(db.Integer, db.ForeignKey("teachers.id"))
    attendance_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.Enum("present", "absent", "late"), default="present", nullable=False)
    captured_image = db.Column(db.String(255))
    confidence = db.Column(db.Float)
    method = db.Column(db.Enum("face", "manual", "face_recognition", "system"), default="face_recognition", nullable=False)
    attendance_source = db.Column(db.String(50), default="manual", nullable=False)
    remarks = db.Column(db.String(255))
    marked_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    student = db.relationship("Student", back_populates="attendance_records")
    subject = db.relationship("Subject", back_populates="attendance_records")
    marked_by_teacher = db.relationship("Teacher", back_populates="attendance_marked")

    @property
    def course(self):
        return self.subject

    @property
    def course_id(self):
        return self.subject_id
