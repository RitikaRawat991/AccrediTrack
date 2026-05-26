from flask import Flask, render_template, request, redirect, session, flash, get_flashed_messages
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

def get_db():
    conn = sqlite3.connect("database.db", timeout=10)
    conn.row_factory = sqlite3.Row

    conn.execute(
        "CREATE TABLE IF NOT EXISTS coordinators ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "name TEXT,"
        "username TEXT UNIQUE,"
        "department TEXT,"
        "section TEXT"
        ")"
    )

    conn.execute(
        "CREATE TABLE IF NOT EXISTS certificates ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "student_name TEXT,"
        "roll_no TEXT,"
        "section TEXT,"
        "category TEXT,"
        "file_name TEXT,"
        "status TEXT"
        ")"
    )

    # If certificates existed earlier, ensure category column is present.
    try:
        conn.execute("ALTER TABLE certificates ADD COLUMN category TEXT")
    except sqlite3.OperationalError:
        pass

    conn.commit()
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

    messages = get_flashed_messages(with_categories=True)
    return render_template("login.html", messages=messages)

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
        return redirect("/")

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
        name = request.form["name"]
        department = request.form["department"]

        conn = get_db()
        conn.execute(
            "INSERT INTO users (username, password, role, approved) VALUES (?, ?, ?, ?)",
            (username, password, "coordinator", 0)
        )
        conn.execute(
            "INSERT INTO coordinators (name, username, department) VALUES (?, ?, ?)",
            (name, username, department)
        )
        conn.commit()
        conn.close()
        flash('Registration submitted. Wait for admin approval.', 'success')
        return redirect('/')

    return render_template("register_coordinator.html")

@app.route("/admin")
def admin():
    if session.get("role") != "admin":
        return redirect("/")

    conn = get_db()
    students = conn.execute("SELECT * FROM students ").fetchall()
    pending_students = conn.execute(
        "SELECT * FROM users WHERE role='student' AND approved=0"
    ).fetchall()
    pending_coordinators = conn.execute(
        "SELECT * FROM users WHERE role='coordinator' AND approved=0"
    ).fetchall()

    # Category graph (only approved)
    category_counts = conn.execute(
        "SELECT category, COUNT(*) as count FROM certificates WHERE status='Approved' GROUP BY category ORDER BY count DESC"
    ).fetchall()

    conn.close()

    return render_template(
        "admin.html",
        students=students,
        pending_students=pending_students,
        pending=pending_coordinators,
        category_counts=category_counts,
    )



@app.route("/approve_coordinator/<int:id>", methods=["POST"])
def approve_coordinator(id):
    if session.get("role") != "admin":
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

@app.route("/reject_coordinator/<int:id>")
def reject_coordinator(id):
    if session.get("role") != "admin":
        return redirect("/")

    conn = get_db()
    conn.execute("DELETE FROM users WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect("/admin")


# ---------------- APPROVE STUDENT ----------------
@app.route("/approve_student/<int:id>", methods=["POST"])
def approve_student(id):
    if session.get("role") != "admin":
        return redirect("/")

    section = request.form["section"]
    conn = get_db()
    user = conn.execute("SELECT username FROM users WHERE id=?", (id,)).fetchone()

    if not user:
        conn.close()
        return "User not found"

    roll = user["username"]
    conn.execute("UPDATE users SET approved=1, section=? WHERE id=?", (section, id))
    conn.execute("UPDATE students SET section=? WHERE roll_no=?", (section, roll))
    conn.commit()
    conn.close()
    return redirect("/admin")


@app.route("/reject_student/<int:id>")
def reject_student(id):
    if session.get("role") != "admin":
        return redirect("/")

    conn = get_db()
    user = conn.execute("SELECT username FROM users WHERE id=?", (id,)).fetchone()
    if user:
        conn.execute("DELETE FROM students WHERE roll_no=?", (user["username"],))
    conn.execute("DELETE FROM users WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect("/admin")

@app.route("/coordinator")
def coordinator():
    if session.get("role") != "coordinator":
        return redirect("/")
    section = session.get("section")

    category = request.args.get("category", "")

    conn = get_db()
    students = conn.execute("SELECT * FROM students WHERE section=?", (section,)).fetchall()

    if category:
        certificates = conn.execute(
            "SELECT * FROM certificates WHERE section=? AND category=?",
            (section, category)
        ).fetchall()
    else:
        certificates = conn.execute(
            "SELECT * FROM certificates WHERE section=?",
            (section,)
        ).fetchall()

    conn.close()

    return render_template("coordinator.html", students=students, certificates=certificates)

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

@app.route("/student", methods=["GET", "POST"])
def student():
    if session.get("role") != "student":
        return redirect("/")

    conn = get_db()
    roll = session.get("username")
    student_data = conn.execute("SELECT * FROM students WHERE roll_no=?", (roll,)).fetchone()

    if request.method == "POST":

        if "profile_pic" in request.files:
            photo = request.files["profile_pic"]
            if photo and photo.filename != "":
                filename = secure_filename(photo.filename)
                photo.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
                conn.execute("UPDATE students SET profile_pic=? WHERE roll_no=?", (filename, roll))
                conn.commit()

        if "certificate" in request.files:
            file = request.files["certificate"]
            if student_data and student_data["section"] and file and file.filename != "":
                category = request.form.get("category", "Certification")
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
                conn.execute(
                    "INSERT INTO certificates (student_name, roll_no, section, category, file_name, status) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (student_data["name"], roll, student_data["section"], category, filename, "Pending")
                )
                conn.commit()

        if "achievements" in request.form:
            achievements = request.form["achievements"]
            conn.execute("UPDATE students SET achievements=? WHERE roll_no=?", (achievements, roll))
            conn.commit()

    certificates = conn.execute("SELECT * FROM certificates WHERE roll_no=?", (roll,)).fetchall()
    conn.close()

    return render_template("student.html", student=student_data, certificates=certificates,
                           university="Graphic Era Hill University")


@app.route("/approve/<int:id>")
def approve(id):
    if session.get("role") != "coordinator":
        return redirect("/")

    conn = get_db()
    conn.execute("UPDATE certificates SET status='Approved' WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect("/coordinator")

@app.route("/reject/<int:id>")
def reject(id):
    if session.get("role") != "coordinator":
        return redirect("/")

    conn = get_db()
    conn.execute("UPDATE certificates SET status='Rejected' WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect("/coordinator")


@app.route("/delete/<int:id>")
def delete_student(id):
    # Admin only
    if session.get("role") != "admin":
        return redirect("/")

    conn = get_db()

    # Delete from students table
    conn.execute("DELETE FROM students WHERE id=?", (id,))

    # Also delete corresponding user account if exists
    # In this app, students.roll_no == users.username
    user = conn.execute("SELECT roll_no FROM students WHERE id=?", (id,)).fetchone()
    # Note: since we deleted above, fetch might be None. To be safe, fetch first.
    conn.close()

    # Re-implement safely with two-step: fetch roll_no first.
    conn = get_db()
    row = conn.execute("SELECT roll_no FROM students WHERE id=?", (id,)).fetchone()
    if row:
        roll_no = row["roll_no"]
        conn.execute("DELETE FROM students WHERE id=?", (id,))
        conn.execute("DELETE FROM users WHERE username=?", (roll_no,))
    else:
        # If already deleted from students, still attempt users deletion by id mapping impossible.
        conn.execute("DELETE FROM students WHERE id=?", (id,))

    conn.commit()
    conn.close()
    return redirect("/admin")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


if __name__ == "__main__":
    app.run(debug=True)

