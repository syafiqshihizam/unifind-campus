"""Repair the LOCAL CampusBack demo counter account without deleting items or users.
Put this file next to server.py and run: python FIX_COUNTER_LOGIN.py
For classroom/demo projects only. Never ship preset credentials to production.
"""
from server import db_connect, init_db, make_hash, now, DB_PATH

EMAIL = "counter@campus.test"
DEMO_PASSWORD = "Demo1234!"

init_db()
with db_connect() as con:
    row = con.execute("SELECT id FROM users WHERE email=? COLLATE NOCASE", (EMAIL,)).fetchone()
    if row:
        user_id = row["id"]
        con.execute(
            "UPDATE users SET password_hash=?, is_staff=1 WHERE id=?",
            (make_hash(DEMO_PASSWORD), user_id),
        )
        result = "Reset existing counter account"
    else:
        cur = con.execute(
            "INSERT INTO users (name, email, password_hash, created_at, is_staff) VALUES (?, ?, ?, ?, 1)",
            ("Campus Counter Staff", EMAIL, make_hash(DEMO_PASSWORD), now()),
        )
        user_id = cur.lastrowid
        result = "Created missing counter account"
    # Force a fresh login after credential reset. Do not touch other accounts/data.
    con.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))

print("SUCCESS:", result)
print("Database:", DB_PATH)
print("Email:", EMAIL)
print("Password:", DEMO_PASSWORD)
print("Role: Counter Staff")
print("This is a DEMO password: change it before any public deployment.")
