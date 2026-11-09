"""CampusBack V8: a dependency-free, found-items-only web application.
Run `python server.py` then visit http://localhost:8000.
Only uses the Python 3.9+ standard library.
"""
import base64
import hashlib
import hmac
import json
import mimetypes
import os
import re
import secrets
import sqlite3
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from contextlib import contextmanager
from email.parser import BytesParser
from email.policy import default
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

BASE = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get('CAMPUSBACK_DB', str(BASE / 'data' / 'campusback.db')))
UPLOAD_DIR = Path(os.environ.get('CAMPUSBACK_UPLOADS', str(BASE / 'uploads')))
STATIC_DIR = BASE / 'static'
MAX_BODY = 6 * 1024 * 1024
CATEGORIES = ('Wallet', 'Electronics', 'Keys', 'Cards', 'Bag', 'Bottle', 'Clothing', 'Other')
LOCATIONS = ('Library', 'Cafeteria', 'Lecture Hall', 'Student Centre', 'Hostel', 'Parking Area', 'Sports Centre', 'Other')
HANDOVERS = ('Student Affairs Office', 'Library Counter', 'Security Office')
COOKIE_NAME = 'campusback_session'
# PWA files (manifest, service worker, helpers) served from the site root so the worker can control '/'.
PWA_FILES = {
    '/manifest.webmanifest': 'manifest.webmanifest',
    '/service-worker.js': 'service-worker.js',
    '/pwa.js': 'pwa.js',
    '/offline.html': 'offline.html',
}
mimetypes.add_type('application/manifest+json', '.webmanifest')
PASSWORD_ITERS = 180_000


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


