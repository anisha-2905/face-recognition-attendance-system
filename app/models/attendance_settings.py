from datetime import datetime, time

from app.extensions import db


class AttendanceSettings(db.Model):
    __tablename__ = "attendance_settings"

    id = db.Column(db.Integer, primary_key=True)
    start_time = db.Column(db.Time, nullable=False, default=time(9, 0))
    end_time = db.Column(db.Time, nullable=False, default=time(17, 0))
    auto_absent_enabled = db.Column(db.Boolean, nullable=False, default=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
