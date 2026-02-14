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
            # approval check
            if user["role"] == "coordinator" and user["approved"] == 0:
                return "Account not approved by admin yet."

            session["role"] = user["role"]
            session["section"] = user["section"]

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


# ---------------- ADMIN DASHBOARD ----------------
@app.route("/admin", methods=["GET", "POST"])
def admin():

    if "role" not in session or session["role"] != "admin":
        return redirect("/")

    conn = get_db()

    # Add student
    if request.method == "POST":
        name = request.form["name"]
        roll = request.form["roll"]
        dept = request.form["department"]
        sem = request.form["semester"]
        cgpa = request.form["cgpa"]
        attendance = request.form["attendance"]

        conn.execute(
            "INSERT INTO students (name, roll_no, department, semester, cgpa, attendance) VALUES (?, ?, ?, ?, ?, ?)",
            (name, roll, dept, sem, cgpa, attendance)
        )
        conn.commit()

    students = conn.execute("SELECT * FROM students").fetchall()

    pending_users = conn.execute(
        "SELECT * FROM users WHERE role='coordinator' AND approved=0"
    ).fetchall()

    conn.close()

    return render_template("admin.html", students=students, pending=pending_users)


# ---------------- APPROVE COORDINATOR ----------------
@app.route("/approve_coordinator/<int:id>", methods=["POST"])
def approve_coordinator(id):

    if "role" not in session or session["role"] != "admin":
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


# ---------------- DELETE STUDENT ----------------
@app.route("/delete/<int:id>")
def delete_student(id):
    conn = get_db()
    conn.execute("DELETE FROM students WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect("/admin")


# ---------------- STUDENT DASHBOARD ----------------
@app.route("/student", methods=["GET", "POST"])
def student():

    if "role" not in session or session["role"] != "student":
        return redirect("/")

    conn = get_db()

    if request.method == "POST":
        name = request.form["name"]
        roll = request.form["roll"]
        section = request.form["section"]
        file = request.files["certificate"]

        if file:
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

            conn.execute(
                "INSERT INTO certificates (student_name, roll_no, section, file_name, status) VALUES (?, ?, ?, ?, ?)",
                (name, roll, section, filename, "Pending")
            )
            conn.commit()

    certificates = conn.execute(
        "SELECT * FROM certificates WHERE roll_no=?",
        (request.form.get("roll", ""),)
    ).fetchall()

    conn.close()

    return render_template("student.html", certificates=certificates)


# ---------------- COORDINATOR DASHBOARD ----------------
@app.route("/coordinator")
def coordinator():

    if "role" not in session or session["role"] != "coordinator":
        return redirect("/")

    section = session["section"]

    conn = get_db()
    certificates = conn.execute(
        "SELECT * FROM certificates WHERE section=?",
        (section,)
    ).fetchall()
    conn.close()

    return render_template("coordinator.html", certificates=certificates)

#           REJECT COORDINATOR             
@app.route("/reject_coordinator/<int:id>")
def reject_coordinator(id):

    if "role" not in session or session["role"] != "admin":
        return redirect("/")

    conn = get_db()
    conn.execute("DELETE FROM users WHERE id=?", (id,))
    conn.commit()
    conn.close()

    return redirect("/admin")

# ---------------- APPROVE / REJECT CERTIFICATE ----------------
@app.route("/approve/<int:id>")
def approve(id):

    if "role" not in session or session["role"] != "coordinator":
        return redirect("/")

    conn = get_db()
    conn.execute("UPDATE certificates SET status='Approved' WHERE id=?", (id,))
    conn.commit()
    conn.close()

    return redirect("/coordinator")


@app.route("/reject/<int:id>")
def reject(id):

    if "role" not in session or session["role"] != "coordinator":
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
