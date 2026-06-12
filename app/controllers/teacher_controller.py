from collections import defaultdict
from datetime import datetime
from io import BytesIO

from flask import Blueprint, flash, jsonify, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Attendance, Enrollment, Student, Subject
from app.services.attendance_service import auto_mark_absent, get_attendance_settings
from app.services.face_service import FaceRegistrationError, decode_image_data, load_known_faces, mark_attendance, recognize_face
from app.utils.decorators import roles_required

teacher_bp = Blueprint("teacher", __name__)


@teacher_bp.route("/dashboard")
@login_required
@roles_required("teacher")
def dashboard():
    teacher = current_user.teacher_profile
    if not teacher:
        flash("Teacher profile is not available.", "warning")
        return render_template(
            "teacher/dashboard.html",
            subjects=[],
            stats={},
            recent_records=[],
            subject_records=[],
            low_attendance_students=[],
        )

    subjects = Subject.query.filter_by(teacher_id=teacher.id).all()
    subject_ids = [subject.id for subject in subjects]
    today = datetime.utcnow().date()
    total_records = Attendance.query.filter(Attendance.subject_id.in_(subject_ids)).count() if subject_ids else 0
    present_count = (
        Attendance.query.filter(Attendance.subject_id.in_(subject_ids), Attendance.status == "present").count()
        if subject_ids
        else 0
    )
    today_present = (
        Attendance.query.filter(
            Attendance.subject_id.in_(subject_ids),
            Attendance.attendance_date == today,
            Attendance.status.in_(["present", "late"]),
        ).count()
        if subject_ids
        else 0
    )
    enrolled_pairs = sum(len(subject.enrollments) for subject in subjects)
    stats = {
        "subjects": len(subjects),
        "present_today": today_present,
        "absent_today": max(enrolled_pairs - today_present, 0) if enrolled_pairs else 0,
        "present_rate": round((present_count / total_records) * 100, 1) if total_records else 0,
    }
    recent_records = _attendance_query(teacher).limit(8).all()
    subject_records = _subject_records(subjects, subject_ids)
    low_attendance_students = _low_attendance_students(subject_ids)
    return render_template(
        "teacher/dashboard.html",
        subjects=subjects,
        stats=stats,
        recent_records=recent_records,
        subject_records=subject_records,
        low_attendance_students=low_attendance_students,
    )


@teacher_bp.route("/attendance")
@login_required
@roles_required("teacher")
def attendance():
    teacher = current_user.teacher_profile
    if not teacher:
        return render_template(
            "teacher/attendance.html",
            records=[],
            subjects=[],
            students=[],
            filters=_filters(),
            export_args=request.args.to_dict(),
            today=datetime.utcnow().date(),
        )

    records = _attendance_query(teacher).limit(200).all()
    subjects = Subject.query.filter_by(teacher_id=teacher.id).order_by(Subject.code.asc()).all()
    students = _teacher_students(teacher)
    return render_template(
        "teacher/attendance.html",
        records=records,
        subjects=subjects,
        students=students,
        filters=_filters(),
        export_args=request.args.to_dict(),
        today=datetime.utcnow().date(),
    )


@teacher_bp.route("/attendance/manual", methods=["POST"])
@login_required
@roles_required("teacher")
def manual_attendance():
    teacher = current_user.teacher_profile
    if not teacher:
        flash("Teacher profile is not available.", "warning")
        return redirect(url_for("teacher.attendance"))

    subject_id = _form_int("subject_id")
    student_id = _form_int("student_id")
    attendance_date = _form_date("attendance_date") or datetime.utcnow().date()
    status = request.form.get("status", "present")
    if status not in {"present", "absent", "late"}:
        status = "present"

    subject = Subject.query.filter_by(id=subject_id, teacher_id=teacher.id).first()
    enrollment = Enrollment.query.filter_by(student_id=student_id, subject_id=subject_id).first()
    if not subject or not enrollment:
        flash("Select one of your subjects and an enrolled student.", "danger")
        return redirect(url_for("teacher.attendance"))

    attendance = Attendance.query.filter_by(
        student_id=student_id,
        subject_id=subject_id,
        attendance_date=attendance_date,
    ).first()
    if attendance is None:
        attendance = Attendance(
            student_id=student_id,
            subject_id=subject_id,
            attendance_date=attendance_date,
            method="manual",
            attendance_source="teacher_manual",
        )
        db.session.add(attendance)

    attendance.status = status
    attendance.marked_by_teacher_id = teacher.id
    attendance.method = "manual"
    attendance.attendance_source = "teacher_manual"
    attendance.remarks = request.form.get("remarks", "").strip() or None
    db.session.commit()
    flash("Attendance saved.", "success")
    return redirect(url_for("teacher.attendance", **request.args.to_dict()))


