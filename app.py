import os
from flask import Flask, render_template, request, redirect, session
import mysql.connector
from datetime import datetime, time
from zoneinfo import ZoneInfo
from math import radians, sin, cos, sqrt, atan2


app = Flask(__name__)

app.secret_key = "smart_qr_attendance_secret"


# =====================================================
# AIVEN MYSQL CONNECTION
# =====================================================
import os

# AIVEN MYSQL CONNECTION

db = mysql.connector.connect(
    host=os.environ.get("AIVEN_HOST"),
    port=int(os.environ.get("AIVEN_PORT", "20098")),
    user=os.environ.get("AIVEN_USER"),
    password=os.environ.get("AIVEN_PASSWORD"),
    database="attendance_db"
)


# =====================================================
# HOME / ADMIN LOGIN PAGE
# =====================================================

@app.route("/")
def home():

    return render_template("admin_login.html")


# =====================================================
# ADMIN LOGIN
# =====================================================

@app.route("/admin_login", methods=["POST"])
def admin_login():

    username = request.form["username"]
    password = request.form["password"]

    cursor = db.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT *
        FROM admin
        WHERE username=%s AND password=%s
        """,
        (username, password)
    )

    admin = cursor.fetchone()

    cursor.close()

    if admin:

        session["admin_logged_in"] = True
        session["admin_username"] = username

        return redirect("/dashboard")

    return render_template(
        "admin_login.html",
        error="Invalid Username or Password!"
    )


# =====================================================
# ADMIN DASHBOARD
# =====================================================

@app.route("/dashboard")
def dashboard():

    if "admin_logged_in" not in session:
        return redirect("/")

    cursor = db.cursor(dictionary=True)

    # TOTAL STUDENTS
    cursor.execute(
        """
        SELECT COUNT(*) AS total
        FROM students
        """
    )

    total_students = cursor.fetchone()["total"]


    # PRESENT TODAY
    cursor.execute(
        """
        SELECT COUNT(*) AS total
        FROM attendance
        WHERE attendance_date = CURDATE()
        """
    )

    present_today = cursor.fetchone()["total"]


    # ABSENT TODAY
    absent_today = total_students - present_today


    # PRESENT STUDENTS TODAY
    cursor.execute(
        """
        SELECT
            attendance.id,
            students.roll_no,
            students.name,
            students.department,
            students.year,
            attendance.attendance_date,
            attendance.attendance_time,
            attendance.status

        FROM attendance

        JOIN students
        ON attendance.student_id = students.id

        WHERE attendance.attendance_date = CURDATE()

        ORDER BY attendance.attendance_time DESC
        """
    )

    records = cursor.fetchall()


    # ABSENT STUDENTS TODAY
    cursor.execute(
        """
        SELECT
            students.roll_no,
            students.name,
            students.department,
            students.year

        FROM students

        LEFT JOIN attendance
        ON students.id = attendance.student_id
        AND attendance.attendance_date = CURDATE()

        WHERE attendance.student_id IS NULL

        ORDER BY students.roll_no ASC
        """
    )

    absent_students = cursor.fetchall()

    cursor.close()


    return render_template(
        "dashboard.html",
        total_students=total_students,
        present_today=present_today,
        absent_today=absent_today,
        records=records,
        absent_students=absent_students
    )


# =====================================================
# VIEW REGISTERED STUDENTS
# =====================================================

@app.route("/students")
def students():

    if "admin_logged_in" not in session:
        return redirect("/")

    cursor = db.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            id,
            roll_no,
            name,
            username,
            department,
            year

        FROM students

        ORDER BY roll_no ASC
        """
    )

    students_list = cursor.fetchall()

    cursor.close()

    return render_template(
        "students.html",
        students=students_list
    )


# =====================================================
# STUDENT REGISTRATION PAGE
# =====================================================

@app.route("/register")
def register():

    if "admin_logged_in" not in session:
        return redirect("/")

    return render_template(
        "register_student.html"
    )


# =====================================================
# STUDENT REGISTRATION
# =====================================================

@app.route("/register_student", methods=["POST"])
def register_student():

    if "admin_logged_in" not in session:
        return redirect("/")

    roll_no = request.form["roll_no"]
    name = request.form["name"]
    username = request.form["username"]
    password = request.form["password"]
    department = request.form["department"]
    year = request.form["year"]

    cursor = db.cursor()

    cursor.execute(
        """
        INSERT INTO students
        (
            roll_no,
            name,
            username,
            password,
            department,
            year
        )

        VALUES
        (
            %s,
            %s,
            %s,
            %s,
            %s,
            %s
        )
        """,
        (
            roll_no,
            name,
            username,
            password,
            department,
            year
        )
    )

    db.commit()

    cursor.close()

    return "Student Registered Successfully!"


# =====================================================
# STUDENT LOGIN PAGE
# =====================================================

@app.route("/student")
def student():

    return render_template(
        "student_login.html"
    )


# =====================================================
# STUDENT LOGIN
# =====================================================

