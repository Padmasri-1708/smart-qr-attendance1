CREATE TABLE students (
    id INT AUTO_INCREMENT PRIMARY KEY,
    roll_no VARCHAR(20) UNIQUE,
    name VARCHAR(100),
    username VARCHAR(50) UNIQUE,
    password VARCHAR(100),
    department VARCHAR(50),
    year VARCHAR(10)
);