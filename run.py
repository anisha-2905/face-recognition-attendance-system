from app import create_app
from app.extensions import db
from app.models import Attendance, Department, Enrollment, FaceProfile, Schedule, Student, Subject, Teacher, User

app = create_app()


@app.cli.command("init-db")
def init_db():
    """Create database tables."""
    db.create_all()
    print("Database tables created.")


@app.cli.command("seed-db")
def seed_db():
    """Seed demo users, profiles, and a sample subject."""
    from werkzeug.security import generate_password_hash

    if User.query.filter_by(email="admin@example.com").first():
        print("Seed data already exists.")
        return

    admin = User(
        name="System Admin",
        email="admin@example.com",
        password_hash=generate_password_hash("Admin@123"),
        role="admin",
    )
    teacher = User(
        name="Demo Teacher",
        email="teacher@example.com",
        password_hash=generate_password_hash("Teacher@123"),
        role="teacher",
    )
    student = User(
        name="Demo Student",
        email="student@example.com",
        password_hash=generate_password_hash("Student@123"),
        role="student",
    )
    db.session.add_all([admin, teacher, student])
    db.session.flush()

    department = Department(code="CSE", name="Computer Science", description="Computer Science and Engineering")
    db.session.add(department)
    db.session.flush()

    teacher_profile = Teacher(
        user_id=teacher.id,
        employee_number="TCH001",
        department_id=department.id,
        department=department.name,
    )
    student_profile = Student(
        user_id=student.id,
        roll_number="STU001",
        department_id=department.id,
        department=department.name,
    )
    db.session.add_all([teacher_profile, student_profile])
    db.session.flush()

    subject = Subject(
        code="CS101",
        name="Introduction to Computer Science",
        department_id=department.id,
        department=department.name,
        teacher_id=teacher_profile.id,
    )
    db.session.add(subject)
    db.session.flush()
    db.session.add(Enrollment(student_id=student_profile.id, subject_id=subject.id))
    db.session.commit()
    print("Demo data seeded.")


if __name__ == "__main__":
    app.run(debug=True)
