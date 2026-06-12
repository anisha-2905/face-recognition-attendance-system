from collections import defaultdict
from datetime import datetime
from io import BytesIO

from flask import Blueprint, flash, jsonify, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from app.models import Attendance, Enrollment, Subject
from app.services.attendance_service import get_attendance_settings
from app.services.face_service import (
    FaceRegistrationError,
    decode_image_data,
    mark_attendance,
    recognize_student_face,
    register_face,
)
from app.utils.decorators import roles_required

student_bp = Blueprint("student", __name__)


@student_bp.route("/dashboard")
@login_required
@roles_required("student")
def dashboard():
    student = current_user.student_profile
    if not student:
        flash("Student profile is not available.", "warning")
        return render_template(
            "student/dashboard.html",
            student=None,
            enrollments=[],
            attendance=[],
            last_attendance=None,
            today_attendance=[],
            stats={},
        )

    enrollments = Enrollment.query.filter_by(student_id=student.id).all()
    attendance = _attendance_query(student).limit(8).all()
    last_attendance = Attendance.query.filter_by(student_id=student.id).order_by(Attendance.marked_at.desc()).first()
    today_attendance = _today_attendance(student)
    stats = _attendance_stats(student)
    return render_template(
        "student/dashboard.html",
        student=student,
        enrollments=enrollments,
        attendance=attendance,
        last_attendance=last_attendance,
        today_attendance=today_attendance,
        stats=stats,
    )


@student_bp.route("/face", methods=["GET"])
@login_required
@roles_required("student")
def register_face_page():
    student = current_user.student_profile
    if not student:
        flash("Student profile is not available.", "warning")
        return redirect(url_for("student.dashboard"))
    return render_template("student/register_face.html", student=student)


@student_bp.route("/face/register", methods=["POST"])
@login_required
@roles_required("student")
def register_face_capture():
    student = current_user.student_profile
    if not student:
        return jsonify({"ok": False, "message": "Student profile is not available."}), 400

    payload = request.get_json(silent=True) or {}
    images = payload.get("images", [])
    replace = bool(payload.get("replace"))
    try:
        profile = register_face(student.id, images=images, replace=replace)
    except FaceRegistrationError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400

    return jsonify(
        {
            "ok": True,
            "message": "Face registration completed.",
            "image_url": url_for("static", filename=profile.image_path),
        }
    )


@student_bp.route("/attendance/scan")
@login_required
@roles_required("student")
def scan_attendance_page():
    student = current_user.student_profile
    if not student:
        flash("Student profile is not available.", "warning")
        return redirect(url_for("student.dashboard"))

    enrollments = Enrollment.query.filter_by(student_id=student.id).all()
    selected_subject_id = _int_arg("subject_id") or (enrollments[0].subject_id if enrollments else None)
    selected_subject = next(
        (enrollment.subject for enrollment in enrollments if enrollment.subject_id == selected_subject_id),
        None,
    )
    today_attendance = _today_attendance(student, selected_subject_id)
    return render_template(
        "student/scan_attendance.html",
        student=student,
        enrollments=enrollments,
        selected_subject=selected_subject,
        today_attendance=today_attendance,
    )


@student_bp.route("/attendance/scan/mark", methods=["POST"])
@login_required
@roles_required("student")
def scan_attendance_mark():
    student = current_user.student_profile
    if not student:
        return jsonify({"ok": False, "message": "Student profile is not available."}), 400

    payload = request.get_json(silent=True) or {}
    subject_id = payload.get("subject_id")
    image_data = payload.get("image")
    if not subject_id:
        return jsonify({"ok": False, "message": "Select a subject before scanning."}), 400
    if not image_data:
        return jsonify({"ok": False, "message": "No camera frame received."}), 400

    settings = get_attendance_settings()
    now_time = datetime.utcnow().time()
    if now_time < settings.start_time or now_time > settings.end_time:
        return jsonify(
            {
                "ok": False,
                "message": f"Attendance window is closed. Scan between {settings.start_time.strftime('%H:%M')} and {settings.end_time.strftime('%H:%M')}.",
            }
        ), 400

    subject = Subject.query.join(Enrollment, Enrollment.subject_id == Subject.id).filter(
        Enrollment.student_id == student.id,
        Subject.id == subject_id,
    ).first()
    if not subject:
        return jsonify({"ok": False, "message": "You are not enrolled in the selected subject."}), 400

    try:
        frame = decode_image_data(image_data)
        result = recognize_student_face(student.id, frame)
        if not result["matched"]:
            return jsonify({"ok": False, "message": result.get("reason") or "Face verification failed.", "result": result}), 400
        attendance, created = mark_attendance(
            student.id,
            subject_id=subject.id,
            confidence=result["confidence"],
        )
    except FaceRegistrationError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400

    return jsonify(
        {
            "ok": True,
            "created": created,
            "message": "Attendance marked present." if created else "Attendance already marked for this subject today.",
            "attendance": {
                "status": attendance.status,
                "subject": attendance.subject.code,
                "marked_at": attendance.marked_at.strftime("%Y-%m-%d %H:%M:%S"),
                "confidence": attendance.confidence or result["confidence"],
            },
            "result": result,
        }
    )


@student_bp.route("/attendance")
@login_required
@roles_required("student")
def attendance_history():
    student = current_user.student_profile
    if not student:
        return render_template("student/attendance.html", records=[], subjects=[], filters={}, export_args={})

    records = _attendance_query(student).limit(200).all()
    subjects = _enrolled_subjects(student)
    return render_template(
        "student/attendance.html",
        records=records,
        subjects=subjects,
        filters=_filters(),
        export_args=request.args.to_dict(),
    )


