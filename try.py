from cs50 import SQL

from helpers import apology, login_required, lookup, usd


db = SQL("sqlite:///finance.db")

user_id = 3
purchases = db.execute("SELECT name, symbol, SUM(shares) FROM purchases WHERE user_id=? GROUP BY symbol;", user_id)

prices = []
for row in purchases:
    prices.append(lookup(row["symbol"])["price"])



print(prices)