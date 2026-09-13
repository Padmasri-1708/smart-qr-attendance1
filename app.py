import os

from flask import Flask, render_template, request, redirect, session
import mysql.connector

from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

from math import radians, sin, cos, sqrt, atan2


app = Flask(__name__)

app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY",
    "smart_qr_attendance_secret"
)


# =====================================================
# INDIA TIMEZONE
# =====================================================

INDIA_TZ = ZoneInfo("Asia/Kolkata")


# =====================================================
# AIVEN MYSQL CONNECTION
# =====================================================

def get_db():
    """
    Create a fresh MySQL connection.

    Aiven MySQL requires SSL.
    """

    return mysql.connector.connect(
        host=os.environ.get("AIVEN_HOST"),
        port=int(os.environ.get("AIVEN_PORT", "20098")),
        user=os.environ.get("AIVEN_USER"),
        password=os.environ.get("AIVEN_PASSWORD"),
        database="attendance_db",

        # Aiven requires SSL
        ssl_disabled=False
    )


# =====================================================
# HOME / ADMIN LOGIN PAGE
# =====================================================

@app.route("/")
def home():

    return render_template(
        "admin_login.html"
    )


# =====================================================
# ADMIN LOGIN
# =====================================================

@app.route("/admin_login", methods=["POST"])
def admin_login():

    username = request.form["username"]
    password = request.form["password"]

    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:

        cursor.execute(
            """
            SELECT *
            FROM admin
            WHERE username=%s
            AND password=%s
            """,
            (
                username,
                password
            )
        )

        admin = cursor.fetchone()

    finally:

        cursor.close()
        db.close()

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

    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:

        # TOTAL STUDENTS
        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM students
            """
        )

        total_students = cursor.fetchone()["total"]


        # =================================================
        # INDIA TODAY
        # =================================================

        india_now = datetime.now(
            timezone.utc
        ).astimezone(
            INDIA_TZ
        )

        today = india_now.date()


        # =================================================
        # PRESENT TODAY
        # =================================================

        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM attendance
            WHERE attendance_date=%s
            """,
            (
                today,
            )
        )

        present_today = cursor.fetchone()["total"]


        # ABSENT TODAY
        absent_today = (
            total_students -
            present_today
        )


        # =================================================
        # PRESENT STUDENTS TODAY
        # =================================================

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
            ON attendance.student_id=students.id

            WHERE attendance.attendance_date=%s

            ORDER BY attendance.attendance_time DESC
            """,
            (
                today,
            )
        )

        records = cursor.fetchall()


        # =================================================
        # ABSENT STUDENTS TODAY
        # =================================================

        cursor.execute(
            """
            SELECT
                students.roll_no,
                students.name,
                students.department,
                students.year

            FROM students

            LEFT JOIN attendance
            ON students.id=attendance.student_id
            AND attendance.attendance_date=%s

            WHERE attendance.student_id IS NULL

            ORDER BY students.roll_no ASC
            """,
            (
                today,
            )
        )

        absent_students = cursor.fetchall()

    finally:

        cursor.close()
        db.close()


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

    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:

        cursor.execute(
            """
            SELECT
                id,
                roll_no,
                name,
                username,
                department,
                year,
                device_name,
                device_id

            FROM students

            ORDER BY roll_no ASC
            """
        )

        students_list = cursor.fetchall()

    finally:

        cursor.close()
        db.close()


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


    db = get_db()
    cursor = db.cursor()

    try:

        cursor.execute(
            """
            INSERT INTO students
            (
                roll_no,
                name,
                username,
                password,
                department,
                year,
                device_name,
                device_id
            )

            VALUES
            (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                NULL,
                NULL
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

    finally:

        cursor.close()
        db.close()


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


    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:

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

    finally:

        cursor.close()
        db.close()


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


    now = datetime.now(
        timezone.utc
    ).astimezone(
        INDIA_TZ
    )


    qr_data = (
        "https://smart-qr-attendance1-3.onrender.com"
        "/scan_qr"
    )


    return render_template(
        "qr_display.html",

        qr_data=qr_data,

        date=now.strftime(
            "%d-%m-%Y"
        ),

        time=now.strftime(
            "%I:%M %p"
        )
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

@app.route(
    "/mark_attendance",
    methods=["POST"]
)
def mark_attendance():

    # =================================================
    # STUDENT LOGIN CHECK
    # =================================================

    if "student_id" not in session:

        return {
            "success": False,
            "message": "Student login required!"
        }, 401


    # =================================================
    # GET JSON DATA
    # =================================================

    data = request.get_json()


    if not data:

        return {
            "success": False,
            "message": "Location data not received!"
        }, 400


    latitude = data.get("latitude")

    longitude = data.get("longitude")

    device_id = data.get("device_id")

    device_name = data.get(
        "device_name",
        "Unknown Device"
    )


    # =================================================
    # DEVICE ID CHECK
    # =================================================

    if not device_id:

        return {
            "success": False,
            "message": "Device ID not received!"
        }, 400


    # =================================================
    # CLEAN DEVICE NAME
    # =================================================

    if not isinstance(
        device_name,
        str
    ):

        device_name = "Unknown Device"


    device_name = device_name.strip()


    if not device_name:

        device_name = "Unknown Device"


    # Limit device name length
    device_name = device_name[:100]


    # =================================================
    # LOCATION CHECK
    # =================================================

    if (
        latitude is None
        or longitude is None
    ):

        return {
            "success": False,
            "message": "Location not received!"
        }, 400


    # =================================================
    # CURRENT INDIA DATE AND TIME
    # =================================================

    now = datetime.now(
        timezone.utc
    ).astimezone(
        INDIA_TZ
    )


    current_date = now.date()

    current_time = now.time()


    display_date = now.strftime(
        "%d-%m-%Y"
    )


    display_time = now.strftime(
        "%I:%M %p"
    )


    # =================================================
    # ATTENDANCE TIME
    # 8:10 AM TO 11:00 PM
    # =================================================

    class_start = time(
        8,
        10
    )

    class_end = time(
        23,
        0
    )


    if not (
        class_start
        <= current_time
        <= class_end
    ):

        return {
            "success": False,
            "message":
                "Attendance time has expired!"
        }


    # =================================================
    # COLLEGE LOCATION
    # =================================================

    COLLEGE_LAT = 12.554062

    COLLEGE_LON = 78.021858

    ALLOWED_RADIUS = 200


    # =================================================
    # DISTANCE CALCULATION
    # =================================================

    R = 6371000


    try:

        lat1 = radians(
            COLLEGE_LAT
        )

        lat2 = radians(
            float(latitude)
        )


        delta_lat = radians(
            float(latitude)
            -
            COLLEGE_LAT
        )


        delta_lon = radians(
            float(longitude)
            -
            COLLEGE_LON
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


    except (
        TypeError,
        ValueError
    ):

        return {
            "success": False,
            "message":
                "Invalid location data!"
        }, 400


    # =================================================
    # LOCATION VALIDATION
    # =================================================

    if distance > ALLOWED_RADIUS:

        return {
            "success": False,

            "message":
                "You are outside the college location!",

            "distance":
                distance
        }


    # =================================================
    # STUDENT ID
    # =================================================

    student_id = session[
        "student_id"
    ]


    # =================================================
    # DATABASE CONNECTION
    # =================================================

    db = None
    cursor = None


    try:

        db = get_db()

        cursor = db.cursor(
            dictionary=True
        )


        # =================================================
        # GET STUDENT DEVICE DETAILS
        # =================================================

        cursor.execute(
            """
            SELECT
                device_id,
                device_name

            FROM students

            WHERE id=%s
            """,
            (
                student_id,
            )
        )


        student_device = cursor.fetchone()


        # =================================================
        # STUDENT NOT FOUND
        # =================================================

        if not student_device:

            return {
                "success": False,
                "message":
                    "Student not found!"
            }


        registered_device_id = (
            student_device["device_id"]
        )

        registered_device_name = (
            student_device["device_name"]
        )


        # =================================================
        # FIRST DEVICE BINDING
        # =================================================

        if registered_device_id is None:

            cursor.execute(
                """
                UPDATE students

                SET
                    device_id=%s,
                    device_name=%s

                WHERE id=%s
                """,
                (
                    device_id,
                    device_name,
                    student_id
                )
            )

            db.commit()


        # =================================================
        # SAME DEVICE
        # =================================================

        elif registered_device_id == device_id:

            # Update device name if it changed
            if (
                device_name != "Unknown Device"
                and device_name != registered_device_name
            ):

                cursor.execute(
                    """
                    UPDATE students

                    SET device_name=%s

                    WHERE id=%s
                    """,
                    (
                        device_name,
                        student_id
                    )
                )

                db.commit()


        # =================================================
        # DIFFERENT DEVICE
        # =================================================

        else:

            return {
                "success": False,

                "message":
                    "This student is already registered with another device."
            }


        # =================================================
        # CHECK ALREADY ATTENDED TODAY
        # =================================================

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


        # =================================================
        # ALREADY ATTENDED
        # =================================================

        if existing:

            return {
                "success": False,

                "message":
                    "Attendance already marked today!",

                "distance":
                    distance,

                "time":
                    display_time
            }


        # =================================================
        # INSERT ATTENDANCE
        # =================================================

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


    except mysql.connector.Error as e:

        if db:
            db.rollback()

        print(
            "DATABASE ERROR:",
            e
        )

        return {
            "success": False,

            "message":
                "Database error. Please try again."
        }, 500


    finally:

        if cursor:
            cursor.close()

        if db:
            db.close()


    # =================================================
    # SUCCESS RESPONSE
    # =================================================

    return {

        "success": True,

        "message":
            "Attendance marked successfully!",

        "date":
            display_date,

        "time":
            display_time,

        "distance":
            distance,

        "device_name":
            device_name
    }


# =====================================================
# VIEW ALL ATTENDANCE
# =====================================================

@app.route("/attendance")
def attendance():

    if "admin_logged_in" not in session:
        return redirect("/")


    db = get_db()
    cursor = db.cursor(
        dictionary=True
    )


    try:

        cursor.execute(
            """
            SELECT

                attendance.id,

                students.roll_no,

                students.name,

                students.department,

                students.year,

                students.device_name,

                students.device_id,

                attendance.attendance_date,

                attendance.attendance_time,

                attendance.status

            FROM attendance

            JOIN students

            ON attendance.student_id=students.id

            ORDER BY

                attendance.attendance_date DESC,

                attendance.attendance_time DESC
            """
        )


        records = cursor.fetchall()

    finally:

        cursor.close()
        db.close()


    return render_template(
        "attendance.html",
        records=records
    )


# =====================================================
# TIME TEST
# =====================================================

@app.route("/time_test")
def time_test():

    utc_now = datetime.now(
        timezone.utc
    )


    india_now = utc_now.astimezone(
        INDIA_TZ
    )


    return {

        "UTC":
            utc_now.strftime(
                "%d-%m-%Y %I:%M:%S %p"
            ),

        "INDIA_TIME":
            india_now.strftime(
                "%d-%m-%Y %I:%M:%S %p"
            ),

        "TIMEZONE":
            str(
                india_now.tzinfo
            ),

        "UTC_OFFSET":
            str(
                india_now.utcoffset()
            )
    }


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

        port=int(
            os.environ.get(
                "PORT",
                5000
            )
        ),

        debug=False
    )