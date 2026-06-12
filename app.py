from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, render_template, request, redirect, url_for, session, Response
import csv
import io
import sqlite3 , matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
app = Flask(__name__)

app.secret_key = "spendwise_secret_key"


# ==========================
# DATABASE
# ==========================

def init_db():

    conn = sqlite3.connect("spendwise.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS expenses(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount REAL NOT NULL,
        category TEXT NOT NULL,
        date TEXT NOT NULL,
        description TEXT
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS incomes(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        amount REAL NOT NULL,
        source TEXT NOT NULL,
        date TEXT NOT NULL
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS goals(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    target_amount REAL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS budget(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount REAL NOT NULL
    )
    """)

    conn.commit()
    conn.close()


# ==========================
# HOME
# ==========================

@app.route("/")
def home():
    return render_template("index.html")


# ==========================
# REGISTER
# ==========================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]
        password = generate_password_hash (
            request.form["password"]
        )

        conn = sqlite3.connect("spendwise.db")
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
            (name, email, password)
        )

        conn.commit()
        conn.close()

        return """
        <h2>✅ Account Created Successfully!</h2>
        <a href='/login'>Go To Login</a>
        """

    return render_template("register.html")


# ==========================
# LOGIN
# ==========================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]
        

        conn = sqlite3.connect("spendwise.db")
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM users WHERE email=?",
            (email, )
        )

        user = cursor.fetchone()

        conn.close()

        if user and check_password_hash(
            user[3],
            password
        ):

            session["user_id"] = user[0]
            session["user_name"] = user[1]

            return redirect(url_for("dashboard"))

        return "<h2>❌ Invalid Email or Password</h2>"

    return render_template("login.html")


# ==========================
# DASHBOARD
# ==========================

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect("spendwise.db")
    cursor = conn.cursor()

    # search feature

    search = request.args.get("search", "")
    category = request.args.get("category", "")
    period = request.args.get("period", "")
    if search:


        cursor.execute("""
        SELECT * FROM expenses
        WHERE user_id=?
        AND (
            category LIKE ?
            OR description LIKE ?
        )
        """,
        (
            session["user_id"],
            f"%{search}%",
            f"%{search}%"
        ))

    elif category:

        cursor.execute("""
        SELECT * FROM expenses
        WHERE user_id=?
        AND category=?
        """,
        (
           session["user_id"],
           category
        ))
          

    elif period == "this_month":

       cursor.execute("""
       SELECT *
       FROM expenses
       WHERE user_id=?
       AND strftime('%Y-%m', date)=strftime('%Y-%m', 'now')
       """,
      (session["user_id"],))

    elif period == "last_month":

       cursor.execute("""
       SELECT *
       FROM expenses
       WHERE user_id=?
       AND strftime('%Y-%m', date)=strftime('%Y-%m', date('now','-1 month'))
       """,
       (session["user_id"],))

    else:

        cursor.execute(
            "SELECT * FROM expenses WHERE user_id=?",
            (session["user_id"],)
        )

    expenses = cursor.fetchall()
    

    cursor.execute("""
    SELECT *
    FROM expenses
    WHERE user_id=?
    ORDER BY id DESC
    LIMIT 5
    """,
    (session["user_id"],))

    recent_expenses = cursor.fetchall()
    
    cursor.execute("""
    SELECT *
    FROM incomes
    ORDER BY id DESC
    LIMIT 5
    """)

    recent_incomes = cursor.fetchall()

    # Total Expense
    cursor.execute("SELECT SUM(amount) FROM expenses WHERE user_id=?",
                   (session["user_id"],)
                )
    result = cursor.fetchone()

    if result and result[0] is not None:
        total_expense = result[0]
    else:
        total_expense = 0

    # Total Income
    cursor.execute("SELECT SUM(amount) FROM incomes")
    result = cursor.fetchone()

    if result and result[0] is not None:
        total_income = result[0]
    else:
        total_income = 0

    # Balance
    balance = total_income - total_expense
    
    cursor.execute("""
    SELECT target_amount
    FROM goals
    WHERE user_id=?
    """,
    (session["user_id"],))

    goal = cursor.fetchone()

    goal_amount = 0
    progress = 0

    if goal:

       goal_amount = goal[0]

       if goal_amount > 0:
           progress = round((balance / goal_amount) * 100, 2)

           if progress > 100:
               progress = 100

    # Top Spending Category

    cursor.execute("""
    SELECT category, SUM(amount) as total
    FROM expenses
    WHERE user_id=?
    GROUP BY category
    ORDER BY total DESC
    LIMIT 1
    """, (session["user_id"],))

    top_category = cursor.fetchone()

    # Pie Chart Data
    cursor.execute("""
    SELECT category, SUM(amount)
    FROM expenses
    GROUP BY category
    """)

    data = cursor.fetchall()

    if data:

        categories = []
        amounts = []

        for row in data:
            categories.append(row[0])
            amounts.append(row[1])

        plt.figure(figsize=(5,5))

        plt.pie(
            amounts,
            labels=categories,
            autopct="%1.1f%%"
        )

        plt.title("Expense Distribution")

        plt.savefig("static/chart.png")

        plt.close()
    
    plt.figure(figsize=(6,4))

    plt.bar(
        ["Income", "Expense"],
        [total_income, total_expense]
    )

    plt.title("Income vs Expense")
    plt.ylabel("Amount (₹)")

    plt.savefig("static/income_expense.png")
    plt.close()

    # SET-BUDGET

    cursor.execute(
    "SELECT amount FROM budget WHERE user_id=?",
    (session["user_id"],)
    )

    budget_data = cursor.fetchone()

    budget_amount = 0
    alert_message = ""

    if budget_data:
        budget_amount = budget_data[0]

    if total_expense >= budget_amount:
        alert_message = f"🚨 Budget Exceeded by ₹{total_expense-budget_amount}"

    elif total_expense >= budget_amount * 0.8:
        alert_message = "⚠️ You have used more than 80% of your budget"

    # Monthly Analytics Graph

    cursor.execute("""
        SELECT substr(date,1,7), SUM(amount)
        FROM expenses
        WHERE user_id=?
        GROUP BY substr(date,1,7)
        ORDER BY substr(date,1,7)
        """, (session["user_id"],))

    monthly_data = cursor.fetchall()

    if monthly_data:

       months = []
       totals = []

       for row in monthly_data:
           months.append(row[0])
           totals.append(row[1])

       plt.figure(figsize=(8,4))

       plt.plot(
        months,
        totals,
        marker="o"
    )

    plt.title("Monthly Expenses")
    plt.xlabel("Month")
    plt.ylabel("Amount")

    plt.grid(True)

    plt.savefig("static/monthly_chart.png")

    plt.close()
   
    conn.close()
    return render_template(
        "dashboard.html",
        expenses=expenses,
        total_expense=total_expense,
        total_income=total_income,
        balance=balance,
        username=session["user_name"],
        budget_amount=budget_amount,
        alert_message=alert_message,
        top_category=top_category,
        recent_expenses=recent_expenses,
        recent_incomes=recent_incomes,
        progress=progress,
        goal_amount=goal_amount
    )


# ==========================
# ADD INCOME
# ==========================

@app.route("/add-income", methods=["GET", "POST"])
def add_income():

    if request.method == "POST":

        amount = request.form["amount"]
        source = request.form["source"]
        date = request.form["date"]

        conn = sqlite3.connect("spendwise.db")
        cursor = conn.cursor()

        cursor.execute("""
        INSERT INTO incomes(amount, source, date)
        VALUES (?, ?, ?)
        """, (amount, source, date))

        conn.commit()
        conn.close()

        return redirect(url_for("dashboard"))

    return render_template("add_income.html")


# ==========================
# SET GOAL
# ==========================

@app.route("/set-goal", methods=["GET", "POST"])
def set_goal():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":

        amount = request.form["amount"]

        conn = sqlite3.connect("spendwise.db")
        cursor = conn.cursor()

        cursor.execute("""
        DELETE FROM goals
        WHERE user_id=?
        """, (session["user_id"],))

        cursor.execute("""
        INSERT INTO goals(user_id, target_amount)
        VALUES (?,?)
        """, (session["user_id"], amount))

        conn.commit()
        conn.close()

        return redirect(url_for("dashboard"))

    return render_template("set_goal.html")

# ==========================
# ADD EXPENSE
# ==========================

@app.route("/add-expense", methods=["GET", "POST"])
def add_expense():

    if request.method == "POST":

        amount = request.form["amount"]
        category = request.form["category"]
        date = request.form["date"]
        description = request.form["description"]

        conn = sqlite3.connect("spendwise.db")
        cursor = conn.cursor()

        cursor.execute("""
        INSERT INTO expenses(user_id, amount, category, date, description)
        VALUES (?, ?, ?, ?, ?)
        """, (
            session["user_id"], 
            amount,
            category, 
            date, 
            description
            ))

        conn.commit()
        conn.close()

        return redirect(url_for("dashboard"))

    return render_template("add_expense.html")

# ==========================
# SET-BUDGET
# ==========================

@app.route("/set-budget", methods=["GET", "POST"])
def set_budget():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":

        amount = request.form["amount"]

        conn = sqlite3.connect("spendwise.db")
        cursor = conn.cursor()

        cursor.execute(
            "DELETE FROM budget WHERE user_id=?",
            (session["user_id"],)
        )

        cursor.execute("""
        INSERT INTO budget(user_id, amount)
        VALUES (?,?)
        """, (
            session["user_id"],
            amount
        ))

        conn.commit()
        conn.close()

        return redirect(url_for("dashboard"))

    return render_template("set_budget.html")


# ==========================
# EDIT EXPENSE
# ==========================

@app.route("/edit-expense/<int:id>", methods=["GET", "POST"])
def edit_expense(id):

    conn = sqlite3.connect("spendwise.db")
    cursor = conn.cursor()

    if request.method == "POST":

        amount = request.form["amount"]
        category = request.form["category"]
        date = request.form["date"]
        description = request.form["description"]

        cursor.execute("""
        UPDATE expenses
        SET amount=?,
            category=?,
            date=?,
            description=?
        WHERE id=?
        """,
        (amount, category, date, description, id))

        conn.commit()
        conn.close()

        return redirect(url_for("dashboard"))

    cursor.execute(
        "SELECT * FROM expenses WHERE id=?",
        (id,)
    )

    expense = cursor.fetchone()

    conn.close()

    return render_template(
        "edit_expense.html",
        expense=expense
    )


# ==========================
# DELETE EXPENSE
# ==========================

@app.route("/delete-expense/<int:id>")
def delete_expense(id):

    conn = sqlite3.connect("spendwise.db")
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM expenses WHERE id=?",
        (id,)
    )

    conn.commit()
    conn.close()

    return redirect(url_for("dashboard"))


@app.route("/export-csv")
def export_csv():

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect("spendwise.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT amount, category, date, description
        FROM expenses
        WHERE user_id=?
    """, (session["user_id"],))

    expenses = cursor.fetchall()

    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Amount",
        "Category",
        "Date",
        "Description"
    ])

    for expense in expenses:
        writer.writerow(expense)

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition":
            "attachment; filename=expenses.csv"
        }
    )


# ==========================
# DELETE INCOME
# ==========================

@app.route("/delete-income/<int:id>")
def delete_income(id):

    conn = sqlite3.connect("spendwise.db")
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM incomes WHERE id=?",
        (id,)
    )

    conn.commit()
    conn.close()

    return redirect(url_for("dashboard"))

# ==========================
# LOGOUT
# ==========================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


# ==========================
# RUN APP
# ==========================

if __name__ == "__main__":

    init_db()

    app.run(host="0.0.0.0", port=5000)