@student_bp.route("/profile")
@login_required
@roles_required("student")
def profile():
    student = current_user.student_profile
    return render_template("student/profile.html", student=student)


@student_bp.route("/reports")
@login_required
@roles_required("student")
def reports():
    student = current_user.student_profile
    if not student:
        return render_template(
            "student/reports.html",
            summaries=[],
            subjects=[],
            filters={},
            export_args={},
            analytics=_empty_attendance_analytics(),
        )

    records = _attendance_query(student).all()
    summaries = _build_subject_summary(records)
    subjects = _enrolled_subjects(student)
    analytics = _build_attendance_analytics(records)
    return render_template(
        "student/reports.html",
        summaries=summaries,
        subjects=subjects,
        filters=_filters(),
        export_args=request.args.to_dict(),
        analytics=analytics,
    )


@student_bp.route("/attendance/export/excel")
@login_required
@roles_required("student")
def export_attendance_excel():
    student = current_user.student_profile
    if not student:
        flash("Student profile is not available.", "warning")
        return redirect(url_for("student.dashboard"))

    output = _build_excel(_attendance_query(student).all())
    return send_file(
        output,
        as_attachment=True,
        download_name="my_attendance_report.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@student_bp.route("/attendance/export/pdf")
@login_required
@roles_required("student")
def export_attendance_pdf():
    student = current_user.student_profile
    if not student:
        flash("Student profile is not available.", "warning")
        return redirect(url_for("student.dashboard"))

    output = _build_pdf(_attendance_query(student).all(), student)
    return send_file(
        output,
        as_attachment=True,
        download_name="my_attendance_report.pdf",
        mimetype="application/pdf",
    )


def _attendance_query(student):
    query = Attendance.query.join(Subject).filter(Attendance.student_id == student.id)
    filters = _filters()

    if filters["subject_id"]:
        query = query.filter(Attendance.subject_id == filters["subject_id"])
    if filters["status"]:
        query = query.filter(Attendance.status == filters["status"])
    if filters["start_date"]:
        query = query.filter(Attendance.attendance_date >= filters["start_date"])
    if filters["end_date"]:
        query = query.filter(Attendance.attendance_date <= filters["end_date"])

    return query.order_by(Attendance.attendance_date.desc(), Subject.code.asc())


def _filters():
    return {
        "subject_id": _int_arg("subject_id"),
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
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _enrolled_subjects(student):
    return [enrollment.subject for enrollment in student.enrollments]


def _today_attendance(student, subject_id=None):
    today = datetime.utcnow().date()
    query = Attendance.query.filter_by(student_id=student.id, attendance_date=today)
    if subject_id:
        query = query.filter_by(subject_id=subject_id)
    return query.order_by(Attendance.marked_at.desc()).all()


def _attendance_stats(student):
    records = Attendance.query.filter_by(student_id=student.id).all()
    total = len(records)
    present = sum(1 for record in records if record.status == "present")
    late = sum(1 for record in records if record.status == "late")
    absent = sum(1 for record in records if record.status == "absent")
    attended = present + late
    return {
        "subjects": len(student.enrollments),
        "total": total,
        "present": present,
        "late": late,
        "absent": absent,
        "percentage": round((attended / total) * 100, 1) if total else 0,
    }


def _build_subject_summary(records):
    summary = {}
    for record in records:
        item = summary.setdefault(
            record.subject_id,
            {"subject": record.subject, "present": 0, "late": 0, "absent": 0, "total": 0},
        )
        item[record.status] += 1
        item["total"] += 1

    rows = []
    for item in summary.values():
        attended = item["present"] + item["late"]
        item["percentage"] = round((attended / item["total"]) * 100, 1) if item["total"] else 0
        rows.append(item)
    return sorted(rows, key=lambda row: row["subject"].code)


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
    sheet.title = "My Attendance"
    headers = ["Date", "Subject", "Subject Name", "Status", "Source", "Method", "Confidence", "Marked By", "Marked At"]
    sheet.append(headers)
    for cell in sheet[1]:
        cell.font = Font(bold=True)

    for record in records:
        teacher_name = record.marked_by_teacher.user.name if record.marked_by_teacher else "-"
        sheet.append(
            [
                record.attendance_date.isoformat(),
                record.subject.code,
                record.subject.name,
                record.status.title(),
                _label(record.attendance_source),
                _label(record.method),
                record.confidence or 0,
                teacher_name,
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


def _build_pdf(records, student):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    output = BytesIO()
    document = SimpleDocTemplate(output, pagesize=landscape(A4), rightMargin=24, leftMargin=24, topMargin=24)
    styles = getSampleStyleSheet()
    title = f"Attendance Report - {student.user.name} ({student.roll_number})"
    data = [["Date", "Subject", "Status", "Source", "Method", "Confidence", "Marked By"]]

    for record in records:
        teacher_name = record.marked_by_teacher.user.name if record.marked_by_teacher else "-"
        data.append(
            [
                record.attendance_date.isoformat(),
                record.subject.code,
                record.status.title(),
                _label(record.attendance_source),
                _label(record.method),
                f"{record.confidence or 0:.2f}",
                teacher_name,
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

    document.build([Paragraph(title, styles["Title"]), Spacer(1, 12), table])
    output.seek(0)
    return output


def _label(value):
    return (value or "-").replace("_", " ").title()
