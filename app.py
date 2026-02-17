from flask import Flask, render_template, request, redirect, session
import sqlite3
import os
from werkzeug.utils import secure_filename

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
            session["section"] = user["section"]
            session["username"] = user["username"]

            if user["role"] == "admin":
                return redirect("/admin")
            elif user["role"] == "coordinator":
                return redirect("/coordinator")
            elif user["role"] == "student":
                return redirect("/student")

        return "Invalid Credentials"

    return render_template("login.html")


# ---------------- REGISTER COORDINATOR ----------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db()
        conn.execute(
            "INSERT INTO users (username, password, role, approved) VALUES (?, ?, ?, ?)",
            (username, password, "coordinator", 0)
        )
        conn.commit()
        conn.close()

        return "Registration submitted. Wait for admin approval."

    return render_template("register.html")


# ---------------- REGISTER STUDENT ----------------
@app.route("/register_student", methods=["GET", "POST"])
def register_student():

    if request.method == "POST":
        roll = request.form["roll"]
        password = request.form["password"]
        name = request.form["name"]
        department = request.form["department"]

        conn = get_db()

        # username = roll
        conn.execute(
            "INSERT INTO users (username, password, role, approved) VALUES (?, ?, ?, ?)",
            (roll, password, "student", 0)
        )

        conn.execute(
            "INSERT INTO students (name, roll_no, department, semester, cgpa, attendance, section) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (name, roll, department, 0, 0.0, 0.0, None)   # ✅ FIXED
        )

        conn.commit()
        conn.close()

        return "Student registration submitted. Wait for admin approval."

    return render_template("register_student.html")


# ---------------- ADMIN DASHBOARD ----------------
@app.route("/admin")
def admin():

    if "role" not in session or session["role"] != "admin":
        return redirect("/")

    conn = get_db()

    students = conn.execute("SELECT * FROM students").fetchall()

    pending_coordinators = conn.execute(
        "SELECT * FROM users WHERE role='coordinator' AND approved=0"
    ).fetchall()

    pending_students = conn.execute(
        "SELECT * FROM users WHERE role='student' AND approved=0"
    ).fetchall()

    conn.close()

    return render_template("admin.html",
                           students=students,
                           pending=pending_coordinators,
                           pending_students=pending_students)


# ---------------- APPROVE COORDINATOR ----------------
@app.route("/approve_coordinator/<int:id>", methods=["POST"])
def approve_coordinator(id):

    if session["role"] != "admin":
        return redirect("/")

    section = request.form["section"]

    conn = get_db()
    conn.execute(
        "UPDATE users SET approved=1, section=? WHERE id=?",
        (section, id)
    )
    conn.commit()
    conn.close()

    return redirect("/admin")


# ---------------- APPROVE STUDENT ----------------
@app.route("/approve_student/<int:id>", methods=["POST"])
def approve_student(id):

    if session["role"] != "admin":
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

    if session["role"] != "coordinator":
        return redirect("/")

    section = session["section"]

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

    if session["role"] != "coordinator":
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
@app.route("/student", methods=["GET", "POST"])
def student():

    if session["role"] != "student":
        return redirect("/")

    conn = get_db()

    if request.method == "POST":
        file = request.files["certificate"]

        roll = session["username"]   # ✅ FIXED (no form roll)

        student_data = conn.execute(
            "SELECT name, section FROM students WHERE roll_no=?",
            (roll,)
        ).fetchone()

        if student_data and file:
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

            conn.execute(
                "INSERT INTO certificates (student_name, roll_no, section, file_name, status) VALUES (?, ?, ?, ?, ?)",
                (student_data["name"], roll, student_data["section"], filename, "Pending")
            )
            conn.commit()

    certificates = conn.execute(
        "SELECT * FROM certificates WHERE roll_no=?",
        (session["username"],)
    ).fetchall()

    conn.close()

    return render_template("student.html", certificates=certificates)


# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


if __name__ == "__main__":
    app.run(debug=True)