@teacher_bp.route("/attendance/finalize", methods=["POST"])
@login_required
@roles_required("teacher")
def finalize_attendance():
    teacher = current_user.teacher_profile
    if not teacher:
        flash("Teacher profile is not available.", "warning")
        return redirect(url_for("teacher.attendance"))

    subject_id = _form_int("subject_id")
    attendance_date = _form_date("attendance_date") or datetime.utcnow().date()
    subject = Subject.query.filter_by(id=subject_id, teacher_id=teacher.id).first()
    if not subject:
        flash("Select one of your assigned subjects before finalizing attendance.", "danger")
        return redirect(url_for("teacher.attendance"))

    settings = get_attendance_settings()
    if not settings.auto_absent_enabled:
        flash("Automatic absent marking is disabled by admin.", "warning")
        return redirect(url_for("teacher.attendance", subject_id=subject.id, start_date=attendance_date, end_date=attendance_date))

    if attendance_date == datetime.utcnow().date() and datetime.utcnow().time() < settings.end_time:
        flash(f"Attendance window is still open until {settings.end_time.strftime('%H:%M')}.", "warning")
        return redirect(url_for("teacher.attendance", subject_id=subject.id, start_date=attendance_date, end_date=attendance_date))

    result = auto_mark_absent(subject.id, attendance_date)
    flash(
        f"Attendance finalized for {subject.code}. Present: {result['present_count']}, Auto absent: {result['auto_absent_count']}.",
        "success",
    )
    return redirect(url_for("teacher.attendance", subject_id=subject.id, start_date=attendance_date, end_date=attendance_date))


@teacher_bp.route("/attendance/<int:attendance_id>/update", methods=["POST"])
@login_required
@roles_required("teacher")
def update_attendance(attendance_id):
    teacher = current_user.teacher_profile
    if not teacher:
        flash("Teacher profile is not available.", "warning")
        return redirect(url_for("teacher.attendance"))

    attendance = (
        Attendance.query.join(Subject)
        .filter(Attendance.id == attendance_id, Subject.teacher_id == teacher.id)
        .first_or_404()
    )
    status = request.form.get("status", attendance.status)
    if status not in {"present", "absent", "late"}:
        status = attendance.status
    attendance.status = status
    attendance.method = "manual"
    attendance.attendance_source = "teacher_correction"
    attendance.marked_by_teacher_id = teacher.id
    attendance.remarks = request.form.get("remarks", "").strip() or attendance.remarks
    db.session.commit()
    flash("Attendance record updated.", "success")
    return redirect(url_for("teacher.attendance", **request.args.to_dict()))


@teacher_bp.route("/attendance/camera")
@login_required
@roles_required("teacher")
def attendance_camera():
    teacher = current_user.teacher_profile
    if not teacher:
        flash("Teacher profile is not available.", "warning")
        return redirect(url_for("teacher.dashboard"))

    subjects = Subject.query.filter_by(teacher_id=teacher.id).order_by(Subject.code.asc()).all()
    selected_subject_id = _int_arg("subject_id") or (subjects[0].id if subjects else None)
    selected_subject = next((subject for subject in subjects if subject.id == selected_subject_id), None)
    return render_template(
        "teacher/attendance_camera.html",
        subjects=subjects,
        selected_subject=selected_subject,
        known_face_count=len(load_known_faces()),
    )


@teacher_bp.route("/attendance/camera/recognize", methods=["POST"])
@login_required
@roles_required("teacher")
def recognize_attendance_frame():
    teacher = current_user.teacher_profile
    if not teacher:
        return jsonify({"ok": False, "message": "Teacher profile is not available."}), 400

    payload = request.get_json(silent=True) or {}
    subject_id = payload.get("subject_id")
    image_data = payload.get("image")
    subject = Subject.query.filter_by(id=subject_id, teacher_id=teacher.id).first()
    if not subject:
        return jsonify({"ok": False, "message": "Select one of your assigned subjects."}), 400
    if not image_data:
        return jsonify({"ok": False, "message": "No camera frame received."}), 400

    try:
        frame = decode_image_data(image_data)
        result = recognize_face(frame)
        marked = []
        for face in result.get("faces", []):
            if not face["matched"]:
                continue
            attendance, created = mark_attendance(
                face["student_id"],
                subject_id=subject.id,
                teacher_id=teacher.id,
                confidence=face["confidence"],
            )
            marked.append(
                {
                    "student_id": attendance.student_id,
                    "name": attendance.student.user.name,
                    "roll_number": attendance.student.roll_number,
                    "confidence": face["confidence"],
                    "created": created,
                    "marked_at": attendance.marked_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "subject": attendance.subject.code,
                }
            )
    except FaceRegistrationError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400

    return jsonify({"ok": True, "result": result, "marked": marked})


