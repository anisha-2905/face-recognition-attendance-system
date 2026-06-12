import base64
import json
import os
import uuid
from datetime import datetime

import cv2
import face_recognition
import numpy as np
from flask import current_app
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Attendance, Enrollment, FaceProfile, Student


FACE_MATCH_TOLERANCE = 0.5
MIN_REGISTRATION_IMAGES = 3


class FaceRegistrationError(ValueError):
    pass


def register_face(student_id, images=None, replace=False, camera_index=0, samples=5):
    """Register a student's face from uploaded browser frames or a local webcam."""
    student = Student.query.get_or_404(student_id)
    existing = FaceProfile.query.filter_by(student_id=student.id).first()
    if existing and not replace:
        raise FaceRegistrationError("Face data is already registered for this student.")

    frames = _frames_from_payload(images) if images else _capture_webcam_frames(camera_index, samples)
    if len(frames) < MIN_REGISTRATION_IMAGES:
        raise FaceRegistrationError(f"Capture at least {MIN_REGISTRATION_IMAGES} clear face images.")

    encodings = []
    stored_paths = []
    for frame in frames:
        face_locations = face_recognition.face_locations(frame)
        if not face_locations:
            raise FaceRegistrationError("One or more images do not contain a detectable face.")
        if len(face_locations) > 1:
            raise FaceRegistrationError("Registration images must contain only one face.")

        encoding = face_recognition.face_encodings(frame, face_locations)[0]
        encodings.append(encoding)
        stored_paths.append(_save_face_image(student.id, frame))

    averaged_encoding = np.mean(encodings, axis=0)
    _reject_duplicate_face(student.id, averaged_encoding)

    if existing is None:
        existing = FaceProfile(student_id=student.id, image_path=stored_paths[0], face_encoding="[]")
        db.session.add(existing)

    existing.image_path = stored_paths[0]
    existing.face_encoding = json.dumps(averaged_encoding.tolist())
    db.session.commit()
    return existing


def load_known_faces():
    known_faces = []
    profiles = FaceProfile.query.join(Student).all()
    for profile in profiles:
        try:
            encoding = np.array(json.loads(profile.face_encoding), dtype=np.float64)
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        known_faces.append(
            {
                "student_id": profile.student_id,
                "name": profile.student.user.name,
                "roll_number": profile.student.roll_number,
                "encoding": encoding,
            }
        )
    return known_faces


def recognize_face(frame):
    rgb_frame = _normalize_frame(frame)
    face_locations = face_recognition.face_locations(rgb_frame)
    if not face_locations:
        return {"matched": False, "reason": "No face detected.", "faces": []}

    known_faces = load_known_faces()
    if not known_faces:
        return {"matched": False, "reason": "No registered faces found.", "faces": []}

    known_encodings = [item["encoding"] for item in known_faces]
    results = []
    for location, encoding in zip(face_locations, face_recognition.face_encodings(rgb_frame, face_locations)):
        distances = face_recognition.face_distance(known_encodings, encoding)
        best_index = int(np.argmin(distances))
        best_distance = float(distances[best_index])
        confidence = max(0.0, min(1.0, 1.0 - best_distance))
        matched = best_distance <= FACE_MATCH_TOLERANCE
        known = known_faces[best_index] if matched else None
        results.append(
            {
                "matched": matched,
                "student_id": known["student_id"] if known else None,
                "name": known["name"] if known else "Unknown",
                "roll_number": known["roll_number"] if known else "",
                "confidence": round(confidence * 100, 2),
                "box": _box_to_dict(location),
            }
        )

    return {"matched": any(item["matched"] for item in results), "faces": results}


