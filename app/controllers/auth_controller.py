from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.forms import LoginForm
from app.services.auth_service import authenticate, login_user_with_session, logout_current_user

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

ROLE_DASHBOARDS = {
    "admin": "admin.dashboard",
    "teacher": "teacher.dashboard",
    "student": "student.dashboard",
}


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    return redirect(url_for("auth.student_login"))


@auth_bp.route("/teacher/login", methods=["GET", "POST"])
def teacher_login():
    return _login(expected_role="teacher")


@auth_bp.route("/student/login", methods=["GET", "POST"])
def student_login():
    return _login(expected_role="student")


def _login(expected_role=None):
    if current_user.is_authenticated:
        return redirect(url_for(ROLE_DASHBOARDS.get(current_user.role, "main.index")))

    form = LoginForm()
    if expected_role and request.method == "GET":
        form.role.data = expected_role

    if form.validate_on_submit():
        selected_role = expected_role or form.role.data
        user = authenticate(form.email.data, form.password.data, selected_role)
        if user:
            login_user_with_session(user)
            flash(f"Welcome back, {user.name}.", "success")
            return redirect(request.args.get("next") or url_for(ROLE_DASHBOARDS[user.role]))
        flash("Invalid credentials for the selected role.", "danger")

    return render_template("auth/login.html", form=form, expected_role=expected_role)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_current_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("auth.login"))