@teacher_bp.route("/reports")
@login_required
@roles_required("teacher")
def reports():
    teacher = current_user.teacher_profile
    if not teacher:
        return render_template(
            "teacher/reports.html",
            summaries=[],
            subjects=[],
            filters=_filters(),
            export_args=request.args.to_dict(),
            analytics=_empty_attendance_analytics(),
        )

    records = _attendance_query(teacher).all()
    summaries = _build_student_summary(records)
    subjects = Subject.query.filter_by(teacher_id=teacher.id).order_by(Subject.code.asc()).all()
    analytics = _build_attendance_analytics(records)
    return render_template(
        "teacher/reports.html",
        summaries=summaries,
        subjects=subjects,
        filters=_filters(),
        export_args=request.args.to_dict(),
        analytics=analytics,
    )


@teacher_bp.route("/attendance/export/excel")
@login_required
@roles_required("teacher")
def export_attendance_excel():
    teacher = current_user.teacher_profile
    if not teacher:
        flash("Teacher profile is not available.", "warning")
        return redirect(url_for("teacher.attendance"))

    records = _attendance_query(teacher).all()
    output = _build_excel(records)
    return send_file(
        output,
        as_attachment=True,
        download_name="attendance_report.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@teacher_bp.route("/attendance/export/pdf")
@login_required
@roles_required("teacher")
def export_attendance_pdf():
    teacher = current_user.teacher_profile
    if not teacher:
        flash("Teacher profile is not available.", "warning")
        return redirect(url_for("teacher.attendance"))

    records = _attendance_query(teacher).all()
    output = _build_pdf(records)
    return send_file(
        output,
        as_attachment=True,
        download_name="attendance_report.pdf",
        mimetype="application/pdf",
    )


def _attendance_query(teacher):
    query = (
        Attendance.query.join(Subject)
        .join(Student, Attendance.student_id == Student.id)
        .filter(Subject.teacher_id == teacher.id)
    )
    filters = _filters()

    if filters["subject_id"]:
        query = query.filter(Attendance.subject_id == filters["subject_id"])
    if filters["student_id"]:
        query = query.filter(Attendance.student_id == filters["student_id"])
    if filters["section"]:
        query = query.filter(Student.section == filters["section"])
    if filters["status"]:
        query = query.filter(Attendance.status == filters["status"])
    if filters["start_date"]:
        query = query.filter(Attendance.attendance_date >= filters["start_date"])
    if filters["end_date"]:
        query = query.filter(Attendance.attendance_date <= filters["end_date"])

    return query.order_by(Attendance.attendance_date.desc(), Student.roll_number.asc())


def _filters():
    return {
        "subject_id": _int_arg("subject_id"),
        "student_id": _int_arg("student_id"),
        "section": request.args.get("section", "").strip(),
        "status": request.args.get("status", "").strip(),
        "start_date": _date_arg("start_date"),
        "end_date": _date_arg("end_date"),
    }


def _int_arg(name):
    value = request.args.get(name, "").strip()
    return int(value) if value.isdigit() else None


def _date_arg(name):
    value = request.args.get(name, "").strip()
    if not value:
        return None


def _form_int(name):
    value = request.form.get(name, "").strip()
    return int(value) if value.isdigit() else None


def _form_date(name):
    value = request.form.get(name, "").strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _teacher_students(teacher):
    return (
        Student.query.join(Enrollment)
        .join(Subject, Enrollment.subject_id == Subject.id)
        .filter(Subject.teacher_id == teacher.id)
        .order_by(Student.roll_number.asc())
        .distinct()
        .all()
    )


def _subject_records(subjects, subject_ids):
    today = datetime.utcnow().date()
    rows = []
    for subject in subjects:
        present_today = Attendance.query.filter_by(
            subject_id=subject.id,
            attendance_date=today,
            status="present",
        ).count()
        rows.append(
            {
                "subject": subject,
                "students": len(subject.enrollments),
                "records": Attendance.query.filter_by(subject_id=subject.id).count(),
                "present_today": present_today,
            }
        )
    return rows


def _low_attendance_students(subject_ids):
    if not subject_ids:
        return []
    records = Attendance.query.filter(Attendance.subject_id.in_(subject_ids)).all()
    summary = {}
    for record in records:
        item = summary.setdefault(
            record.student_id,
            {"student": record.student, "present": 0, "late": 0, "total": 0},
        )
        if record.status == "present":
            item["present"] += 1
        if record.status == "late":
            item["late"] += 1
        item["total"] += 1

    rows = []
    for item in summary.values():
        attended = item["present"] + item["late"]
        percentage = round((attended / item["total"]) * 100, 1) if item["total"] else 0
        if percentage < 75:
            rows.append({"student": item["student"], "percentage": percentage})
    return sorted(rows, key=lambda row: row["percentage"])[:5]
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _build_student_summary(records):
    summary = {}
    for record in records:
        key = (record.student_id, record.subject_id)
        item = summary.setdefault(
            key,
            {
                "student": record.student,
                "subject": record.subject,
                "present": 0,
                "late": 0,
                "absent": 0,
                "total": 0,
            },
        )
        item[record.status] += 1
        item["total"] += 1

    rows = []
    for item in summary.values():
        attended = item["present"] + item["late"]
        item["percentage"] = round((attended / item["total"]) * 100, 1) if item["total"] else 0
        rows.append(item)
    return sorted(rows, key=lambda row: (row["subject"].code, row["student"].roll_number))


def _empty_attendance_analytics():
    return {
        "monthly": {"labels": [], "present": [], "late": [], "absent": [], "percentages": []},
        "status": {"present": 0, "late": 0, "absent": 0},
        "percentage": 0,
        "total": 0,
    }


def _build_attendance_analytics(records):
    analytics = _empty_attendance_analytics()
    monthly = defaultdict(lambda: {"present": 0, "late": 0, "absent": 0, "total": 0})

    for record in records:
        status = record.status
        if status not in analytics["status"]:
            continue

        month_key = record.attendance_date.strftime("%Y-%m")
        analytics["status"][status] += 1
        monthly[month_key][status] += 1
        monthly[month_key]["total"] += 1
        analytics["total"] += 1

    attended = analytics["status"]["present"] + analytics["status"]["late"]
    analytics["percentage"] = round((attended / analytics["total"]) * 100, 1) if analytics["total"] else 0

    for month_key in sorted(monthly):
        month = datetime.strptime(month_key, "%Y-%m")
        month_data = monthly[month_key]
        month_attended = month_data["present"] + month_data["late"]
        analytics["monthly"]["labels"].append(month.strftime("%b %Y"))
        analytics["monthly"]["present"].append(month_data["present"])
        analytics["monthly"]["late"].append(month_data["late"])
        analytics["monthly"]["absent"].append(month_data["absent"])
        analytics["monthly"]["percentages"].append(
            round((month_attended / month_data["total"]) * 100, 1) if month_data["total"] else 0
        )

    return analytics


def _build_excel(records):
    from openpyxl import Workbook
    from openpyxl.styles import Font

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Attendance"
    headers = ["Date", "Student", "Roll No.", "Subject", "Status", "Source", "Method", "Confidence", "Marked At"]
    sheet.append(headers)
    for cell in sheet[1]:
        cell.font = Font(bold=True)

    for record in records:
        sheet.append(
            [
                record.attendance_date.isoformat(),
                record.student.user.name,
                record.student.roll_number,
                f"{record.subject.code} - {record.subject.name}",
                record.status.title(),
                _label(record.attendance_source),
                _label(record.method),
                record.confidence or 0,
                record.marked_at.strftime("%Y-%m-%d %H:%M"),
            ]
        )

    for column in sheet.columns:
        width = max(len(str(cell.value or "")) for cell in column) + 2
        sheet.column_dimensions[column[0].column_letter].width = min(width, 42)

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output


def _build_pdf(records):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    output = BytesIO()
    document = SimpleDocTemplate(output, pagesize=landscape(A4), rightMargin=24, leftMargin=24, topMargin=24)
    styles = getSampleStyleSheet()
    data = [["Date", "Student", "Roll No.", "Subject", "Status", "Source", "Method", "Confidence"]]

    for record in records:
        data.append(
            [
                record.attendance_date.isoformat(),
                record.student.user.name,
                record.student.roll_number,
                record.subject.code,
                record.status.title(),
                _label(record.attendance_source),
                _label(record.method),
                f"{record.confidence or 0:.2f}",
            ]
        )

    table = Table(data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0d6efd")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#dee2e6")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f9fa")]),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
            ]
        )
    )

    document.build([Paragraph("Attendance Report", styles["Title"]), Spacer(1, 12), table])
    output.seek(0)
    return output


def _label(value):
    return (value or "-").replace("_", " ").title()
