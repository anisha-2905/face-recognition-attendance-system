# Face Recognition Attendance System

An AI-powered attendance management system built using Flask, MySQL, OpenCV, and Face Recognition technology. The system provides secure attendance tracking for educational institutions through role-based access for Admins, Teachers, and Students.

## Overview

Traditional attendance methods are time-consuming and prone to human error. This project automates attendance management using facial recognition while providing analytics, reporting, and role-based dashboards.

The system allows students to register and verify their face, automatically mark attendance, and enables teachers and administrators to manage records efficiently.

## Key Features

### Authentication & Role Management

* Separate Admin, Teacher, and Student login systems
* Secure password hashing using Werkzeug
* Session-based authentication
* Role-based route protection

### Face Recognition

* Student face registration
* Face encoding storage
* Real-time face verification
* Duplicate attendance prevention

### Attendance Management

* Student self-attendance through face scan
* Manual attendance correction by teachers
* Automatic absent marking for non-scanned students
* Attendance source tracking (Face Scan, Manual, Auto Absent)

### Analytics & Reports

* Attendance statistics dashboard
* Attendance percentage calculations
* Excel export using OpenPyXL
* PDF export using ReportLab
* Attendance history and filtering

### Administration

* Student management
* Teacher management
* Subject management
* Department management
* Face profile management
* Attendance settings management

## Technology Stack

### Backend

* Python
* Flask
* SQLAlchemy
* Flask-Login
* Flask-WTF

### Database

* MySQL

### Face Recognition

* OpenCV
* face_recognition
* dlib

### Frontend

* HTML
* CSS
* Bootstrap 5
* Jinja2

### Reporting

* OpenPyXL
* ReportLab

## Project Modules

* Admin Dashboard
* Teacher Dashboard
* Student Dashboard
* Face Registration
* Face Recognition Attendance
* Attendance Analytics
* Attendance Reports
* Auto Absent System

## Future Enhancements

* Live classroom attendance monitoring
* Multi-camera attendance support
* Email notifications
* Mobile application integration
* Cloud deployment
* Advanced attendance analytics

## Author

Anisha Salaskar

Bachelor of Science in Information Technology

Final Year Project
