from flask import Flask, render_template, request, redirect, session
import sqlite3

app = Flask(__name__)
app.secret_key = "naac_secret"

def get_db():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn
@app.route("/coordinator")
def coordinator():

    if "role" not in session or session["role"] != "coordinator":
        return redirect("/")

    conn = get_db()
    students = conn.execute("SELECT * FROM students").fetchall()
    conn.close()

    return render_template("coordinator.html", students=students)

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

        else:
            return "Invalid Credentials"

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

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
