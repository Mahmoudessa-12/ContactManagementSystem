from flask import Flask, render_template, request, redirect, session
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

app.secret_key = "contact-management-secret-key"


def get_db_connection():
    connection = sqlite3.connect("contacts.db")
    connection.row_factory = sqlite3.Row
    return connection


# =========================
# Home / Login Page
# =========================

@app.route("/")
def home():
    return render_template("login.html")


# =========================
# Register
# =========================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]

        password_hash = generate_password_hash(password)

        connection = get_db_connection()

        try:
            connection.execute(
                """
                INSERT INTO Users
                (username, email, password_hash, role)
                VALUES (?, ?, ?, ?)
                """,
                (username, email, password_hash, "user")
            )

            connection.commit()

        except sqlite3.IntegrityError:
            connection.close()
            return "Username or email already exists."

        connection.close()

        return redirect("/")

    return render_template("register.html")


# =========================
# Login
# =========================

@app.route("/login", methods=["POST"])
def login():

    username = request.form["username"]
    password = request.form["password"]

    connection = get_db_connection()

    user = connection.execute(
        "SELECT * FROM Users WHERE username = ?",
        (username,)
    ).fetchone()

    connection.close()

    if user and check_password_hash(
        user["password_hash"],
        password
    ):

        session.clear()

        session["user_id"] = user["id"]
        session["username"] = user["username"]
        session["role"] = user["role"]

        print("LOGGED IN USER ID:", session["user_id"])
        print("LOGGED IN USERNAME:", session["username"])
        print("LOGGED IN ROLE:", session["role"])

        if user["role"] == "admin":
            return redirect("/admin")

        return redirect("/dashboard")

    return "Invalid username or password."


# =========================
# User Dashboard
# =========================

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect("/")

    return render_template(
        "dashboard.html",
        username=session["username"],
        role=session["role"]
    )


# =========================
# Admin Dashboard
# =========================

@app.route("/admin")
def admin_dashboard():

    if "user_id" not in session:
        return redirect("/")

    if session["role"] != "admin":
        return "Access Denied"

    return render_template(
        "admin_dashboard.html",
        username=session["username"]
    )


# =========================
# Admin - View Users
# =========================

@app.route("/admin/users")
def admin_users():

    if "user_id" not in session:
        return redirect("/")

    if session["role"] != "admin":
        return "Access Denied"

    connection = get_db_connection()

    users = connection.execute(
        """
        SELECT id, username, email, role, created_at
        FROM Users
        ORDER BY id DESC
        """
    ).fetchall()

    connection.close()

    return render_template(
        "admin_users.html",
        users=users
    )


# =========================
# Admin - Delete User
# =========================

@app.route("/admin/delete-user/<int:user_id>", methods=["POST"])
def admin_delete_user(user_id):

    if "user_id" not in session:
        return redirect("/")

    if session["role"] != "admin":
        return "Access Denied"

    if user_id == session["user_id"]:
        return "You cannot delete your own admin account."

    connection = get_db_connection()

    connection.execute(
        """
        DELETE FROM Contacts
        WHERE user_id = ?
        """,
        (user_id,)
    )

    connection.execute(
        """
        DELETE FROM Users
        WHERE id = ?
        """,
        (user_id,)
    )

    connection.commit()
    connection.close()

    return redirect("/admin/users")


# =========================
# Admin - View All Contacts
# =========================

@app.route("/admin/contacts")
def admin_contacts():

    if "user_id" not in session:
        return redirect("/")

    if session["role"] != "admin":
        return "Access Denied"

    connection = get_db_connection()

    contacts = connection.execute(
        """
        SELECT
            Contacts.id,
            Contacts.name,
            Contacts.phone,
            Contacts.email,
            Contacts.address,
            Contacts.category,
            Contacts.created_at,
            Users.username
        FROM Contacts
        JOIN Users
        ON Contacts.user_id = Users.id
        ORDER BY Contacts.id DESC
        """
    ).fetchall()

    connection.close()

    return render_template(
        "admin_contacts.html",
        contacts=contacts
    )