@contextmanager
def db_connect():
    conn = sqlite3.connect(DB_PATH, timeout=15)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON')
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    with db_connect() as con:
        con.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL COLLATE NOCASE UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sessions (
            token_hash TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            csrf_token TEXT NOT NULL,
            expires_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            kind TEXT NOT NULL CHECK(kind IN ('lost', 'found')),
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            color TEXT NOT NULL,
            location TEXT NOT NULL,
            event_date TEXT NOT NULL,
            description TEXT NOT NULL,
            photo TEXT,
            verification_question TEXT,
            verification_hash TEXT,
            handover_location TEXT,
            status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open', 'matched', 'returned')),
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS claims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            found_id INTEGER NOT NULL UNIQUE REFERENCES items(id),
            lost_id INTEGER NOT NULL REFERENCES items(id),
            claimant_id INTEGER NOT NULL REFERENCES users(id),
            status TEXT NOT NULL DEFAULT 'verified' CHECK(status IN ('verified', 'returned')),
            created_at TEXT NOT NULL,
            returned_at TEXT
        );
        CREATE TABLE IF NOT EXISTS claim_attempts (
            user_id INTEGER NOT NULL REFERENCES users(id),
            found_id INTEGER NOT NULL REFERENCES items(id),
            attempts INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY(user_id, found_id)
        );
        CREATE INDEX IF NOT EXISTS idx_items_kind_status ON items(kind, status);
        CREATE INDEX IF NOT EXISTS idx_items_user ON items(user_id);
        ''')
        # A real receipt requires confirmation from an authorized counter staff account.
        existing_user_cols = {r[1] for r in con.execute('PRAGMA table_info(users)')}
        if 'is_staff' not in existing_user_cols:
            con.execute('ALTER TABLE users ADD COLUMN is_staff INTEGER NOT NULL DEFAULT 0')
        con.executescript('''
        CREATE TABLE IF NOT EXISTS counter_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            found_id INTEGER NOT NULL UNIQUE REFERENCES items(id),
            finder_id INTEGER NOT NULL REFERENCES users(id),
            counter_location TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending_receipt'
                CHECK(status IN ('pending_receipt','received','claim_pending','claimed')),
            requested_at TEXT NOT NULL,
            received_at TEXT,
            received_by INTEGER REFERENCES users(id),
            lost_id INTEGER REFERENCES items(id),
            claimant_id INTEGER REFERENCES users(id),
            claim_requested_at TEXT,
            claimed_at TEXT,
            released_by INTEGER REFERENCES users(id)
        );
        CREATE INDEX IF NOT EXISTS idx_counter_status ON counter_submissions(status);
        CREATE TABLE IF NOT EXISTS direct_claims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            found_id INTEGER NOT NULL UNIQUE REFERENCES items(id),
            claimant_id INTEGER NOT NULL REFERENCES users(id),
            status TEXT NOT NULL DEFAULT 'verified' CHECK(status IN ('verified','returned')),
            created_at TEXT NOT NULL,
            finder_confirmed_at TEXT,
            owner_confirmed_at TEXT,
            returned_at TEXT
        );
        ''')
        # V7: community claims with independent meet-finder / counter workflows.
        existing_profile_cols = {r[1] for r in con.execute('PRAGMA table_info(users)')}
        for column in ('faculty', 'course', 'phone'):
            if column not in existing_profile_cols:
                con.execute(f'ALTER TABLE users ADD COLUMN {column} TEXT NOT NULL DEFAULT ""')
        con.executescript('''
        CREATE TABLE IF NOT EXISTS pickup_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            found_id INTEGER NOT NULL REFERENCES items(id),
            claimant_id INTEGER NOT NULL REFERENCES users(id),
            method TEXT NOT NULL CHECK(method IN ('meet','counter')),
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            accepted_at TEXT,
            submitted_at TEXT,
            received_at TEXT,
            finder_confirmed_at TEXT,
            owner_confirmed_at TEXT,
            completed_at TEXT,
            rejected_at TEXT,
            rejection_note TEXT
        );
        CREATE UNIQUE INDEX IF NOT EXISTS uniq_active_pickup_per_item
            ON pickup_requests(found_id) WHERE status NOT IN ('rejected','cancelled','completed');
        CREATE INDEX IF NOT EXISTS idx_pickups_claimant ON pickup_requests(claimant_id);
        ''')
        item_columns = {r[1] for r in con.execute('PRAGMA table_info(items)')}
        if 'custody' not in item_columns:
            con.execute("ALTER TABLE items ADD COLUMN custody TEXT NOT NULL DEFAULT 'finder'")
        # On upgrade preserve the fact that campus staff may already hold the item.
        con.execute('''UPDATE items SET custody='counter' WHERE id IN (
            SELECT found_id FROM pickup_requests WHERE method='counter'
            AND status IN ('counter_ready','completed'))''')
        # Upgrade an existing database without deleting reports or uploaded photos.
        existing = {row[1] for row in con.execute('PRAGMA table_info(claims)')}
        for column in ('finder_confirmed_at', 'owner_confirmed_at'):
            if column not in existing:
                con.execute(f'ALTER TABLE claims ADD COLUMN {column} TEXT')
        # Preserve returns already completed in older versions.
        con.execute("""UPDATE claims SET finder_confirmed_at=COALESCE(finder_confirmed_at,returned_at,created_at),
                    owner_confirmed_at=COALESCE(owner_confirmed_at,returned_at,created_at)
                    WHERE status='returned'""")


def make_hash(raw):
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', raw.encode('utf-8'), salt, PASSWORD_ITERS)
    return f'{base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}'


def verify_hash(raw, encoded):
    try:
        salt64, expected64 = encoded.split('$', 1)
        actual = hashlib.pbkdf2_hmac('sha256', raw.encode('utf-8'), base64.b64decode(salt64), PASSWORD_ITERS)
        return hmac.compare_digest(actual, base64.b64decode(expected64))
    except (ValueError, TypeError):
        return False


def norm_answer(value):
    return ' '.join(str(value).casefold().strip().split())


def sanitize_field(value, max_len=200):
    return str(value or '').strip()[:max_len]


def item_to_dict(row, private=False):
    obj = {k: row[k] for k in ('id', 'user_id', 'kind', 'name', 'category', 'color', 'location',
                              'event_date', 'description', 'status', 'created_at')}
    obj['photo_url'] = '/uploads/' + row['photo'] if row['photo'] else None
    if 'reporter' in row.keys():
        obj['reporter'] = row['reporter']
    if 'custody' in row.keys():
        obj['custody'] = row['custody']
    if 'counter_status' in row.keys():
        obj['counter_status'] = row['counter_status']
    if private:
        obj['verification_question'] = row['verification_question'] if row['kind'] == 'found' else None
    return obj


def safe_photo(filename, contents):
    """Trust file signatures rather than only user-supplied extensions or MIME types."""
    filename = filename.lower()
    if filename.endswith(('.jpg', '.jpeg')) and contents[:3] == b'\xff\xd8\xff':
        ext = '.jpg'
    elif filename.endswith('.png') and contents[:8] == b'\x89PNG\r\n\x1a\n':
        ext = '.png'
    elif filename.endswith('.webp') and contents[:4] == b'RIFF' and contents[8:12] == b'WEBP':
        ext = '.webp'
    else:
        raise ValueError('Please upload a valid JPG, PNG, or WEBP image.')
    if not contents or len(contents) > 4 * 1024 * 1024:
        raise ValueError('Photo must be smaller than 4 MB.')
    new_name = uuid.uuid4().hex + ext
    (UPLOAD_DIR / new_name).write_bytes(contents)
    return new_name


class CampusHandler(BaseHTTPRequestHandler):
    server_version = 'CampusBack/8.0'

    def log_message(self, format, *args):
        print('[CampusBack]', format % args)

    def send_json(self, value, status=200, cookie=None):
        payload = json.dumps(value, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        if cookie:
            self.send_header('Set-Cookie', cookie)
        self.end_headers()
        self.wfile.write(payload)

    def fail(self, message, status=400):
        self.send_json({'error': message}, status)

    def get_session(self):
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get('Cookie', ''))
        except Exception:
            return None
        if COOKIE_NAME not in cookie:
            return None
        token_hash = hashlib.sha256(cookie[COOKIE_NAME].value.encode()).hexdigest()
        with db_connect() as con:
            row = con.execute('''SELECT s.csrf_token, u.id, u.name, u.email, u.is_staff, u.faculty, u.course, u.phone
                FROM sessions s JOIN users u ON u.id=s.user_id
                WHERE s.token_hash=? AND s.expires_at>?''', (token_hash, now())).fetchone()
        return dict(row) if row else None

    def auth(self, check_csrf=False):
        user = self.get_session()
        if not user:
            self.fail('Please log in first.', 401)
            return None
        if check_csrf and not hmac.compare_digest(self.headers.get('X-CSRF-Token', ''), user['csrf_token']):
            self.fail('Session verification failed. Refresh the page and try again.', 403)
            return None
        return user

    def read_body(self):
        size = int(self.headers.get('Content-Length', '0'))
        if size <= 0 or size > MAX_BODY:
            raise ValueError('Request is empty or too large (maximum 6 MB).')
        return self.rfile.read(size)

    def read_json(self):
        if not self.headers.get('Content-Type', '').lower().startswith('application/json'):
            raise ValueError('Expected JSON data.')
        obj = json.loads(self.read_body())
        if not isinstance(obj, dict):
            raise ValueError('Invalid form data.')
        return obj

    def read_form(self):
        ctype = self.headers.get('Content-Type', '')
        if not ctype.startswith('multipart/form-data;'):
            raise ValueError('Expected a report form.')
        raw = (f'Content-Type: {ctype}\r\nMIME-Version: 1.0\r\n\r\n').encode() + self.read_body()
        msg = BytesParser(policy=default).parsebytes(raw)
        if not msg.is_multipart():
            raise ValueError('Invalid upload form.')
        data, files = {}, {}
        for part in msg.iter_parts():
            disp = part.get('Content-Disposition', '')
            name_match = re.search(r'(?:^|;)\s*name="([^"]+)"', disp)
            if not name_match:
                continue
            key = name_match.group(1)
            payload = part.get_payload(decode=True) or b''
            filename = part.get_filename()
            if filename:
                files[key] = (filename, payload)
            else:
                data[key] = payload.decode('utf-8', errors='replace')
        return data, files

    def start_session(self, user_id):
        token = secrets.token_urlsafe(40)
        csrf_token = secrets.token_urlsafe(32)
        expiry = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(timespec='seconds')
        with db_connect() as con:
            con.execute('INSERT INTO sessions(token_hash,user_id,csrf_token,expires_at) VALUES(?,?,?,?)',
                        (hashlib.sha256(token.encode()).hexdigest(), user_id, csrf_token, expiry))
        suffix = '; Secure' if os.environ.get('CAMPUSBACK_HTTPS') == '1' else ''
        return f'{COOKIE_NAME}={token}; HttpOnly; SameSite=Lax; Path=/; Max-Age=604800{suffix}'

    def do_GET(self):
        path = unquote(urlsplit(self.path).path)
        # V6 intentionally has no lost-report, automatic match, or legacy claim pages.
        if path in ('/api/my-items', '/api/matches', '/api/claims', '/api/counter'):
            self.fail('This old route is no longer supported in CampusBack V8.', 410)
            return
        try:
            if path in ('/', '/index.html', '/app.js', '/styles.css'):
                file = STATIC_DIR / ('index.html' if path == '/' else path.lstrip('/'))
                self.serve_file(file)
            elif path in PWA_FILES:
                self.serve_file(STATIC_DIR / PWA_FILES[path])
            elif re.fullmatch(r'/icons/[a-z0-9\-]+\.(?:png|svg)', path):
                self.serve_file(STATIC_DIR / 'icons' / path.rsplit('/', 1)[-1])
            elif path.startswith('/uploads/'):
                filename = path.rsplit('/', 1)[-1]
                if not re.fullmatch(r'[a-f0-9]{32}\.(?:png|jpg|webp)', filename):
                    self.fail('Image not found.', 404)
                else:
                    self.serve_file(UPLOAD_DIR / filename)
            elif path == '/api/session':
                user = self.get_session()
                self.send_json({'authenticated': bool(user), 'user':
                    {'id': user['id'], 'name': user['name'], 'email': user['email'], 'is_staff': bool(user['is_staff']), 'faculty':user['faculty'], 'course':user['course'], 'phone':user['phone']} if user else None,
                    'csrf_token': user['csrf_token'] if user else None})
            elif path == '/api/items':
                params = parse_qs(urlsplit(self.path).query)
                term = sanitize_field(params.get('q', [''])[0], 100)
                category = params.get('category', ['all'])[0]
                # V6: Public community shows FOUND reports only. Pending/returned items are not listed.
                sql = """SELECT i.*, u.name AS reporter, cs.status AS counter_status
                    FROM items i JOIN users u ON u.id=i.user_id
                    LEFT JOIN counter_submissions cs ON cs.found_id=i.id
                    WHERE i.kind=? AND i.status='open'"""
                args = ['found']
                if category in CATEGORIES:
                    sql += ' AND i.category=?'; args.append(category)
                if term:
                    sql += ' AND (i.name LIKE ? OR i.description LIKE ? OR i.location LIKE ?)'
                    args.extend(['%' + term + '%'] * 3)
                sql += ' ORDER BY i.created_at DESC, i.id DESC LIMIT 120'
                with db_connect() as con:
                    records = con.execute(sql, args).fetchall()
                self.send_json({'items': [item_to_dict(row) for row in records]})
            elif re.fullmatch(r'/api/items/\d+/claim-info', path):
                user = self.auth()
                if not user: return
                found_id = int(path.split('/')[3])
                with db_connect() as con:
                    row = con.execute("""SELECT i.*, cs.id AS counter_id, cs.status AS counter_status
                        FROM items i LEFT JOIN counter_submissions cs ON cs.found_id=i.id
                        WHERE i.id=? AND i.kind='found'""", (found_id,)).fetchone()
                if user['is_staff']:
                    self.fail('Only students can claim items.',403); return
                if not row or row['status'] != 'open':
                    self.fail('This item is no longer available to claim.', 409); return
                if row['user_id'] == user['id']:
                    self.fail('You cannot claim an item you reported yourself.', 403); return
                if row['counter_id'] and row['counter_status'] != 'received':
                    self.fail('This item cannot be claimed until the counter confirms receipt.', 409); return
                if not row['verification_question'] or not row['verification_hash']:
                    self.fail('Please contact Student Affairs to verify this item.', 409); return
                self.send_json({'found_id':found_id,'question':row['verification_question'],
                    'at_counter':bool(row['counter_id']),'counter_id':row['counter_id'],
                    'handover_location':row['handover_location']})
            elif re.fullmatch(r'/api/pickups/\d+/security-question', path):
                user=self.auth()
                if not user:return
                request_id=int(path.split('/')[3])
                with db_connect() as con:
                    row=con.execute('''SELECT p.claimant_id,p.status,p.method,i.verification_question
                        FROM pickup_requests p JOIN items i ON i.id=p.found_id WHERE p.id=?''',(request_id,)).fetchone()
                if not row or user['is_staff'] or user['id']!=row['claimant_id'] or row['method']!='meet' or row['status']!='meet_declined':
                    self.fail('This security question is not available.',403);return
                self.send_json({'question':row['verification_question']})
            elif path == '/api/stats':
                with db_connect() as con:
                    n_found = con.execute("SELECT COUNT(*) FROM items WHERE kind='found' AND status='open'").fetchone()[0]
                    n_returned = con.execute("SELECT COUNT(*) FROM items WHERE kind='found' AND status='returned'").fetchone()[0]
                self.send_json({'found': n_found, 'returned': n_returned})
            elif path == '/api/my-found':
                user = self.auth()
                if not user: return
                if user['is_staff']:
                    self.fail('Only students can report found items.', 403); return
                with db_connect() as con:
                    rows = con.execute('''SELECT i.*, u.name AS reporter FROM items i
                        JOIN users u ON u.id=i.user_id
                        WHERE i.kind='found' AND i.user_id=? ORDER BY i.id DESC''',
                        (user['id'],)).fetchall()
                self.send_json({'items': [item_to_dict(r) for r in rows]})
            elif path == '/api/pickups':
                user = self.auth()
                if not user: return
                with db_connect() as con:
                    rows = con.execute('''SELECT p.*, i.name AS item_name, i.category, i.location, i.event_date,
                        i.photo, i.handover_location AS counter_location, i.user_id AS finder_id, finder.name AS finder_name,
                        finder.faculty AS finder_faculty, finder.course AS finder_course,
                        finder.phone AS finder_phone, owner.name AS owner_name
                        FROM pickup_requests p JOIN items i ON i.id=p.found_id
                        JOIN users finder ON finder.id=i.user_id
                        JOIN users owner ON owner.id=p.claimant_id
                        WHERE p.claimant_id=? OR i.user_id=? OR (?=1 AND p.method='counter') ORDER BY p.id DESC''',
                        (user['id'],user['id'],user['is_staff'])).fetchall()
                results=[]
                for r in rows:
                    role = ('staff' if user['is_staff'] and user['id'] not in (r['finder_id'],r['claimant_id'])
                            else ('finder' if user['id']==r['finder_id'] else 'owner'))
                    share_contact=(r['method']=='meet' and r['accepted_at'] is not None and
                        r['status'] not in ('rejected','cancelled') and role=='owner')
                    results.append({
                        'id':r['id'],'found_id':r['found_id'],'item_name':r['item_name'],
                        'category':r['category'],'location':r['location'],'event_date':r['event_date'],
                        'counter_location':r['counter_location'],
                        'photo_url':'/uploads/'+r['photo'] if r['photo'] else None,
                        'finder_name':r['finder_name'],'owner_name':r['owner_name'],
                        'finder_faculty':r['finder_faculty'] if share_contact else None,
                        'finder_course':r['finder_course'] if share_contact else None,
                        'finder_phone':r['finder_phone'] if share_contact else None,
                        'method':r['method'],'status':r['status'],'role':role,
                        'created_at':r['created_at'],'accepted_at':r['accepted_at'],
                        'finder_confirmed_at':r['finder_confirmed_at'],
                        'owner_confirmed_at':r['owner_confirmed_at'],
                        'completed_at':r['completed_at'],'submitted_at':r['submitted_at'],
                        'received_at':r['received_at'],'rejection_note':r['rejection_note']})
                self.send_json({'requests':results})
            elif path == '/favicon.ico':
                self.send_response(204); self.end_headers()
            else:
                self.fail('Page not found.', 404)
        except Exception as exc:
            self.log_message('GET error: %r', exc)
            self.fail('Could not load this page.', 500)

    def serve_file(self, file):
        if not file.is_file():
            self.fail('File not found.', 404)
            return
        body = file.read_bytes()
        ctype = mimetypes.guess_type(str(file))[0] or 'application/octet-stream'
        self.send_response(200)
        self.send_header('Content-Type', ctype + ('; charset=utf-8' if ctype.startswith('text/') or ctype == 'application/javascript' else ''))
        self.send_header('Content-Length', str(len(body)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        path = urlsplit(self.path).path
        try:
            # Deprecated V4 claim creators are disabled: all new requests must use
            # /api/pickups so finder acceptance and counter checks cannot be bypassed.
            if path in ('/api/direct-claims', '/api/claims') or re.fullmatch(
                    r'/api/counter/\d+/claim|/api/counter/items/\d+/submit', path):
                self.fail('This old claim route is no longer supported. Update to CampusBack V6.', 410)
                return
            if path == '/api/register':
                data = self.read_json()
                name = sanitize_field(data.get('name'), 60)
                email = sanitize_field(data.get('email'), 130).lower()
                password = str(data.get('password', ''))
                if len(name) < 2 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email) or len(password) < 8:
                    self.fail('Enter a name, valid email, and password of at least 8 characters.'); return
                with db_connect() as con:
                    try:
                        cur = con.execute('INSERT INTO users(name,email,password_hash,created_at) VALUES(?,?,?,?)',
                                          (name, email, make_hash(password), now()))
                    except sqlite3.IntegrityError:
                        self.fail('An account with this email already exists.', 409); return
                    user_id = cur.lastrowid
                self.send_json({'message': 'Account created.'}, 201, self.start_session(user_id))
            elif path == '/api/login':
                data = self.read_json()
                email = sanitize_field(data.get('email'), 130)
                password = str(data.get('password', ''))
                with db_connect() as con:
                    row = con.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
                if not row or not verify_hash(password, row['password_hash']):
                    self.fail('Email or password is incorrect.', 401); return
                self.send_json({'message': 'Welcome back!'}, 200, self.start_session(row['id']))
            elif path == '/api/logout':
                user = self.auth(check_csrf=True)
                if not user: return
                cookie = SimpleCookie(); cookie.load(self.headers.get('Cookie', ''))
                if COOKIE_NAME in cookie:
                    with db_connect() as con:
                        con.execute('DELETE FROM sessions WHERE token_hash=?',
                            (hashlib.sha256(cookie[COOKIE_NAME].value.encode()).hexdigest(),))
                self.send_json({'message': 'Logged out.'}, cookie=f'{COOKIE_NAME}=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0')
            elif path == '/api/profile':
                user=self.auth(check_csrf=True)
                if not user:return
                data=self.read_json()
                faculty=sanitize_field(data.get('faculty'),100)
                course=sanitize_field(data.get('course'),100)
                phone=sanitize_field(data.get('phone'),35)
                if phone and not re.fullmatch(r'[+0-9 ()-]{7,35}',phone):
                    self.fail('Use a valid contact phone number.');return
                with db_connect() as con:
                    con.execute('UPDATE users SET faculty=?,course=?,phone=? WHERE id=?',
                                (faculty,course,phone,user['id']))
                self.send_json({'message':'Profile updated.'})
            elif path == '/api/pickups':
                user=self.auth(check_csrf=True)
                if not user:return
                data=self.read_json()
                try:found_id=int(data.get('found_id'))
                except (TypeError,ValueError):self.fail('Choose a found item.');return
                method=data.get('method')
                if method not in ('meet','counter'):
                    self.fail('Choose meet finder or collect at counter.');return
                if user['is_staff']:
                    self.fail('Counter staff cannot request student items.',403);return
                with db_connect() as con:
                    item=con.execute("SELECT * FROM items WHERE id=? AND kind='found'",(found_id,)).fetchone()
                    if not item or item['status']!='open':
                        self.fail('This item is no longer available.');return
                    if item['user_id']==user['id']:
                        self.fail('You cannot request an item you posted.',403);return
                    if item['custody']=='counter' and method!='counter':
                        self.fail('This item is already at campus counter. Choose counter collection.',409);return
                    if con.execute('SELECT 1 FROM counter_submissions WHERE found_id=?',(found_id,)).fetchone():
                        self.fail('This item is already managed by an older counter submission.',409);return
                    if method=='counter':
                        attempts=con.execute('SELECT attempts FROM claim_attempts WHERE user_id=? AND found_id=?',
                                             (user['id'],found_id)).fetchone()
                        if attempts and attempts['attempts']>=5:
                            self.fail('Too many incorrect attempts. Please contact Student Affairs.',429);return
                        answer=str(data.get('answer','')).strip()
                        if not answer or not (verify_hash(norm_answer(answer),item['verification_hash'] or '')
                                              or verify_hash(answer,item['verification_hash'] or '')):
                            con.execute('''INSERT INTO claim_attempts(user_id,found_id,attempts)
                                VALUES(?,?,1) ON CONFLICT(user_id,found_id) DO UPDATE SET attempts=attempts+1''',
                                (user['id'],found_id))
                            self.fail('Incorrect answer. Your request was not submitted.',403);return
                    changed=con.execute("UPDATE items SET status='matched' WHERE id=? AND status='open'",(found_id,))
                    if changed.rowcount!=1:
                        self.fail('Someone else requested this item first.',409);return
                    if method=='meet':
                        status='meet_requested'
                    elif item['custody']=='counter':
                        status='counter_ready'  # staff already holds the item
                    else:
                        status='counter_waiting_finder'
                    row=con.execute('''INSERT INTO pickup_requests(found_id,claimant_id,method,status,created_at,received_at)
                        VALUES(?,?,?,?,?,?)''', (found_id,user['id'],method,status,now(),
                        now() if status=='counter_ready' else None))
                self.send_json({'message':'Request sent! Track progress in Pending.', 'request_id':row.lastrowid},201)
            elif re.fullmatch(r'/api/pickups/\d+/(?:accept|reject|cancel|owner-confirm|not-my-item|wait-finder|switch-counter|submit-counter|receive-counter|release-counter|reject-counter)',path):
                user=self.auth(check_csrf=True)
                if not user:return
                req_id=int(path.split('/')[3]);action=path.split('/')[4]
                with db_connect() as con:
                    r=con.execute('''SELECT p.*,i.user_id AS finder_id FROM pickup_requests p
                        JOIN items i ON i.id=p.found_id WHERE p.id=?''',(req_id,)).fetchone()
                    if not r:self.fail('Request not found.',404);return
                    finder=user['id']==r['finder_id'];owner=user['id']==r['claimant_id'];staff=bool(user['is_staff'])
                    status=r['status'];ts=now()
                    if action=='accept':
                        if not finder or r['method']!='meet' or status not in ('meet_requested','meet_waiting'):
                            self.fail('Only the finder can accept a pending meetup.',403);return
                        profile=con.execute('SELECT faculty,course,phone FROM users WHERE id=?',(user['id'],)).fetchone()
                        if not profile['phone']:
                            self.fail('Please add your contact number in My Profile before accepting.',409);return
                        con.execute("UPDATE pickup_requests SET status='meet_accepted',accepted_at=?,rejection_note=NULL WHERE id=?",(ts,req_id))
                        message='Meetup accepted. Your contact details are shared privately with this claimant.'
                    elif action=='reject':
                        if not finder or status not in ('meet_requested','meet_waiting','counter_waiting_finder'):
                            self.fail('Only the finder can decline a request they have not accepted.',403);return
                        data=self.read_json()
                        reason=sanitize_field(data.get('reason'),40)
                        detail=sanitize_field(data.get('detail'),200)
                        options={'not_owner':'Claimant is not the rightful owner',
                                 'not_on_campus':'Finder is not currently on campus',
                                 'schedule_conflict':'Finder is not available at the requested time',
                                 'other':'Other reason'}
                        if reason not in options:
                            self.fail('Please choose a reason for declining.');return
                        if reason=='other' and len(detail)<4:
                            self.fail('Please explain the other reason (at least 4 characters).');return
                        note=options[reason]+((': '+detail) if reason=='other' else '')
                        # No owner: release item. Scheduling issue: let claimant choose to wait or switch method.
                        if r['method']=='meet' and reason!='not_owner':
                            con.execute("UPDATE pickup_requests SET status='meet_declined',rejected_at=?,rejection_note=? WHERE id=?",(ts,note,req_id))
                            message='Meetup declined with reason. Claimant can choose another collection method or wait.'
                        else:
                            con.execute("UPDATE pickup_requests SET status='rejected',rejected_at=?,rejection_note=? WHERE id=?",(ts,note,req_id))
                            con.execute("UPDATE items SET status='open' WHERE id=?",(r['found_id'],))
                            message='Claim rejected. The item is available in Community again.'
                    elif action=='wait-finder':
                        if not owner or status!='meet_declined' or r['method']!='meet':
                            self.fail('Only the claimant can choose to wait for the finder.',403);return
                        con.execute("UPDATE pickup_requests SET status='meet_waiting' WHERE id=?",(req_id,))
                        message='Waiting for the finder. They can accept when they become available.'
                    elif action=='switch-counter':
                        if not owner or status!='meet_declined' or r['method']!='meet':
                            self.fail('Only the claimant can switch a declined meetup to counter collection.',403);return
                        data=self.read_json()
                        answer=norm_answer(data.get('answer',''))
                        item=con.execute('SELECT * FROM items WHERE id=?',(r['found_id'],)).fetchone()
                        attempts=con.execute('SELECT attempts FROM claim_attempts WHERE user_id=? AND found_id=?',
                                             (user['id'],r['found_id'])).fetchone()
                        if attempts and attempts['attempts']>=5:
                            self.fail('Too many incorrect attempts. Please contact Student Affairs.',429);return
                        if not item['verification_hash'] or not verify_hash(answer,item['verification_hash']):
                            con.execute('''INSERT INTO claim_attempts(user_id,found_id,attempts) VALUES(?,?,1)
                                ON CONFLICT(user_id,found_id) DO UPDATE SET attempts=attempts+1''',
                                (user['id'],r['found_id']))
                            self.send_json({'error':'Incorrect security answer. Counter request not created.'},403);return
                        next_status='counter_ready' if item['custody']=='counter' else 'counter_waiting_finder'
                        con.execute('''UPDATE pickup_requests SET method='counter',status=?,received_at=?,
                            accepted_at=NULL,rejection_note=NULL WHERE id=?''',
                            (next_status,ts if next_status=='counter_ready' else None,req_id))
                        message='Counter collection selected. Finder or counter staff will complete the handover.'
                    elif action=='cancel':
                        if not owner or status not in ('meet_requested','meet_accepted','meet_declined','meet_waiting','counter_waiting_finder'):
                            self.fail('This request can no longer be cancelled.',403);return
                        con.execute("UPDATE pickup_requests SET status='cancelled',rejected_at=? WHERE id=?",(ts,req_id))
                        con.execute("UPDATE items SET status='open' WHERE id=?",(r['found_id'],))
                        message='Request cancelled. Item is available in Community again.'
                    elif action=='owner-confirm':
                        # One confirmation only: owner confirms the actual handover. Finder does NOT reconfirm.
                        if not owner or r['method']!='meet' or status!='meet_accepted':
                            self.fail('Only the claimant can confirm an accepted meetup.',403);return
                        con.execute("UPDATE pickup_requests SET owner_confirmed_at=?,status='completed',completed_at=? WHERE id=?",(ts,ts,req_id))
                        con.execute("UPDATE items SET status='returned' WHERE id=?",(r['found_id'],))
                        message='Collection confirmed by owner. Item marked Returned.'
                    elif action=='not-my-item':
                        if not owner or r['method']!='meet' or status!='meet_accepted':
                            self.fail('Only the claimant can mark an accepted meetup as the wrong item.',403);return
                        con.execute("UPDATE pickup_requests SET status='rejected',rejected_at=?,rejection_note=? WHERE id=?",
                                    (ts,'Claimant confirmed this was not their item',req_id))
                        con.execute("UPDATE items SET status='open' WHERE id=?",(r['found_id'],))
                        message='Thanks for checking. Item is available again in Community.'
                    elif action=='submit-counter':
                        if not finder or status!='counter_waiting_finder':
                            self.fail('Only the finder can submit this item.',403);return
                        con.execute("UPDATE pickup_requests SET status='counter_waiting_staff',submitted_at=? WHERE id=?",(ts,req_id))
                        message='Submission recorded. Counter staff must confirm they received the item.'
                    elif action=='receive-counter':
                        if not staff or status!='counter_waiting_staff':
                            self.fail('Only staff can confirm counter receipt.',403);return
                        con.execute("UPDATE pickup_requests SET status='counter_ready',received_at=? WHERE id=?",(ts,req_id))
                        con.execute("UPDATE items SET custody='counter' WHERE id=?",(r['found_id'],))
                        message='Counter receipt confirmed. Owner can now collect with student ID.'
                    elif action=='reject-counter':
                        if not staff or status!='counter_ready':
                            self.fail('Only staff can reject a counter collection claim.',403);return
                        con.execute("UPDATE pickup_requests SET status='rejected',rejected_at=? WHERE id=?",(ts,req_id))
                        con.execute("UPDATE items SET status='open',custody='counter' WHERE id=?",(r['found_id'],))
                        message='Claim rejected. Item remains safely at the counter and is available in Community again.'
                    elif action=='release-counter':
                        if not staff or status!='counter_ready':
                            self.fail('Only staff can confirm collection.',403);return
                        con.execute("UPDATE pickup_requests SET status='completed',completed_at=? WHERE id=?",(ts,req_id))
                        con.execute("UPDATE items SET status='returned' WHERE id=?",(r['found_id'],))
                        message='Collection confirmed. Item marked Returned.'
                    else:
                        self.fail('Unknown action.');return
                self.send_json({'message':message})
            elif path == '/api/items':
                user = self.auth(check_csrf=True)
                if not user: return
                data, files = self.read_form()
                # V6: no Lost report creation, even if a caller tampers with the form.
                if user['is_staff']:
                    self.fail('Counter staff cannot publish found reports.',403); return
                kind = 'found'
                if data.get('kind', 'found') != 'found':
                    self.fail('CampusBack accepts Found Item reports only.',400); return
                name = sanitize_field(data.get('name'), 90)
                category = sanitize_field(data.get('category'))
                color = sanitize_field(data.get('color'), 40)
                location = sanitize_field(data.get('location'))
                event_date = sanitize_field(data.get('event_date'))
                description = sanitize_field(data.get('description'), 800)
                question = sanitize_field(data.get('question'), 160)
                answer = norm_answer(data.get('answer', ''))
                handover = sanitize_field(data.get('handover'))
                if category not in CATEGORIES or location not in LOCATIONS:
                    self.fail('Choose a valid category and location.'); return
                if len(name) < 3 or not color or len(description) < 8:
                    self.fail('Add an item name, colour, and description (at least 8 characters).'); return
                try:
                    event = date.fromisoformat(event_date)
                except ValueError:
                    self.fail('Choose a valid date.'); return
                if event > date.today() or event < date.today() - timedelta(days=365):
                    self.fail('Date must be within the past year and not in the future.'); return
                if not question or not answer or handover not in HANDOVERS:
                    self.fail('Found reports need a private ownership question, answer, and handover location.'); return
                if len(answer) < 1:
                    self.fail('Add a secret verification answer.'); return
                photo = None
                if 'photo' in files:
                    photo = safe_photo(*files['photo'])
                with db_connect() as con:
                    cur = con.execute('''INSERT INTO items(user_id,kind,name,category,color,location,event_date,description,
                        photo,verification_question,verification_hash,handover_location,created_at)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''', (user['id'], kind, name, category, color, location, event_date,
                        description, photo, question, make_hash(answer) if answer else None, handover, now()))
                self.send_json({'message': 'Report posted!', 'id': cur.lastrowid}, 201)
            else:
                self.fail('Page not found.', 404)
        except (ValueError, json.JSONDecodeError) as exc:
            self.fail(str(exc), 400)
        except sqlite3.IntegrityError:
            self.fail('This item is already claimed or cannot be changed.', 409)
        except Exception as exc:
            self.log_message('POST error: %r', exc)
            self.fail('Something went wrong. Please try again.', 500)


def run(port=8000, host='127.0.0.1'):
    init_db()
    with ThreadingHTTPServer((host, port), CampusHandler) as server:
        print(f'\nCampusBack is running at http://localhost:{server.server_port}')
        print('Press Ctrl+C to stop. Data is saved in data/campusback.db.\n')
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print('\nServer stopped.')


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    # Local run stays on 127.0.0.1; hosting platforms (PORT is set) need 0.0.0.0.
    host = os.environ.get('HOST', '0.0.0.0' if 'PORT' in os.environ else '127.0.0.1')
    run(port=port, host=host)
