from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.forms import DepartmentForm, LoginForm, StudentForm, SubjectForm, TeacherForm, UserForm
from app.models import Attendance, Department, Enrollment, FaceProfile, Student, Subject, Teacher, User
from app.services.attendance_service import get_attendance_settings
from app.services.auth_service import authenticate, create_user, login_user_with_session
from app.utils.decorators import roles_required

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        if current_user.role == "admin":
            return redirect(url_for("admin.dashboard"))
        flash("Sign out before accessing the admin portal.", "warning")
        return redirect(url_for(f"{current_user.role}.dashboard"))

    form = LoginForm()
    form.role.data = "admin"
    if form.validate_on_submit():
        user = authenticate(form.email.data, form.password.data, "admin")
        if user:
            login_user_with_session(user)
            flash(f"Welcome back, {user.name}.", "success")
            return redirect(request.args.get("next") or url_for("admin.dashboard"))
        flash("Invalid admin credentials.", "danger")
    return render_template("auth/login.html", form=form, expected_role="admin", admin_portal=True)


@admin_bp.route("/dashboard")
@login_required
@roles_required("admin")
def dashboard():
    stats = {
        "students": Student.query.count(),
        "teachers": Teacher.query.count(),
        "subjects": Subject.query.count(),
        "departments": Department.query.count(),
        "attendance": Attendance.query.count(),
    }
    recent_students = Student.query.order_by(Student.created_at.desc()).limit(5).all()
    recent_teachers = Teacher.query.order_by(Teacher.created_at.desc()).limit(5).all()
    return render_template(
        "admin/dashboard.html",
        stats=stats,
        recent_students=recent_students,
        recent_teachers=recent_teachers,
    )


@admin_bp.route("/users")
@login_required
@roles_required("admin")
def users():
    return render_template("admin/users.html", users=User.query.order_by(User.created_at.desc()).all())


@admin_bp.route("/attendance")
@login_required
@roles_required("admin")
def attendance_records():
    query = Attendance.query.join(Student).join(Subject)
    subject_id = _int_arg("subject_id")
    student_id = _int_arg("student_id")
    status = request.args.get("status", "").strip()
    if subject_id:
        query = query.filter(Attendance.subject_id == subject_id)
    if student_id:
        query = query.filter(Attendance.student_id == student_id)
    if status:
        query = query.filter(Attendance.status == status)
    return render_template(
        "admin/attendance.html",
        records=query.order_by(Attendance.attendance_date.desc(), Student.roll_number.asc()).limit(300).all(),
        subjects=Subject.query.order_by(Subject.code.asc()).all(),
        students=Student.query.join(User).order_by(User.name.asc()).all(),
        filters={"subject_id": subject_id, "student_id": student_id, "status": status},
    )