@app.route("/student_login", methods=["POST"])
def student_login():

    username = request.form["username"]
    password = request.form["password"]

    cursor = db.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT *
        FROM students
        WHERE username=%s
        AND password=%s
        """,
        (
            username,
            password
        )
    )

    student_data = cursor.fetchone()

    cursor.close()

    if student_data:

        session["student_id"] = student_data["id"]
        session["student_name"] = student_data["name"]
        session["roll_no"] = student_data["roll_no"]

        return redirect("/scan_qr")

    return render_template(
        "student_login.html",
        error="Invalid Username or Password!"
    )


# =====================================================
# GENERATE QR
# =====================================================

@app.route("/generate_qr")
def generate_qr():

    if "admin_logged_in" not in session:
        return redirect("/")

    now = datetime.now()

    qr_data = "https://smart-qr-attendance1-3.onrender.com/scan_qr"

    return render_template(
        "qr_display.html",
        qr_data=qr_data,
        date=now.strftime("%d-%m-%Y"),
        time=now.strftime("%I:%M %p")
    )


# =====================================================
# SCAN QR PAGE
# =====================================================

@app.route("/scan_qr")
def scan_qr():

    if "student_id" not in session:
        return redirect("/student")

    student_name = session["student_name"]

    return render_template(
        "scan_qr.html",
        student_name=student_name
    )


# =====================================================
# MARK ATTENDANCE
# =====================================================

@app.route("/mark_attendance", methods=["POST"])
def mark_attendance():

    if "student_id" not in session:

        return {
            "success": False,
            "message": "Student login required!"
        }, 401


    data = request.get_json()

    if not data:

        return {
            "success": False,
            "message": "Location data not received!"
        }


    latitude = data.get("latitude")
    longitude = data.get("longitude")


    if latitude is None or longitude is None:

        return {
            "success": False,
            "message": "Location not received!"
        }


    # CURRENT DATE AND TIME

    now = datetime.now(ZoneInfo("Asia/Kolkatha"))

    current_date = now.strftime("%d-%m-%Y")
    current_time = now.strftime("%I:%M %p")


    # ATTENDANCE TIME
    # 8:10 AM TO 11:00 PM

    class_start = time(8, 10)
    class_end = time(23, 0)


    if not (
        class_start
        <= current_time
        <= class_end
    ):

        return {
            "success": False,
            "message": "Attendance time has expired!"
        }


    # COLLEGE LOCATION

    COLLEGE_LAT = 12.671705
    COLLEGE_LON = 77.965916

    ALLOWED_RADIUS = 200


    # DISTANCE CALCULATION

    R = 6371000

    lat1 = radians(COLLEGE_LAT)
    lat2 = radians(float(latitude))

    delta_lat = radians(
        float(latitude) - COLLEGE_LAT
    )

    delta_lon = radians(
        float(longitude) - COLLEGE_LON
    )

    a = (
        sin(delta_lat / 2) ** 2
        +
        cos(lat1)
        *
        cos(lat2)
        *
        sin(delta_lon / 2) ** 2
    )

    c = 2 * atan2(
        sqrt(a),
        sqrt(1 - a)
    )

    distance = R * c

    distance = round(
        distance,
        2
    )


    # LOCATION VALIDATION

    if distance > ALLOWED_RADIUS:

        return {
            "success": False,
            "message":
                "You are outside the college location!",
            "distance": distance
        }


    # DATABASE

    student_id = session["student_id"]

    cursor = db.cursor(
        dictionary=True
    )


    # CHECK ALREADY ATTENDED

    cursor.execute(
        """
        SELECT *
        FROM attendance
        WHERE student_id=%s
        AND attendance_date=%s
        """,
        (
            student_id,
            current_date
        )
    )

    existing = cursor.fetchone()


    if existing:

        cursor.close()

        return {
            "success": False,
            "message":
                "Attendance already marked today!",
            "distance": distance
        }


    # INSERT ATTENDANCE

    cursor.execute(
        """
        INSERT INTO attendance
        (
            student_id,
            attendance_date,
            attendance_time,
            status
        )

        VALUES
        (
            %s,
            %s,
            %s,
            %s
        )
        """,
        (
            student_id,
            current_date,
            current_time,
            "Present"
        )
    )

    db.commit()

    cursor.close()


    return {
        "success": True,
        "message":
            "Attendance marked successfully!",
        "distance": distance
    }


# =====================================================
# VIEW ALL ATTENDANCE
# =====================================================

@app.route("/attendance")
def attendance():

    if "admin_logged_in" not in session:
        return redirect("/")

    cursor = db.cursor(
        dictionary=True
    )

    cursor.execute(
        """
        SELECT

            attendance.id,

            students.roll_no,
            students.name,
            students.department,
            students.year,

            attendance.attendance_date,
            attendance.attendance_time,
            attendance.status

        FROM attendance

        JOIN students
        ON attendance.student_id = students.id

        ORDER BY
            attendance.attendance_date DESC,
            attendance.attendance_time DESC
        """
    )

    records = cursor.fetchall()

    cursor.close()

    return render_template(
        "attendance.html",
        records=records
    )


# =====================================================
# LOGOUT
# =====================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/")


# =====================================================
# RUN FLASK
# =====================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )

