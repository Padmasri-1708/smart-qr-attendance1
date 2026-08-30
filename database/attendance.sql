CREATE TABLE attendance (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT,
    attendance_date DATE,
    attendance_time TIME,
    status VARCHAR(20),
    FOREIGN KEY (student_id) REFERENCES students(id)
);