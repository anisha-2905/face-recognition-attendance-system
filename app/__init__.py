from flask import Flask, redirect, request, url_for

from app.config import Config
from app.extensions import db, login_manager
from app.models import User


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "warning"

    register_blueprints(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    @login_manager.unauthorized_handler
    def unauthorized():
        if request.path.startswith("/admin"):
            return redirect(url_for("admin.login", next=request.full_path))
        if request.path.startswith("/teacher"):
            return redirect(url_for("auth.teacher_login", next=request.full_path))
        return redirect(url_for("auth.student_login", next=request.full_path))

    return app


def register_blueprints(app):
    from app.controllers.admin_controller import admin_bp
    from app.controllers.auth_controller import auth_bp
    from app.controllers.main_controller import main_bp
    from app.controllers.student_controller import student_bp
    from app.controllers.teacher_controller import teacher_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(teacher_bp, url_prefix="/teacher")
    app.register_blueprint(student_bp, url_prefix="/student")
