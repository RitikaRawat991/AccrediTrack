from flask import Flask, render_template, request, redirect, session
import sqlite3
import os
from werkzeug.utils import secure_filename
from flask import send_from_directory


app = Flask(__name__)
app.secret_key = "naac_secret"

UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


# ---------------- DATABASE ----------------
def get_db():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
# ---------------- LOGIN ----------------
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE username=? AND password=?",
            (username, password)
        ).fetchone()
        conn.close()

        if user:

            if user["role"] != "admin" and user["approved"] == 0:
                return "Account not approved by admin yet."

            session["role"] = user["role"]
            session["username"] = user["username"]
            session["section"] = user["section"]

            if user["role"] == "admin":
                return redirect("/admin")
            elif user["role"] == "coordinator":
                return redirect("/coordinator")
            elif user["role"] == "student":
                return redirect("/student")

        return "Invalid Credentials"

    return render_template("login.html")


# ---------------- REGISTER STUDENT ----------------
@app.route("/register_student", methods=["GET", "POST"])
def register_student():

    if request.method == "POST":
        roll = request.form["roll"]
        password = request.form["password"]
        name = request.form["name"]
        department = request.form["department"]

        conn = get_db()

        conn.execute(
            "INSERT INTO users (username, password, role, approved) VALUES (?, ?, ?, ?)",
            (roll, password, "student", 0)
        )

        conn.execute(
            "INSERT INTO students (name, roll_no, department, semester, cgpa, attendance, section) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (name, roll, department, 0, 0.0, 0.0, None)
        )

        conn.commit()
        conn.close()

        return "Registration submitted. Wait for admin approval."

    return render_template("register_student.html")


# ---------------- REGISTER COORDINATOR ----------------
@app.route("/register", methods=["GET", "POST"])
def register():
    return render_template("register_coordinator.html")

@app.route("/register_coordinator", methods=["GET", "POST"])
def register_coordinator():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        section  = request.form["section"]

        conn = get_db()
        conn.execute(
            "INSERT INTO users (username, password, role, section, approved) VALUES (?, ?, ?, ?, ?)",
            (username, password, "coordinator", section, 0)
        )
        conn.commit()
        conn.close()

        return redirect("/")

    return render_template("register_coordinator.html")

# ---------------- ADMIN DASHBOARD ----------------
@app.route("/admin")
def admin():

    if session.get("role") != "admin":
        return redirect("/")

    conn = get_db()

    students = conn.execute("SELECT * FROM students").fetchall()

    pending_students = conn.execute(
        "SELECT * FROM users WHERE role='student' AND approved=0"
    ).fetchall()

    conn.close()

    return render_template("admin.html",
                           students=students,
                           pending_students=pending_students)


# ---------------- APPROVE STUDENT ----------------
@app.route("/approve_student/<int:id>", methods=["POST"])
def approve_student(id):

    if session.get("role") != "admin":
        return redirect("/")

    section = request.form["section"]

    conn = get_db()

    user = conn.execute(
        "SELECT username FROM users WHERE id=?",
        (id,)
    ).fetchone()

    if not user:
        conn.close()
        return "User not found"

    roll = user["username"]

    conn.execute(
        "UPDATE users SET approved=1, section=? WHERE id=?",
        (section, id)
    )

    conn.execute(
        "UPDATE students SET section=? WHERE roll_no=?",
        (section, roll)
    )

    conn.commit()
    conn.close()

    return redirect("/admin")


# ---------------- COORDINATOR DASHBOARD ----------------
@app.route("/coordinator")
def coordinator():

    if session.get("role") != "coordinator":
        return redirect("/")

    section = session.get("section")

    conn = get_db()

    students = conn.execute(
        "SELECT * FROM students WHERE section=?",
        (section,)
    ).fetchall()

    certificates = conn.execute(
        "SELECT * FROM certificates WHERE section=?",
        (section,)
    ).fetchall()

    conn.close()

    return render_template("coordinator.html",
                           students=students,
                           certificates=certificates)


# ---------------- UPDATE STUDENT ----------------
@app.route("/update_student/<int:id>", methods=["POST"])
def update_student(id):

    if session.get("role") != "coordinator":
        return redirect("/")

    semester = request.form["semester"]
    cgpa = request.form["cgpa"]
    attendance = request.form["attendance"]

    conn = get_db()
    conn.execute(
        "UPDATE students SET semester=?, cgpa=?, attendance=? WHERE id=?",
        (semester, cgpa, attendance, id)
    )
    conn.commit()
    conn.close()

    return redirect("/coordinator")


# ---------------- STUDENT DASHBOARD ----------------
# ---------------- STUDENT DASHBOARD (PORTFOLIO) ----------------
@app.route("/student", methods=["GET", "POST"])
def student():

    if session.get("role") != "student":
        return redirect("/")

    conn = get_db()
    roll = session.get("username")

    student_data = conn.execute(
        "SELECT * FROM students WHERE roll_no=?",
        (roll,)
    ).fetchone()

    if request.method == "POST":

        # ---------- PROFILE PHOTO ----------
        if "profile_pic" in request.files:
            photo = request.files["profile_pic"]
            if photo and photo.filename != "":
                filename = secure_filename(photo.filename)
                photo.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

                conn.execute(
                    "UPDATE students SET profile_pic=? WHERE roll_no=?",
                    (filename, roll)
                )
                conn.commit()

        # ---------- CERTIFICATE ----------
        if "certificate" in request.files:
            file = request.files["certificate"]

            if student_data and student_data["section"] and file and file.filename != "":
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

                conn.execute(
                    "INSERT INTO certificates (student_name, roll_no, section, file_name, status) VALUES (?, ?, ?, ?, ?)",
                    (student_data["name"], roll, student_data["section"], filename, "Pending")
                )
                conn.commit()

        # ---------- ACHIEVEMENTS ----------
        if "achievements" in request.form:
            achievements = request.form["achievements"]

            conn.execute(
                "UPDATE students SET achievements=? WHERE roll_no=?",
                (achievements, roll)
            )
            conn.commit()

    certificates = conn.execute(
        "SELECT * FROM certificates WHERE roll_no=?",
        (roll,)
    ).fetchall()

    conn.close()

    return render_template(
        "student.html",
        student=student_data,
        certificates=certificates,
        university="Graphic Era Hill University"
    )


# ---------------- APPROVE CERTIFICATE ----------------
@app.route("/approve/<int:id>")
def approve(id):

    if session.get("role") != "coordinator":
        return redirect("/")

    conn = get_db()
    conn.execute("UPDATE certificates SET status='Approved' WHERE id=?", (id,))
    conn.commit()
    conn.close()

    return redirect("/coordinator")


# ---------------- REJECT CERTIFICATE ----------------
@app.route("/reject/<int:id>")
def reject(id):

    if session.get("role") != "coordinator":
        return redirect("/")

    conn = get_db()
    conn.execute("UPDATE certificates SET status='Rejected' WHERE id=?", (id,))
    conn.commit()
    conn.close()

    return redirect("/coordinator")


# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


if __name__ == "__main__":
    app.run(debug=True)