# =========================
# Add Contact
# =========================

@app.route("/add-contact", methods=["GET", "POST"])
def add_contact():

    if "user_id" not in session:
        return redirect("/")

    if request.method == "POST":

        name = request.form["name"]
        phone = request.form["phone"]
        email = request.form["email"]
        address = request.form["address"]
        category = request.form["category"]

        connection = get_db_connection()

        connection.execute(
            """
            INSERT INTO Contacts
            (user_id, name, phone, email, address, category)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                session["user_id"],
                name,
                phone,
                email,
                address,
                category
            )
        )

        connection.commit()
        connection.close()

        return redirect("/contacts")

    return render_template("add_contact.html")


# =========================
# View / Search / Filter Contacts
# =========================

@app.route("/contacts")
def contacts():

    if "user_id" not in session:
        return redirect("/")

    search = request.args.get("search", "").strip()
    category = request.args.get("category", "").strip()

    connection = get_db_connection()

    query = """
        SELECT *
        FROM Contacts
        WHERE user_id = ?
    """

    parameters = [session["user_id"]]

    if search:

        query += """
            AND (
                name LIKE ?
                OR phone LIKE ?
                OR email LIKE ?
                OR category LIKE ?
            )
        """

        search_value = "%" + search + "%"

        parameters.extend([
            search_value,
            search_value,
            search_value,
            search_value
        ])

    if category:

        query += " AND category = ?"

        parameters.append(category)

    query += " ORDER BY id DESC"

    contacts = connection.execute(
        query,
        parameters
    ).fetchall()

    categories = connection.execute(
        """
        SELECT DISTINCT category
        FROM Contacts
        WHERE user_id = ?
        AND category IS NOT NULL
        AND category != ''
        ORDER BY category
        """,
        (session["user_id"],)
    ).fetchall()

    connection.close()

    return render_template(
        "contacts.html",
        contacts=contacts,
        search=search,
        category=category,
        categories=categories
    )


# =========================
# Update Contact
# =========================

@app.route("/edit-contact/<int:contact_id>", methods=["GET", "POST"])
def edit_contact(contact_id):

    if "user_id" not in session:
        return redirect("/")

    connection = get_db_connection()

    contact = connection.execute(
        """
        SELECT *
        FROM Contacts
        WHERE id = ? AND user_id = ?
        """,
        (contact_id, session["user_id"])
    ).fetchone()

    if contact is None:
        connection.close()
        return "Contact not found."

    if request.method == "POST":

        name = request.form["name"]
        phone = request.form["phone"]
        email = request.form["email"]
        address = request.form["address"]
        category = request.form["category"]

        connection.execute(
            """
            UPDATE Contacts
            SET name = ?,
                phone = ?,
                email = ?,
                address = ?,
                category = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ?
            """,
            (
                name,
                phone,
                email,
                address,
                category,
                contact_id,
                session["user_id"]
            )
        )

        connection.commit()
        connection.close()

        return redirect("/contacts")

    connection.close()

    return render_template(
        "edit_contact.html",
        contact=contact
    )


# =========================
# Delete Contact
# =========================

@app.route("/delete-contact/<int:contact_id>")
def delete_contact(contact_id):

    if "user_id" not in session:
        return redirect("/")

    connection = get_db_connection()

    connection.execute(
        """
        DELETE FROM Contacts
        WHERE id = ? AND user_id = ?
        """,
        (contact_id, session["user_id"])
    )

    connection.commit()
    connection.close()

    return redirect("/contacts")


# =========================
# Logout
# =========================

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/")


# =========================
# Test Database
# =========================

@app.route("/test-db")
def test_database():

    connection = get_db_connection()

    users = connection.execute(
        "SELECT * FROM Users"
    ).fetchall()

    contacts = connection.execute(
        "SELECT * FROM Contacts"
    ).fetchall()

    connection.close()

    return f"Database Connected! Users: {len(users)}, Contacts: {len(contacts)}"


# =========================
# Run Application
# =========================

if __name__ == "__main__":
    app.run(debug=True)