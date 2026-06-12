USE face_attendance;

INSERT INTO users (id, name, email, password_hash, role)
VALUES
  (1, 'System Admin', 'admin@example.com', 'replace-with-generated-hash', 'admin'),
  (2, 'Demo Teacher', 'teacher@example.com', 'replace-with-generated-hash', 'teacher'),
  (3, 'Demo Student', 'student@example.com', 'replace-with-generated-hash', 'student');

INSERT INTO departments (id, code, name, description)
VALUES (1, 'CSE', 'Computer Science', 'Computer Science and Engineering');

INSERT INTO teachers (id, user_id, employee_number, department_id, department, designation)
VALUES (1, 2, 'TCH001', 1, 'Computer Science', 'Assistant Professor');

INSERT INTO students (id, user_id, roll_number, admission_number, department_id, department, semester, section)
VALUES (1, 3, 'STU001', 'ADM001', 1, 'Computer Science', '1', 'A');

INSERT INTO subjects (id, code, name, department_id, department, semester, teacher_id)
VALUES (1, 'CS101', 'Introduction to Computer Science', 1, 'Computer Science', '1', 1);

INSERT INTO student_subjects (student_id, subject_id)
VALUES (1, 1);
