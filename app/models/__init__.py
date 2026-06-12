from app.models.attendance import Attendance
from app.models.attendance_settings import AttendanceSettings
from app.models.activity_log import ActivityLog
from app.models.course import Course
from app.models.department import Department
from app.models.enrollment import Enrollment
from app.models.face_profile import FaceProfile
from app.models.schedule import Schedule
from app.models.student import Student
from app.models.subject import Subject
from app.models.teacher import Teacher
from app.models.user import User

__all__ = [
    "ActivityLog",
    "Attendance",
    "AttendanceSettings",
    "Course",
    "Department",
    "Enrollment",
    "FaceProfile",
    "Schedule",
    "Student",
    "Subject",
    "Teacher",
    "User",
]
