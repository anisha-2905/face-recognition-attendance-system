ALTER TABLE face_profiles
  CHANGE COLUMN encoding_json face_encoding TEXT NOT NULL;

ALTER TABLE attendance
  ADD COLUMN attendance_source VARCHAR(50) NOT NULL DEFAULT 'manual' AFTER method;
