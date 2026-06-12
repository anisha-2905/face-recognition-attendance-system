from datetime import date, time

from app.extensions import db
from app.models import Attendance, AttendanceSettings, Enrollment


def get_attendance_settings():
    settings = AttendanceSettings.query.order_by(AttendanceSettings.id.asc()).first()
    if settings is None:
        settings = AttendanceSettings(start_time=time(9, 0), end_time=time(17, 0), auto_absent_enabled=True)
        db.session.add(settings)
        db.session.commit()
    return settings


def mark_attendance(student_id, subject_id, status="present", confidence=None, captured_image=None):
    attendance = Attendance.query.filter_by(
        student_id=student_id,
        subject_id=subject_id,
        attendance_date=date.today(),
    ).first()

    if attendance is None:
        attendance = Attendance(
            student_id=student_id,
            subject_id=subject_id,
            attendance_date=date.today(),
            method="manual",
            attendance_source="manual",
        )
        db.session.add(attendance)

    attendance.status = status
    attendance.confidence = confidence
    attendance.captured_image = captured_image
    db.session.commit()
    return attendance


def auto_mark_absent(subject_id, attendance_date):
    assigned_students = Enrollment.query.filter_by(subject_id=subject_id).all()
    existing_records = Attendance.query.filter_by(
        subject_id=subject_id,
        attendance_date=attendance_date,
    ).all()
    existing_by_student = {record.student_id: record for record in existing_records}
    present_count = sum(1 for record in existing_records if record.status == "present")
    created_absent = 0

    for enrollment in assigned_students:
        if enrollment.student_id in existing_by_student:
            continue
        attendance = Attendance(
            student_id=enrollment.student_id,
            subject_id=subject_id,
            attendance_date=attendance_date,
            status="absent",
            method="system",
            attendance_source="auto_absent",
            remarks="Automatically marked absent because no attendance was recorded",
        )
        db.session.add(attendance)
        created_absent += 1

    db.session.commit()
    return {
        "present_count": present_count,
        "auto_absent_count": created_absent,
        "assigned_count": len(assigned_students),
    }
