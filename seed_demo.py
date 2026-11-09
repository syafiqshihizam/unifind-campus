"""Seed local classroom demo users and FOUND items. Resets passwords of DEMO emails only."""
from datetime import date, timedelta
from server import db_connect, init_db, make_hash, now

init_db()
with db_connect() as con:
    users = {}
    for name, email, faculty, course, phone in [
        ('Sara', 'sara@campus.test', 'Faculty of Computing', 'Information Systems', '0123456789'),
        ('Daniel', 'daniel@campus.test', 'Faculty of Business', 'Entrepreneurship', '0112345678'),
    ]:
        row = con.execute('SELECT id FROM users WHERE email=?', (email,)).fetchone()
        if row:
            users[name] = row['id']
            con.execute('UPDATE users SET faculty=?,course=?,phone=?,password_hash=? WHERE id=?', (faculty, course, phone, make_hash('Demo1234!'), row['id']))
        else:
            users[name] = con.execute('''INSERT INTO users
                (name,email,password_hash,created_at,faculty,course,phone) VALUES(?,?,?,?,?,?,?)''',
                (name, email, make_hash('Demo1234!'), now(), faculty, course, phone)).lastrowid
    staff = con.execute('SELECT id FROM users WHERE email=?', ('counter@campus.test',)).fetchone()
    if not staff:
        con.execute('''INSERT INTO users(name,email,password_hash,created_at,is_staff)
            VALUES(?,?,?,?,1)''', ('Campus Counter Staff', 'counter@campus.test', make_hash('Demo1234!'), now()))
    else:
        con.execute('UPDATE users SET is_staff=1,password_hash=? WHERE id=?', (make_hash('Demo1234!'),staff['id']))
    # Add these fixtures only if there's no current found item at all.
    if con.execute("SELECT COUNT(*) FROM items WHERE kind='found'").fetchone()[0] == 0:
        d = (date.today() - timedelta(days=1)).isoformat()
        examples = [
            ('Daniel', 'Black Wallet', 'Wallet', 'Black', 'Library',
             'Small black leather wallet found by the library entrance.', 'How many cards are inside?', '3'),
            ('Daniel', 'White Wireless Earbuds', 'Electronics', 'White', 'Cafeteria',
             'White wireless earbuds found under a cafeteria table.', 'What is the colour of the sticker in the case?', 'Blue'),
            ('Daniel', 'Yellow Backpack', 'Bag', 'Yellow', 'Student Centre',
             'Yellow backpack found near the entrance of Student Centre.', 'What colour is the keychain?', 'Green'),
            ('Sara', 'Silver House Keys', 'Keys', 'Silver', 'Lecture Hall',
             'Set of silver keys with a small ring found near Lecture Hall 3.', 'How many keys are attached?', '4'),
        ]
        for username, name, category, color, location, description, question, answer in examples:
            con.execute('''INSERT INTO items(user_id,kind,name,category,color,location,event_date,description,
                verification_question,verification_hash,handover_location,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',
                (users[username], 'found', name, category, color, location, d, description,
                 question, make_hash(answer.casefold()), 'Student Affairs Office', now()))

print('CampusBack V8 demo accounts are ready (only FOUND items).')
print('Owner/student: sara@campus.test / Demo1234!')
print('Finder/student: daniel@campus.test / Demo1234!')
print('Counter staff: counter@campus.test / Demo1234!')
print('Wallet: 3 | Earbuds: Blue | Backpack: Green | Keys: 4')
