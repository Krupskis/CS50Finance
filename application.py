import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
import datetime

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    user_id = session["user_id"]
    purchases = db.execute("SELECT name, symbol, SUM(shares) FROM purchases WHERE user_id=? GROUP BY symbol;", user_id)

    balance = db.execute("SELECT cash FROM users WHERE id=?;", user_id)
    prices = []
    for row in purchases:
            data = lookup(row["symbol"])
            prices.append(data["price"])



    return render_template("index.html", purchases = purchases, prices = prices, balance = balance[0])
    return apology("TODO")


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "POST":

        try:
            val = int(request.form.get("shares"))
            if val <= 0:
                return apology("Oops. That's not a valid number")
        except ValueError:
            return apology("Oops. That's not a valid number")
        data = lookup(request.form.get("symbol"))
        if data is None:
            return apology("This symbol does not exist", 403)

        # Creating a timestamp
        ts = datetime.datetime.now().strftime("%A, %d. %B %Y %I:%M%p")
        # looking how much money the user has left on his account
        remainder = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        if data["price"]*int(request.form.get("shares")) > remainder[0]['cash']:
            return apology("insufficient funds", 403)
        else:
            db.execute("UPDATE users SET cash = ? WHERE id = ?", remainder[0]['cash']-data["price"]*int(request.form.get("shares")), session["user_id"])
            db.execute("INSERT INTO purchases(user_id, price, date, shares, symbol, name) VALUES (:user_id, :price, :date, :shares, :symbol, :name)",
            user_id = session["user_id"], price = data["price"], date = ts, shares = int(request.form.get("shares")), symbol = data["symbol"], name = data["name"])
            message = "Bought"
            flash("Bought!")
            return redirect("/")

    else:
        return render_template("buy.html")

@app.route("/history")
@login_required
def history():
    user_id = session["user_id"]
    histories = db.execute("SELECT purchase_id, symbol, name, shares, date, price FROM purchases WHERE user_id=? ORDER BY purchase_id;", user_id)
    return render_template("history.html", histories=histories)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    if request.method == "POST":
        symbol = request.form.get("symbol")
        data = lookup(symbol)
        if data is None:
            return apology("there is no company with stock symbol like this", 403)
        return render_template("quoted.html", name = data["name"], price = usd(data["price"]))


    return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():

    session.clear()

    if request.method == "POST":

        if not request.form.get("register_username"):
            return apology("must provide username", 404)

        elif not request.form.get("register_password"):
            return apology("must provide password", 403)

        elif request.form.get("register_password") != request.form.get("confirmation"):
            return apology("passwords must match", 403)

        db.execute("INSERT INTO users (username, hash) VALUES (:username, :password)", username = request.form.get("register_username"), password = generate_password_hash(request.form.get("register_password")))
        return redirect("/login")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    user_id = session["user_id"]
    ts = datetime.datetime.now().strftime("%A, %d. %B %Y %I:%M%p")
    if request.method == "POST":
        symbol = request.form.get("symbol")
        try:
            shares = int(request.form.get("shares"))
            if shares <= 0:
                return apology("Oops. That's not a valid number")
        except ValueError:
            return apology("Oops. That's not a valid number")

        purchases = db.execute("SELECT name, symbol, SUM(shares) FROM purchases WHERE user_id=? GROUP BY symbol;", user_id)
        for purchase in purchases:
            if purchase["symbol"] == symbol:
                if purchase["SUM(shares)"] < shares:
                    return apology("you don't enough stocks", 403)
        shares = 0 - shares
        data = lookup(symbol)
        remainder = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        db.execute("UPDATE users SET cash = ? WHERE id = ?", remainder[0]['cash']+data["price"]*int(request.form.get("shares")), user_id)
        db.execute("INSERT INTO purchases(user_id, price, date, shares, symbol, name) VALUES (:user_id, :price, :date, :shares, :symbol, :name)",
            user_id = user_id, price = data["price"], date = ts, shares = shares, symbol = symbol, name = data["name"])

        flash("sold!")
        return redirect("/")

    else:
        purchases = db.execute("SELECT name, symbol, SUM(shares) FROM purchases WHERE user_id=? GROUP BY symbol;", user_id)
        return render_template("sell.html", purchases=purchases)

@app.route("/changePassword", methods=["POST", "GET"])
@login_required
def changePassword():
    if request.method == "POST":
        user_id = session["user_id"]
        data = db.execute("SELECT hash FROM users where id=?;", user_id)
        password = data[0]["hash"]
        if not check_password_hash(password, request.form.get("current_password")):
            return apology("Wrong current password!", 403)
        elif request.form.get("new_password") != request.form.get("confirm_new_password"):
            return apology("Passwords do not match!", 403)
        elif request.form.get("new_password") == request.form.get("current_password"):
            return apology("you can't change your password to the current one", 403)
        new_password = generate_password_hash(request.form.get("new_password"))
        db.execute("UPDATE users SET hash=? WHERE id=?;", new_password, user_id)
        flash("Password Changed!")
        return redirect("/")
    else:
        return render_template("change.html")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)


# Formatting for flask
def usd(value):
    """Format value as USD."""
    return f"${value:,.2f}"

app.jinja_env.globals.update(usd=usd)
