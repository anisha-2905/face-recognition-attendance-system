from datetime import datetime

from app.extensions import db


class Enrollment(db.Model):
    __tablename__ = "student_subjects"
    __table_args__ = (db.UniqueConstraint("student_id", "subject_id", name="uq_student_subject"),)

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    enrolled_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    student = db.relationship("Student", back_populates="enrollments")
    subject = db.relationship("Subject", back_populates="enrollments")

    @property
    def course(self):
        return self.subject
