from functools import wraps

from flask import abort, redirect, request, session, url_for
from flask_login import current_user


def roles_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                if request.path.startswith("/admin"):
                    return redirect(url_for("admin.login", next=request.full_path))
                if request.path.startswith("/teacher"):
                    return redirect(url_for("auth.teacher_login", next=request.full_path))
                return redirect(url_for("auth.student_login", next=request.full_path))
            session_role = session.get("role")
            if current_user.role not in roles or session_role != current_user.role:
                abort(403)
            return view_func(*args, **kwargs)

        return wrapper

    return decorator