@admin_bp.route("/attendance-settings", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def attendance_settings():
    settings = get_attendance_settings()
    if request.method == "POST":
        start_time = _time_value("start_time")
        end_time = _time_value("end_time")
        if not start_time or not end_time:
            flash("Enter valid start and end times.", "danger")
            return redirect(url_for("admin.attendance_settings"))
        if start_time >= end_time:
            flash("Attendance start time must be before end time.", "danger")
            return redirect(url_for("admin.attendance_settings"))
        settings.start_time = start_time
        settings.end_time = end_time
        settings.auto_absent_enabled = bool(request.form.get("auto_absent_enabled"))
        db.session.commit()
        flash("Attendance settings updated.", "success")
        return redirect(url_for("admin.attendance_settings"))
    return render_template("admin/attendance_settings.html", settings=settings)


@admin_bp.route("/face-profiles")
@login_required
@roles_required("admin")
def face_profiles():
    return render_template(
        "admin/face_profiles.html",
        profiles=FaceProfile.query.join(Student).join(User).order_by(User.name.asc()).all(),
    )


@admin_bp.route("/face-profiles/<int:profile_id>/delete", methods=["POST"])
@login_required
@roles_required("admin")
def delete_face_profile(profile_id):
    profile = FaceProfile.query.get_or_404(profile_id)
    db.session.delete(profile)
    db.session.commit()
    flash("Face profile removed. The student can register again.", "success")
    return redirect(url_for("admin.face_profiles"))


@admin_bp.route("/users/create", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def create_user_view():
    form = UserForm()
    if form.validate_on_submit():
        create_user(
            name=form.name.data,
            email=form.email.data,
            password=form.password.data or "ChangeMe@123",
            role=form.role.data,
            roll_number=form.roll_number.data,
        )
        flash("User created successfully.", "success")
        return redirect(url_for("admin.users"))
    return render_template("admin/user_form.html", form=form)


@admin_bp.route("/students")
@login_required
@roles_required("admin")
def students():
    records = Student.query.join(User).order_by(User.name.asc()).all()
    return render_template("admin/students.html", students=records)


@admin_bp.route("/students/create", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def create_student():
    form = StudentForm()
    _set_department_choices(form)
    if form.validate_on_submit():
        user = User(
            name=form.name.data,
            email=form.email.data,
            password_hash=generate_password_hash(form.password.data or "Student@123"),
            role="student",
        )
        student = Student(
            user=user,
            roll_number=form.roll_number.data,
            admission_number=form.admission_number.data or None,
            department_id=_selected_id(form.department_id.data),
            department=_department_name(form.department_id.data),
            semester=form.semester.data,
            section=form.section.data,
            phone=form.phone.data,
        )
        return _commit_or_form_error(student, "Student created successfully.", "admin.students")
    return render_template("admin/student_form.html", form=form, title="Create Student")


@admin_bp.route("/students/<int:student_id>/edit", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def edit_student(student_id):
    student = Student.query.get_or_404(student_id)
    form = StudentForm(obj=student)
    _set_department_choices(form)
    if not form.is_submitted():
        form.name.data = student.user.name
        form.email.data = student.user.email
    if form.validate_on_submit():
        student.user.name = form.name.data
        student.user.email = form.email.data
        if form.password.data:
            student.user.password_hash = generate_password_hash(form.password.data)
        student.roll_number = form.roll_number.data
        student.admission_number = form.admission_number.data or None
        student.department_id = _selected_id(form.department_id.data)
        student.department = _department_name(form.department_id.data)
        student.semester = form.semester.data
        student.section = form.section.data
        student.phone = form.phone.data
        return _commit_or_form_error(student, "Student updated successfully.", "admin.students")
    return render_template("admin/student_form.html", form=form, title="Edit Student")


@admin_bp.route("/students/<int:student_id>/delete", methods=["POST"])
@login_required
@roles_required("admin")
def delete_student(student_id):
    student = Student.query.get_or_404(student_id)
    db.session.delete(student.user)
    db.session.commit()
    flash("Student deleted successfully.", "success")
    return redirect(url_for("admin.students"))


@admin_bp.route("/teachers")
@login_required
@roles_required("admin")
def teachers():
    records = Teacher.query.join(User).order_by(User.name.asc()).all()
    return render_template("admin/teachers.html", teachers=records)


@admin_bp.route("/teachers/create", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def create_teacher():
    form = TeacherForm()
    _set_department_choices(form)
    if form.validate_on_submit():
        user = User(
            name=form.name.data,
            email=form.email.data,
            password_hash=generate_password_hash(form.password.data or "Teacher@123"),
            role="teacher",
        )
        teacher = Teacher(
            user=user,
            employee_number=form.employee_number.data,
            department_id=_selected_id(form.department_id.data),
            department=_department_name(form.department_id.data),
            designation=form.designation.data,
            phone=form.phone.data,
        )
        return _commit_or_form_error(teacher, "Teacher created successfully.", "admin.teachers")
    return render_template("admin/teacher_form.html", form=form, title="Create Teacher")


@admin_bp.route("/teachers/<int:teacher_id>/edit", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def edit_teacher(teacher_id):
    teacher = Teacher.query.get_or_404(teacher_id)
    form = TeacherForm(obj=teacher)
    _set_department_choices(form)
    if not form.is_submitted():
        form.name.data = teacher.user.name
        form.email.data = teacher.user.email
    if form.validate_on_submit():
        teacher.user.name = form.name.data
        teacher.user.email = form.email.data
        if form.password.data:
            teacher.user.password_hash = generate_password_hash(form.password.data)
        teacher.employee_number = form.employee_number.data
        teacher.department_id = _selected_id(form.department_id.data)
        teacher.department = _department_name(form.department_id.data)
        teacher.designation = form.designation.data
        teacher.phone = form.phone.data
        return _commit_or_form_error(teacher, "Teacher updated successfully.", "admin.teachers")
    return render_template("admin/teacher_form.html", form=form, title="Edit Teacher")


@admin_bp.route("/teachers/<int:teacher_id>/delete", methods=["POST"])
@login_required
@roles_required("admin")
def delete_teacher(teacher_id):
    teacher = Teacher.query.get_or_404(teacher_id)
    db.session.delete(teacher.user)
    db.session.commit()
    flash("Teacher deleted successfully.", "success")
    return redirect(url_for("admin.teachers"))


@admin_bp.route("/subjects")
@login_required
@roles_required("admin")
def subjects():
    return render_template("admin/subjects.html", subjects=Subject.query.order_by(Subject.code.asc()).all())


@admin_bp.route("/subject-allocation", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def subject_allocation():
    if request.method == "POST":
        student_id = _form_int("student_id")
        subject_ids = [int(value) for value in request.form.getlist("subject_ids") if value.isdigit()]
        student = Student.query.get(student_id) if student_id else None
        if not student:
            flash("Select a valid student.", "danger")
            return redirect(url_for("admin.subject_allocation"))
        if not subject_ids:
            flash("Select at least one subject to assign.", "warning")
            return redirect(url_for("admin.subject_allocation", student_id=student.id))

        created = 0
        for subject_id in subject_ids:
            subject = Subject.query.get(subject_id)
            if not subject:
                continue
            existing = Enrollment.query.filter_by(student_id=student.id, subject_id=subject.id).first()
            if existing:
                continue
            db.session.add(Enrollment(student_id=student.id, subject_id=subject.id))
            created += 1
        db.session.commit()
        if created:
            flash(f"Assigned {created} subject(s) to {student.user.name}.", "success")
        else:
            flash("Selected subject(s) were already assigned.", "info")
        return redirect(url_for("admin.subject_allocation", student_id=student.id))

    filters = _allocation_filters()
    student_query = Student.query.join(User)
    subject_query = Subject.query
    if filters["department_id"]:
        student_query = student_query.filter(Student.department_id == filters["department_id"])
        subject_query = subject_query.filter(Subject.department_id == filters["department_id"])
    if filters["section"]:
        student_query = student_query.filter(Student.section == filters["section"])
    if filters["semester"]:
        student_query = student_query.filter(Student.semester == filters["semester"])
        subject_query = subject_query.filter(Subject.semester == filters["semester"])

    students = student_query.order_by(User.name.asc()).all()
    subjects = subject_query.order_by(Subject.code.asc()).all()
    selected_student_id = filters["student_id"] or (students[0].id if students else None)
    selected_student = next((student for student in students if student.id == selected_student_id), None)
    if selected_student is None and selected_student_id:
        selected_student = Student.query.get(selected_student_id)
    assigned_subject_ids = {enrollment.subject_id for enrollment in selected_student.enrollments} if selected_student else set()
    return render_template(
        "admin/subject_allocation.html",
        students=students,
        subjects=subjects,
        departments=Department.query.order_by(Department.name.asc()).all(),
        selected_student=selected_student,
        assigned_subject_ids=assigned_subject_ids,
        filters=filters,
    )


@admin_bp.route("/subject-allocation/<int:enrollment_id>/remove", methods=["POST"])
@login_required
@roles_required("admin")
def remove_subject_allocation(enrollment_id):
    enrollment = Enrollment.query.get_or_404(enrollment_id)
    student_id = enrollment.student_id
    db.session.delete(enrollment)
    db.session.commit()
    flash("Subject assignment removed.", "success")
    return redirect(url_for("admin.subject_allocation", student_id=student_id))


@admin_bp.route("/subjects/create", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def create_subject():
    form = SubjectForm()
    _set_subject_choices(form)
    if form.validate_on_submit():
        subject = Subject(
            code=form.code.data,
            name=form.name.data,
            department_id=_selected_id(form.department_id.data),
            department=_department_name(form.department_id.data),
            semester=form.semester.data,
            teacher_id=_selected_id(form.teacher_id.data),
        )
        return _commit_or_form_error(subject, "Subject created successfully.", "admin.subjects")
    return render_template("admin/subject_form.html", form=form, title="Create Subject")


@admin_bp.route("/subjects/<int:subject_id>/edit", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def edit_subject(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    form = SubjectForm(obj=subject)
    _set_subject_choices(form)
    if form.validate_on_submit():
        subject.code = form.code.data
        subject.name = form.name.data
        subject.department_id = _selected_id(form.department_id.data)
        subject.department = _department_name(form.department_id.data)
        subject.semester = form.semester.data
        subject.teacher_id = _selected_id(form.teacher_id.data)
        return _commit_or_form_error(subject, "Subject updated successfully.", "admin.subjects")
    return render_template("admin/subject_form.html", form=form, title="Edit Subject")


@admin_bp.route("/subjects/<int:subject_id>/delete", methods=["POST"])
@login_required
@roles_required("admin")
def delete_subject(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    db.session.delete(subject)
    db.session.commit()
    flash("Subject deleted successfully.", "success")
    return redirect(url_for("admin.subjects"))


@admin_bp.route("/departments")
@login_required
@roles_required("admin")
def departments():
    return render_template(
        "admin/departments.html",
        departments=Department.query.order_by(Department.name.asc()).all(),
    )


@admin_bp.route("/departments/create", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def create_department():
    form = DepartmentForm()
    if form.validate_on_submit():
        department = Department(
            code=form.code.data,
            name=form.name.data,
            description=form.description.data,
        )
        return _commit_or_form_error(department, "Department created successfully.", "admin.departments")
    return render_template("admin/department_form.html", form=form, title="Create Department")


@admin_bp.route("/departments/<int:department_id>/edit", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def edit_department(department_id):
    department = Department.query.get_or_404(department_id)
    form = DepartmentForm(obj=department)
    if form.validate_on_submit():
        department.code = form.code.data
        department.name = form.name.data
        department.description = form.description.data
        return _commit_or_form_error(department, "Department updated successfully.", "admin.departments")
    return render_template("admin/department_form.html", form=form, title="Edit Department")


@admin_bp.route("/departments/<int:department_id>/delete", methods=["POST"])
@login_required
@roles_required("admin")
def delete_department(department_id):
    department = Department.query.get_or_404(department_id)
    db.session.delete(department)
    db.session.commit()
    flash("Department deleted successfully.", "success")
    return redirect(url_for("admin.departments"))


def _set_department_choices(form):
    form.department_id.choices = [(0, "Unassigned")] + [
        (department.id, department.name) for department in Department.query.order_by(Department.name.asc()).all()
    ]


def _set_subject_choices(form):
    _set_department_choices(form)
    form.teacher_id.choices = [(0, "Unassigned")] + [
        (teacher.id, teacher.user.name) for teacher in Teacher.query.join(User).order_by(User.name.asc()).all()
    ]


def _selected_id(value):
    return value or None


def _int_arg(name):
    value = request.args.get(name, "").strip()
    return int(value) if value.isdigit() else None


def _form_int(name):
    value = request.form.get(name, "").strip()
    return int(value) if value.isdigit() else None


def _allocation_filters():
    return {
        "department_id": _int_arg("department_id"),
        "section": request.args.get("section", "").strip(),
        "semester": request.args.get("semester", "").strip(),
        "student_id": _int_arg("student_id"),
    }


def _time_value(name):
    value = request.form.get(name, "").strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, "%H:%M").time()
    except ValueError:
        return None


def _department_name(department_id):
    department_id = _selected_id(department_id)
    if department_id is None:
        return None
    department = Department.query.get(department_id)
    return department.name if department else None


def _commit_or_form_error(record, success_message, redirect_endpoint):
    try:
        db.session.add(record)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("Could not save record. Check for duplicate email, code, roll number, or employee number.", "danger")
        return redirect(url_for(redirect_endpoint))
    flash(success_message, "success")
    return redirect(url_for(redirect_endpoint))
