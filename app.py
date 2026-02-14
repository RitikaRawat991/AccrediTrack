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

def get_db():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn
@app.route("/update/<int:id>", methods=["POST"])
def update_student(id):

    if "role" not in session or session["role"] != "coordinator":
        return redirect("/")

    cgpa = request.form["cgpa"]
    attendance = request.form["attendance"]

    conn = get_db()
    conn.execute(
        "UPDATE students SET cgpa=?, attendance=? WHERE id=?",
        (cgpa, attendance, id)
    )
    conn.commit()
    conn.close()

    return redirect("/coordinator")

# Login Route
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
            session["role"] = user["role"]

            if user["role"] == "admin":
                return redirect("/admin")
            elif user["role"] == "coordinator":
                return redirect("/coordinator")
            elif user["role"] == "student":
                return redirect("/student")

        else:
            return "Invalid Credentials"

    return render_template("login.html")
@app.route("/approve/<int:id>")
def approve(id):
    conn = get_db()
    conn.execute("UPDATE certificates SET status='Approved' WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect("/coordinator")


@app.route("/reject/<int:id>")
def reject(id):
    conn = get_db()
    conn.execute("UPDATE certificates SET status='Rejected' WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect("/coordinator")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")
@app.route("/coordinator")
def coordinator():

    if "role" not in session or session["role"] != "coordinator":
        return redirect("/")

    conn = get_db()
    certificates = conn.execute("SELECT * FROM certificates").fetchall()
    conn.close()

    return render_template("coordinator.html", certificates=certificates)


@app.route("/student", methods=["GET", "POST"])
def student():

    if "role" not in session or session["role"] != "student":
        return redirect("/")

    conn = get_db()

    if request.method == "POST":
        file = request.files["certificate"]

        if file:
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

            conn.execute(
                "INSERT INTO certificates (student_name, file_name, status) VALUES (?, ?, ?)",
                ("Student", filename, "Pending")
            )
            conn.commit()

    certificates = conn.execute(
        "SELECT * FROM certificates WHERE student_name=?",
        ("Student",)
    ).fetchall()

    conn.close()

    return render_template("student.html", certificates=certificates)

@app.route("/admin", methods=["GET", "POST"])
def admin():

    if "role" not in session or session["role"] != "admin":
        return redirect("/")
    if request.method == "POST":
        name = request.form["name"]
        roll = request.form["roll"]
        dept = request.form["department"]
        sem = request.form["semester"]
        cgpa = request.form["cgpa"]
        attendance = request.form["attendance"]

        conn = get_db()
        conn.execute(
            "INSERT INTO students (name, roll_no, department, semester, cgpa, attendance) VALUES (?, ?, ?, ?, ?, ?)",
            (name, roll, dept, sem, cgpa, attendance)
        )
        conn.commit()
        conn.close()

    conn = get_db()
    students = conn.execute("SELECT * FROM students").fetchall()
    conn.close()

    return render_template("admin.html", students=students)


@app.route("/delete/<int:id>")
def delete_student(id):
    conn = get_db()
    conn.execute("DELETE FROM students WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect("/admin")


if __name__ == "__main__":
    app.run(debug=True)
