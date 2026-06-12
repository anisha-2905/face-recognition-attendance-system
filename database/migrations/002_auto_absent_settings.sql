ALTER TABLE attendance
  MODIFY method ENUM('face', 'manual', 'face_recognition', 'system') NOT NULL DEFAULT 'face_recognition';

CREATE TABLE IF NOT EXISTS attendance_settings (
  id INT AUTO_INCREMENT PRIMARY KEY,
  start_time TIME NOT NULL DEFAULT '09:00:00',
  end_time TIME NOT NULL DEFAULT '17:00:00',
  auto_absent_enabled BOOLEAN NOT NULL DEFAULT TRUE,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO attendance_settings (id, start_time, end_time, auto_absent_enabled)
SELECT 1, '09:00:00', '17:00:00', TRUE
WHERE NOT EXISTS (SELECT 1 FROM attendance_settings);
