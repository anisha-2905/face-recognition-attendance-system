from flask_wtf import FlaskForm
from wtforms import PasswordField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, Length, Optional


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    role = SelectField(
        "Role",
        choices=[("admin", "Admin"), ("teacher", "Teacher"), ("student", "Student")],
        validators=[DataRequired()],
    )
    submit = SubmitField("Sign in")


class UserForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=120)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    role = SelectField(
        "Role",
        choices=[("admin", "Admin"), ("teacher", "Teacher"), ("student", "Student")],
        validators=[DataRequired()],
    )
    roll_number = StringField("Roll / employee number", validators=[Optional(), Length(max=50)])
    password = PasswordField("Password", validators=[Optional(), Length(min=6)])
    submit = SubmitField("Save user")


class StudentForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=120)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField("Password", validators=[Optional(), Length(min=6)])
    roll_number = StringField("Roll number", validators=[DataRequired(), Length(max=50)])
    admission_number = StringField("Admission number", validators=[Optional(), Length(max=50)])
    department_id = SelectField("Department", coerce=int, validators=[Optional()])
    semester = StringField("Semester", validators=[Optional(), Length(max=30)])
    section = StringField("Section", validators=[Optional(), Length(max=30)])
    phone = StringField("Phone", validators=[Optional(), Length(max=30)])
    submit = SubmitField("Save student")


class TeacherForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=120)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField("Password", validators=[Optional(), Length(min=6)])
    employee_number = StringField("Employee number", validators=[DataRequired(), Length(max=50)])
    department_id = SelectField("Department", coerce=int, validators=[Optional()])
    designation = StringField("Designation", validators=[Optional(), Length(max=100)])
    phone = StringField("Phone", validators=[Optional(), Length(max=30)])
    submit = SubmitField("Save teacher")


class SubjectForm(FlaskForm):
    code = StringField("Subject code", validators=[DataRequired(), Length(max=30)])
    name = StringField("Subject name", validators=[DataRequired(), Length(max=150)])
    department_id = SelectField("Department", coerce=int, validators=[Optional()])
    semester = StringField("Semester", validators=[Optional(), Length(max=30)])
    teacher_id = SelectField("Teacher", coerce=int, validators=[Optional()])
    submit = SubmitField("Save subject")


class DepartmentForm(FlaskForm):
    code = StringField("Department code", validators=[DataRequired(), Length(max=30)])
    name = StringField("Department name", validators=[DataRequired(), Length(max=120)])
    description = StringField("Description", validators=[Optional(), Length(max=255)])
    submit = SubmitField("Save department")


CourseForm = SubjectForm
