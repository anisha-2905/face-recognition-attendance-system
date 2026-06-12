from datetime import datetime

from app.extensions import db


class FaceProfile(db.Model):
    __tablename__ = "face_profiles"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id", ondelete="CASCADE"), unique=True, nullable=False)
    image_path = db.Column(db.String(255), nullable=False)
    face_encoding = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    student = db.relationship("Student", back_populates="face_profile")