def recognize_student_face(student_id, frame):
    student = Student.query.get_or_404(student_id)
    profile = FaceProfile.query.filter_by(student_id=student.id).first()
    if not profile:
        raise FaceRegistrationError("Register your face before marking attendance.")

    rgb_frame = _normalize_frame(frame)
    face_locations = face_recognition.face_locations(rgb_frame)
    if not face_locations:
        return {"matched": False, "reason": "No face detected.", "faces": []}
    if len(face_locations) > 1:
        return {"matched": False, "reason": "Only one face should be visible during self attendance.", "faces": []}

    try:
        known_encoding = np.array(json.loads(profile.face_encoding), dtype=np.float64)
    except (TypeError, ValueError, json.JSONDecodeError):
        raise FaceRegistrationError("Registered face data is not readable. Please re-register your face.")

    encoding = face_recognition.face_encodings(rgb_frame, face_locations)[0]
    distance = float(face_recognition.face_distance([known_encoding], encoding)[0])
    confidence = max(0.0, min(1.0, 1.0 - distance))
    matched = distance <= FACE_MATCH_TOLERANCE
    return {
        "matched": matched,
        "reason": None if matched else "Face does not match the logged-in student.",
        "student_id": student.id if matched else None,
        "name": student.user.name if matched else "Unknown",
        "roll_number": student.roll_number if matched else "",
        "confidence": round(confidence * 100, 2),
        "faces": [
            {
                "matched": matched,
                "student_id": student.id if matched else None,
                "name": student.user.name if matched else "Unknown",
                "roll_number": student.roll_number if matched else "",
                "confidence": round(confidence * 100, 2),
                "box": _box_to_dict(face_locations[0]),
            }
        ],
    }


def mark_attendance(student_id, subject_id=None, teacher_id=None, confidence=None, captured_image=None):
    today = datetime.utcnow().date()

    if subject_id is None:
        enrollment = Enrollment.query.filter_by(student_id=student_id).first()
        subject_id = enrollment.subject_id if enrollment else None

    if subject_id is None:
        raise FaceRegistrationError("The recognized student is not enrolled in a subject.")

    if not Enrollment.query.filter_by(student_id=student_id, subject_id=subject_id).first():
        raise FaceRegistrationError("The recognized student is not enrolled in the selected subject.")

    existing_today = Attendance.query.filter_by(
        student_id=student_id,
        subject_id=subject_id,
        attendance_date=today,
    ).first()
    if existing_today:
        return existing_today, False

    attendance = Attendance(
        student_id=student_id,
        subject_id=subject_id,
        marked_by_teacher_id=teacher_id,
        attendance_date=today,
        status="present",
        captured_image=captured_image,
        confidence=confidence,
        method="face_recognition",
        attendance_source="face_scan",
        remarks="Automatically marked by face recognition.",
    )
    db.session.add(attendance)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return Attendance.query.filter_by(
            student_id=student_id,
            subject_id=subject_id,
            attendance_date=today,
        ).first(), False
    return attendance, True


def decode_image_data(image_data):
    return _decode_data_url(image_data)


def _frames_from_payload(images):
    frames = []
    for image_data in images or []:
        frames.append(_decode_data_url(image_data))
    return frames


def _capture_webcam_frames(camera_index, samples):
    capture = cv2.VideoCapture(camera_index)
    if not capture.isOpened():
        raise FaceRegistrationError("Unable to access the webcam.")

    frames = []
    try:
        while len(frames) < samples:
            ok, frame = capture.read()
            if ok:
                frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    finally:
        capture.release()
    return frames


def _decode_data_url(image_data):
    if "," in image_data:
        image_data = image_data.split(",", 1)[1]
    raw = base64.b64decode(image_data)
    buffer = np.frombuffer(raw, dtype=np.uint8)
    frame = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    if frame is None:
        raise FaceRegistrationError("Unable to read one of the submitted images.")
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)


def _normalize_frame(frame):
    if isinstance(frame, str):
        return _decode_data_url(frame)
    if frame.ndim == 3 and frame.shape[2] == 3:
        return frame
    raise FaceRegistrationError("Invalid camera frame.")


def _save_face_image(student_id, rgb_frame):
    upload_dir = os.path.join(current_app.root_path, "static", "uploads", "faces")
    os.makedirs(upload_dir, exist_ok=True)
    filename = f"student_{student_id}_{uuid.uuid4().hex}.jpg"
    path = os.path.join(upload_dir, filename)
    cv2.imwrite(path, cv2.cvtColor(rgb_frame, cv2.COLOR_RGB2BGR))
    return f"uploads/faces/{filename}"


def _reject_duplicate_face(student_id, new_encoding):
    for known in load_known_faces():
        if known["student_id"] == student_id:
            continue
        distance = face_recognition.face_distance([known["encoding"]], new_encoding)[0]
        if distance <= FACE_MATCH_TOLERANCE:
            raise FaceRegistrationError(
                f"This face is already registered to {known['name']} ({known['roll_number']})."
            )


def _box_to_dict(location):
    top, right, bottom, left = location
    return {"top": top, "right": right, "bottom": bottom, "left": left}
