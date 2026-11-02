"""Familie Weekendplanner - Flask + SQLite.

Rollen (via pincode):
  admin   - alles: uitjes aanmaken/verwijderen, pincodes en beveiliging beheren
  planner - uitjes bewerken (planning, locatie, gegevens)
  lezer   - alleen inzien
"""
import mimetypes
import os
import re
import secrets
import shutil
import uuid
import sqlite3
import time
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, g, jsonify, request, send_file, send_from_directory, session
from werkzeug.security import check_password_hash, generate_password_hash

DATA_DIR = os.environ.get("DATA_DIR", "/data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "weekend.db")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "25"))
# deze types mogen in de browser geopend worden; al het andere wordt als download aangeboden
INLINE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp", "application/pdf",
                "text/plain", "video/mp4", "audio/mpeg"}
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
try:
    with open(os.path.join(BASE_DIR, "VERSION")) as _f:
        VERSION = _f.read().strip()
except OSError:
    VERSION = "dev"

ROLES = ("admin", "planner", "lezer")
RANK = {"lezer": 1, "planner": 2, "admin": 3}

STATUSES = ("concept", "gepland", "gaande")
TABS = ("planning", "dag", "locatie", "gegevens", "aanwezig", "bijlagen")
CUSTOM_KINDS = ("tekst", "lijst", "checklist")
EVENT_FIELDS = ["title", "status", "hidden_tabs", "start_date", "end_date", "description", "emoji",
                "location_name", "address", "location_notes", "details"]
PLAN_FIELDS = ["day", "time_start", "time_end", "activity", "who", "notes"]
CONTACT_FIELDS = ["name", "role", "phone", "email", "notes"]
ATTENDEE_FIELDS = ["name", "notes"]


def _secret_key():
    if os.environ.get("SECRET_KEY"):
        return os.environ["SECRET_KEY"]
    path = os.path.join(DATA_DIR, "secret.key")
    if os.path.exists(path):
        with open(path) as f:
            return f.read().strip()
    key = secrets.token_hex(32)
    with open(path, "w") as f:
        f.write(key)
    return key


app = Flask(__name__, static_folder=None)
app.config.update(
    SECRET_KEY=_secret_key(),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "0") == "1",
    MAX_CONTENT_LENGTH=MAX_UPLOAD_MB * 1024 * 1024,
    PERMANENT_SESSION_LIFETIME=timedelta(hours=int(os.environ.get("SESSION_HOURS", "12"))),
)

if os.environ.get("BEHIND_PROXY", "0") == "1":
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS attempts (
    ip TEXT PRIMARY KEY,
    fails INTEGER NOT NULL DEFAULT 0,
    locked_until REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    status TEXT DEFAULT 'concept',
    hidden_tabs TEXT DEFAULT '',
    start_date TEXT DEFAULT '',
    end_date TEXT DEFAULT '',
    description TEXT DEFAULT '',
    emoji TEXT DEFAULT '🏕️',
    location_name TEXT DEFAULT '',
    address TEXT DEFAULT '',
    location_notes TEXT DEFAULT '',
    details TEXT DEFAULT '',
    created_at REAL,
    updated_at REAL
);
CREATE TABLE IF NOT EXISTS planning (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    day TEXT DEFAULT '',
    time_start TEXT DEFAULT '',
    time_end TEXT DEFAULT '',
    activity TEXT NOT NULL,
    who TEXT DEFAULT '',
    notes TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS event_days (
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    day TEXT NOT NULL,
    title TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    PRIMARY KEY (event_id, day)
);
CREATE TABLE IF NOT EXISTS attendees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    notes TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS custom_tabs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    emoji TEXT DEFAULT '📌',
    kind TEXT NOT NULL DEFAULT 'tekst',
    content TEXT DEFAULT '',
    sort INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS custom_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tab_id INTEGER NOT NULL REFERENCES custom_tabs(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    notes TEXT DEFAULT '',
    done INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    stored TEXT NOT NULL,
    mime TEXT DEFAULT 'application/octet-stream',
    size INTEGER DEFAULT 0,
    description TEXT DEFAULT '',
    uploaded_at REAL
);
CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    role TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    email TEXT DEFAULT '',
    notes TEXT DEFAULT ''
);
"""


# ---------------------------------------------------------------- database
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH, timeout=10)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def get_setting(key, default=None):
    row = get_db().execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key, value):
    db = get_db()
    db.execute("INSERT INTO settings(key, value) VALUES(?, ?) "
               "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))
    db.commit()


def init_db():
    with app.app_context():
        db = get_db()
        db.executescript("PRAGMA journal_mode=WAL;" + SCHEMA)
        # migratie: status-kolom voor bestaande databases
        cols = [r["name"] for r in db.execute("PRAGMA table_info(events)")]
        if "status" not in cols:
            db.execute("ALTER TABLE events ADD COLUMN status TEXT DEFAULT 'gepland'")
        if "hidden_tabs" not in cols:
            db.execute("ALTER TABLE events ADD COLUMN hidden_tabs TEXT DEFAULT ''")
        db.commit()
        defaults = {"max_attempts": "5", "lockout_minutes": "10", "title": "Familieweekend"}
        for k, v in defaults.items():
            if get_setting(k) is None:
                set_setting(k, v)
        if get_setting("pin_admin") is None:
            pin = os.environ.get("ADMIN_PIN", "1234")
            set_setting("pin_admin", generate_password_hash(pin))
            set_setting("admin_default", "1" if pin == "1234" else "0")


init_db()


# ---------------------------------------------------------------- helpers
def err(message, status=400, code="error", **extra):
    return jsonify(error=code, message=message, **extra), status


def body():
    return request.get_json(silent=True) or {}


def pick(data, fields):
    return {k: str(data.get(k) or "")[:10000] for k in fields if k in data}


def client_ip():
    return request.remote_addr or "onbekend"


def pin_owner(pin, exclude=None):
    """Geeft de rol terug waarvan deze pincode is, of None."""
    for r in ROLES:
        if r == exclude:
            continue
        h = get_setting(f"pin_{r}")
        if h and check_password_hash(h, pin):
            return r
    return None


def require(min_role):
    def deco(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            role = session.get("role")
            if role not in RANK or session.get("ver") != get_setting(f"pinver_{role}", "0"):
                session.clear()
                return err("Log opnieuw in met je pincode.", 401, "auth")
            if RANK[role] < RANK[min_role]:
                return err("Je hebt hier geen rechten voor.", 403, "forbidden")
            g.role = role
            return f(*args, **kwargs)
        return wrapper
    return deco


def valid_status(data):
    """Controleert status en normaliseert hidden_tabs (komma-lijst van TABS)."""
    if "status" in data and data["status"] not in STATUSES:
        return False
    if "hidden_tabs" in data:
        parts = [t.strip() for t in data["hidden_tabs"].split(",") if t.strip()]
        if any(t not in TABS and not re.fullmatch(r"c\d+", t) for t in parts):
            return False
        custom = [t for t in dict.fromkeys(parts) if t not in TABS]
        data["hidden_tabs"] = ",".join([t for t in TABS if t in parts] + custom)
    return True


def hidden_for_reader(ev):
    """Tabbladen die verborgen zijn voor lezers (planner/admin zien alles)."""
    if g.get("role") != "lezer":
        return set()
    return {t for t in (ev.get("hidden_tabs") or "").split(",") if t}


def event_or_404(event_id):
    row = get_db().execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
    return dict(row) if row else None


@app.after_request
def security_headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "same-origin"
    if request.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


# ---------------------------------------------------------------- pagina
@app.get("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.get("/health")
def health():
    return {"ok": True, "version": VERSION}


# ---------------------------------------------------------------- login
@app.get("/api/me")
def me():
    role = session.get("role")
    if role not in RANK or session.get("ver") != get_setting(f"pinver_{role}", "0"):
        role = None
    return jsonify(role=role, title=get_setting("title", "Familieweekend"), version=VERSION,
                   max_upload_mb=MAX_UPLOAD_MB,
                   admin_default=(role == "admin" and get_setting("admin_default") == "1"))


@app.post("/api/login")
def login():
    db = get_db()
    ip = client_ip()
    now = time.time()
    row = db.execute("SELECT fails, locked_until FROM attempts WHERE ip=?", (ip,)).fetchone()
    if row and row["locked_until"] > now:
        secs = int(row["locked_until"] - now) + 1
        return err("Te veel foute pogingen. Pincode is tijdelijk vergrendeld.", 423, "locked",
                   seconds=secs)

    pin = str(body().get("pin", "")).strip()
    role = pin_owner(pin) if pin.isdigit() else None

    if role:
        db.execute("DELETE FROM attempts WHERE ip=?", (ip,))
        db.commit()
        session.clear()
        session.permanent = True
        session["role"] = role
        session["ver"] = get_setting(f"pinver_{role}", "0")
        return jsonify(role=role)

    max_attempts = int(get_setting("max_attempts", "5"))
    lock_minutes = int(get_setting("lockout_minutes", "10"))
    # na een verlopen vergrendeling opnieuw beginnen met tellen
    fails = 0 if (row is None or row["locked_until"] > 0) else row["fails"]
    fails += 1
    locked_until = now + lock_minutes * 60 if fails >= max_attempts else 0
    db.execute("INSERT INTO attempts(ip, fails, locked_until) VALUES(?,?,?) "
               "ON CONFLICT(ip) DO UPDATE SET fails=excluded.fails, locked_until=excluded.locked_until",
               (ip, fails, locked_until))
    db.commit()
    if locked_until:
        return err(f"Te veel foute pogingen. Vergrendeld voor {lock_minutes} minuten.", 423,
                   "locked", seconds=lock_minutes * 60)
    return err("Onjuiste pincode.", 401, "wrong", remaining=max_attempts - fails)


@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify(ok=True)


# ---------------------------------------------------------------- uitjes
@app.get("/api/events")
@require("lezer")
def list_events():
    rows = get_db().execute(
        "SELECT e.id, e.title, e.status, e.hidden_tabs, e.start_date, e.end_date, e.description, e.emoji, "
        "e.location_name, (SELECT COUNT(*) FROM planning p WHERE p.event_id=e.id) AS items, "
        "(SELECT COUNT(*) FROM attendees a WHERE a.event_id=e.id) AS attendees "
        "FROM events e ORDER BY CASE WHEN e.start_date='' THEN 1 ELSE 0 END, e.start_date, e.id"
    ).fetchall()
    out = []
    for r in rows:
        ev = dict(r)
        hidden = hidden_for_reader(ev)
        if "locatie" in hidden:
            ev["location_name"] = ""
        if {"planning", "dag"} <= hidden:
            ev["items"] = None
        if "aanwezig" in hidden:
            ev["attendees"] = None
        out.append(ev)
    return jsonify(out)


@app.post("/api/events")
@require("admin")
def create_event():
    data = pick(body(), EVENT_FIELDS)
    if not data.get("title", "").strip():
        return err("Geef het uitje een naam.")
    if not valid_status(data):
        return err("Ongeldige status.")
    data.setdefault("emoji", "🏕️")
    data.setdefault("status", "concept")
    now = time.time()
    cols = list(data.keys()) + ["created_at", "updated_at"]
    vals = list(data.values()) + [now, now]
    db = get_db()
    cur = db.execute(f"INSERT INTO events({','.join(cols)}) VALUES({','.join('?' * len(cols))})", vals)
    db.commit()
    return jsonify(id=cur.lastrowid), 201


@app.get("/api/events/<int:event_id>")
@require("lezer")
def get_event(event_id):
    ev = event_or_404(event_id)
    if not ev:
        return err("Uitje niet gevonden.", 404)
    db = get_db()
    ev["planning"] = [dict(r) for r in db.execute(
        "SELECT * FROM planning WHERE event_id=? ORDER BY CASE WHEN day='' THEN 1 ELSE 0 END, day, "
        "CASE WHEN time_start='' THEN 1 ELSE 0 END, time_start, id", (event_id,))]
    ev["contacts"] = [dict(r) for r in db.execute(
        "SELECT * FROM contacts WHERE event_id=? ORDER BY id", (event_id,))]
    ev["days"] = {r["day"]: {"title": r["title"], "notes": r["notes"]} for r in db.execute(
        "SELECT day, title, notes FROM event_days WHERE event_id=?", (event_id,))}
    ev["attendees"] = [dict(r) for r in db.execute(
        "SELECT * FROM attendees WHERE event_id=? ORDER BY name COLLATE NOCASE, id", (event_id,))]
    tabs = [dict(r) for r in db.execute(
        "SELECT * FROM custom_tabs WHERE event_id=? ORDER BY sort, id", (event_id,))]
    for t in tabs:
        t["items"] = [dict(r) for r in db.execute(
            "SELECT * FROM custom_items WHERE tab_id=? ORDER BY done, id", (t["id"],))]
    ev["custom_tabs"] = tabs
    ev["attachments"] = [dict(r) for r in db.execute(
        "SELECT id, filename, mime, size, description, uploaded_at FROM attachments "
        "WHERE event_id=? ORDER BY uploaded_at DESC, id DESC", (event_id,))]
    # verborgen tabbladen: gegevens niet meesturen naar lezers
    hidden = hidden_for_reader(ev)
    ev["custom_tabs"] = [t for t in tabs if f"c{t['id']}" not in hidden]
    if "bijlagen" in hidden:
        ev["attachments"] = []
    if {"planning", "dag"} <= hidden:
        ev["planning"] = []
    if "dag" in hidden:
        ev["days"] = {}
    if "locatie" in hidden:
        ev.update(location_name="", address="", location_notes="")
    if "gegevens" in hidden:
        ev.update(contacts=[], details="")
    if "aanwezig" in hidden:
        ev["attendees"] = []
    return jsonify(ev)


@app.put("/api/events/<int:event_id>/days/<day>")
@require("planner")
def update_day(event_id, day):
    """Titel/thema en notities van één dag (dagplanning)."""
    if not event_or_404(event_id):
        return err("Uitje niet gevonden.", 404)
    try:
        datetime.strptime(day, "%Y-%m-%d")
    except ValueError:
        return err("Ongeldige datum.")
    d = body()
    title = str(d.get("title") or "")[:200]
    notes = str(d.get("notes") or "")[:10000]
    db = get_db()
    db.execute("INSERT INTO event_days(event_id, day, title, notes) VALUES(?,?,?,?) "
               "ON CONFLICT(event_id, day) DO UPDATE SET title=excluded.title, notes=excluded.notes",
               (event_id, day, title, notes))
    _touch(event_id)
    db.commit()
    return jsonify(ok=True)


@app.put("/api/events/<int:event_id>")
@require("planner")
def update_event(event_id):
    if not event_or_404(event_id):
        return err("Uitje niet gevonden.", 404)
    data = pick(body(), EVENT_FIELDS)
    if "hidden_tabs" in data and g.role != "admin":
        return err("Alleen de admin kan de zichtbaarheid van tabbladen wijzigen.", 403, "forbidden")
    if "title" in data and not data["title"].strip():
        return err("De naam mag niet leeg zijn.")
    if not valid_status(data):
        return err("Ongeldige status.")
    if not data:
        return jsonify(ok=True)
    data["updated_at"] = time.time()
    sets = ", ".join(f"{k}=?" for k in data)
    db = get_db()
    db.execute(f"UPDATE events SET {sets} WHERE id=?", list(data.values()) + [event_id])
    db.commit()
    return jsonify(ok=True)


@app.delete("/api/events/<int:event_id>")
@require("admin")
def delete_event(event_id):
    db = get_db()
    db.execute("DELETE FROM events WHERE id=?", (event_id,))
    db.commit()
    shutil.rmtree(os.path.join(UPLOAD_DIR, str(event_id)), ignore_errors=True)
    return jsonify(ok=True)


def _touch(event_id):
    get_db().execute("UPDATE events SET updated_at=? WHERE id=?", (time.time(), event_id))


def _child_routes(table, fields, required, required_msg):
    """Maakt CRUD-routes voor planning/contacts."""

    @require("planner")
    def create(event_id):
        if not event_or_404(event_id):
            return err("Uitje niet gevonden.", 404)
        data = pick(body(), fields)
        if not data.get(required, "").strip():
            return err(required_msg)
        cols = ["event_id"] + list(data.keys())
        db = get_db()
        cur = db.execute(f"INSERT INTO {table}({','.join(cols)}) VALUES({','.join('?' * len(cols))})",
                         [event_id] + list(data.values()))
        _touch(event_id)
        db.commit()
        return jsonify(id=cur.lastrowid), 201

    @require("planner")
    def update(item_id):
        db = get_db()
        row = db.execute(f"SELECT event_id FROM {table} WHERE id=?", (item_id,)).fetchone()
        if not row:
            return err("Niet gevonden.", 404)
        data = pick(body(), fields)
        if required in data and not data[required].strip():
            return err(required_msg)
        if data:
            sets = ", ".join(f"{k}=?" for k in data)
            db.execute(f"UPDATE {table} SET {sets} WHERE id=?", list(data.values()) + [item_id])
            _touch(row["event_id"])
            db.commit()
        return jsonify(ok=True)

    @require("planner")
    def delete(item_id):
        db = get_db()
        row = db.execute(f"SELECT event_id FROM {table} WHERE id=?", (item_id,)).fetchone()
        if row:
            db.execute(f"DELETE FROM {table} WHERE id=?", (item_id,))
            _touch(row["event_id"])
            db.commit()
        return jsonify(ok=True)

    app.add_url_rule(f"/api/events/<int:event_id>/{table}", f"{table}_create", create, methods=["POST"])
    app.add_url_rule(f"/api/{table}/<int:item_id>", f"{table}_update", update, methods=["PUT"])
    app.add_url_rule(f"/api/{table}/<int:item_id>", f"{table}_delete", delete, methods=["DELETE"])


_child_routes("planning", PLAN_FIELDS, "activity", "Vul een activiteit in.")
_child_routes("contacts", CONTACT_FIELDS, "name", "Vul een naam in.")
_child_routes("attendees", ATTENDEE_FIELDS, "name", "Vul een naam in.")


# ---------------------------------------------------------------- eigen tabbladen
def _tab(tab_id):
    row = get_db().execute("SELECT * FROM custom_tabs WHERE id=?", (tab_id,)).fetchone()
    return dict(row) if row else None


@app.post("/api/events/<int:event_id>/tabs")
@require("admin")
def create_tab(event_id):
    if not event_or_404(event_id):
        return err("Uitje niet gevonden.", 404)
    d = body()
    title = str(d.get("title") or "").strip()[:40]
    kind = d.get("kind", "tekst")
    if not title:
        return err("Geef het tabblad een naam.")
    if kind not in CUSTOM_KINDS:
        return err("Onbekend soort tabblad.")
    db = get_db()
    sort = db.execute("SELECT COALESCE(MAX(sort), 0) + 1 FROM custom_tabs WHERE event_id=?",
                      (event_id,)).fetchone()[0]
    cur = db.execute("INSERT INTO custom_tabs(event_id, title, emoji, kind, sort) VALUES(?,?,?,?,?)",
                     (event_id, title, str(d.get("emoji") or "📌")[:8], kind, sort))
    _touch(event_id)
    db.commit()
    return jsonify(id=cur.lastrowid), 201


@app.put("/api/tabs/<int:tab_id>")
@require("planner")
def update_tab(tab_id):
    t = _tab(tab_id)
    if not t:
        return err("Tabblad niet gevonden.", 404)
    d = body()
    # naam, pictogram en soort beheert alleen de admin; de inhoud (tekst) mag de planner bewerken
    if any(k in d for k in ("title", "emoji", "kind")) and g.role != "admin":
        return err("Alleen de admin kan tabbladen beheren.", 403, "forbidden")
    data = {}
    if "title" in d:
        data["title"] = str(d["title"] or "").strip()[:40]
        if not data["title"]:
            return err("De naam mag niet leeg zijn.")
    if "emoji" in d:
        data["emoji"] = str(d["emoji"] or "📌")[:8]
    if "content" in d:
        data["content"] = str(d["content"] or "")[:50000]
    if "kind" in d:
        if d["kind"] not in CUSTOM_KINDS:
            return err("Onbekend soort tabblad.")
        data["kind"] = d["kind"]
    if data:
        db = get_db()
        db.execute(f"UPDATE custom_tabs SET {', '.join(f'{k}=?' for k in data)} WHERE id=?",
                   list(data.values()) + [tab_id])
        _touch(t["event_id"])
        db.commit()
    return jsonify(ok=True)


@app.post("/api/tabs/<int:tab_id>/move")
@require("admin")
def move_tab(tab_id):
    """Verplaats een eigen tabblad naar links (-1) of rechts (+1)."""
    t = _tab(tab_id)
    if not t:
        return err("Tabblad niet gevonden.", 404)
    step = -1 if int(body().get("dir", 1)) < 0 else 1
    db = get_db()
    ids = [r["id"] for r in db.execute(
        "SELECT id FROM custom_tabs WHERE event_id=? ORDER BY sort, id", (t["event_id"],))]
    i = ids.index(tab_id)
    j = i + step
    if 0 <= j < len(ids):
        ids[i], ids[j] = ids[j], ids[i]
        for n, tid in enumerate(ids):
            db.execute("UPDATE custom_tabs SET sort=? WHERE id=?", (n, tid))
        db.commit()
    return jsonify(ok=True)


@app.delete("/api/tabs/<int:tab_id>")
@require("admin")
def delete_tab(tab_id):
    t = _tab(tab_id)
    if t:
        db = get_db()
        db.execute("DELETE FROM custom_tabs WHERE id=?", (tab_id,))
        _touch(t["event_id"])
        db.commit()
    return jsonify(ok=True)


@app.post("/api/tabs/<int:tab_id>/items")
@require("planner")
def create_item(tab_id):
    t = _tab(tab_id)
    if not t:
        return err("Tabblad niet gevonden.", 404)
    d = body()
    title = str(d.get("title") or "").strip()[:500]
    if not title:
        return err("Vul een omschrijving in.")
    db = get_db()
    cur = db.execute("INSERT INTO custom_items(tab_id, title, notes, done) VALUES(?,?,?,?)",
                     (tab_id, title, str(d.get("notes") or "")[:5000], 1 if d.get("done") else 0))
    _touch(t["event_id"])
    db.commit()
    return jsonify(id=cur.lastrowid), 201


def _item_event(item_id):
    return get_db().execute(
        "SELECT t.event_id FROM custom_items i JOIN custom_tabs t ON t.id=i.tab_id WHERE i.id=?",
        (item_id,)).fetchone()


@app.put("/api/items/<int:item_id>")
@require("planner")
def update_item(item_id):
    row = _item_event(item_id)
    if not row:
        return err("Niet gevonden.", 404)
    d = body()
    data = {}
    if "title" in d:
        data["title"] = str(d["title"] or "").strip()[:500]
        if not data["title"]:
            return err("Vul een omschrijving in.")
    if "notes" in d:
        data["notes"] = str(d["notes"] or "")[:5000]
    if "done" in d:
        data["done"] = 1 if d["done"] else 0
    if data:
        db = get_db()
        db.execute(f"UPDATE custom_items SET {', '.join(f'{k}=?' for k in data)} WHERE id=?",
                   list(data.values()) + [item_id])
        _touch(row["event_id"])
        db.commit()
    return jsonify(ok=True)


@app.delete("/api/items/<int:item_id>")
@require("planner")
def delete_item(item_id):
    row = _item_event(item_id)
    if row:
        db = get_db()
        db.execute("DELETE FROM custom_items WHERE id=?", (item_id,))
        _touch(row["event_id"])
        db.commit()
    return jsonify(ok=True)


# ---------------------------------------------------------------- bijlagen
@app.errorhandler(413)
def too_large(_e):
    return err(f"Bestand(en) te groot. Maximaal {MAX_UPLOAD_MB} MB per keer.", 413, "too_large")


def _clean_name(name):
    name = os.path.basename(str(name or "").replace("\\", "/")).strip()
    name = re.sub(r"[\x00-\x1f\x7f]", "", name)[:150]
    return name or "bestand"


@app.post("/api/events/<int:event_id>/attachments")
@require("planner")
def upload_attachments(event_id):
    if not event_or_404(event_id):
        return err("Uitje niet gevonden.", 404)
    files = [f for f in request.files.getlist("files") if f and f.filename]
    if not files:
        return err("Kies minimaal één bestand.")
    desc = str(request.form.get("description") or "")[:1000]
    folder = os.path.join(UPLOAD_DIR, str(event_id))
    os.makedirs(folder, exist_ok=True)
    db = get_db()
    ids = []
    for f in files:
        name = _clean_name(f.filename)
        mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
        stored = uuid.uuid4().hex
        path = os.path.join(folder, stored)
        f.save(path)
        cur = db.execute(
            "INSERT INTO attachments(event_id, filename, stored, mime, size, description, uploaded_at) "
            "VALUES(?,?,?,?,?,?,?)",
            (event_id, name, stored, mime, os.path.getsize(path), desc, time.time()))
        ids.append(cur.lastrowid)
    _touch(event_id)
    db.commit()
    return jsonify(ids=ids), 201


def _attachment(att_id):
    row = get_db().execute("SELECT * FROM attachments WHERE id=?", (att_id,)).fetchone()
    return dict(row) if row else None


@app.get("/api/attachments/<int:att_id>")
@require("lezer")
def download_attachment(att_id):
    a = _attachment(att_id)
    ev = event_or_404(a["event_id"]) if a else None
    if not a or not ev or "bijlagen" in hidden_for_reader(ev):
        return err("Bijlage niet gevonden.", 404)
    path = os.path.join(UPLOAD_DIR, str(a["event_id"]), a["stored"])
    if not os.path.isfile(path):
        return err("Bestand ontbreekt op de server.", 404)
    inline = a["mime"] in INLINE_TYPES and request.args.get("download") != "1"
    resp = send_file(path, mimetype=a["mime"], as_attachment=not inline,
                     download_name=a["filename"], conditional=True, max_age=0)
    # geüploade bestanden nooit als actieve pagina laten draaien
    resp.headers["Content-Security-Policy"] = "default-src 'none'; img-src 'self'; media-src 'self'; " \
                                              "style-src 'unsafe-inline'; sandbox"
    resp.headers["Cache-Control"] = "private, no-store"
    return resp


@app.put("/api/attachments/<int:att_id>")
@require("planner")
def update_attachment(att_id):
    a = _attachment(att_id)
    if not a:
        return err("Bijlage niet gevonden.", 404)
    d = body()
    data = {}
    if "description" in d:
        data["description"] = str(d["description"] or "")[:1000]
    if "filename" in d:
        data["filename"] = _clean_name(d["filename"])
    if data:
        db = get_db()
        db.execute(f"UPDATE attachments SET {', '.join(f'{k}=?' for k in data)} WHERE id=?",
                   list(data.values()) + [att_id])
        db.commit()
    return jsonify(ok=True)


@app.delete("/api/attachments/<int:att_id>")
@require("planner")
def delete_attachment(att_id):
    a = _attachment(att_id)
    if a:
        db = get_db()
        db.execute("DELETE FROM attachments WHERE id=?", (att_id,))
        _touch(a["event_id"])
        db.commit()
        try:
            os.remove(os.path.join(UPLOAD_DIR, str(a["event_id"]), a["stored"]))
        except OSError:
            pass
    return jsonify(ok=True)


# ---------------------------------------------------------------- admin
@app.get("/api/admin/settings")
@require("admin")
def admin_settings():
    now = time.time()
    locks = [dict(r) for r in get_db().execute(
        "SELECT ip, fails, locked_until FROM attempts WHERE locked_until>? OR fails>0 "
        "ORDER BY locked_until DESC", (now,))]
    for l in locks:
        l["seconds"] = max(0, int(l["locked_until"] - now))
    return jsonify(
        pins={r: bool(get_setting(f"pin_{r}")) for r in ROLES},
        max_attempts=int(get_setting("max_attempts", "5")),
        lockout_minutes=int(get_setting("lockout_minutes", "10")),
        title=get_setting("title", "Familieweekend"),
        admin_default=get_setting("admin_default") == "1",
        locks=locks,
    )


@app.put("/api/admin/settings")
@require("admin")
def update_settings():
    d = body()
    try:
        if "max_attempts" in d:
            v = int(d["max_attempts"])
            if not 1 <= v <= 50:
                return err("Aantal pogingen moet tussen 1 en 50 liggen.")
            set_setting("max_attempts", v)
        if "lockout_minutes" in d:
            v = int(d["lockout_minutes"])
            if not 1 <= v <= 1440:
                return err("Vergrendeltijd moet tussen 1 en 1440 minuten liggen.")
            set_setting("lockout_minutes", v)
    except (TypeError, ValueError):
        return err("Vul geldige getallen in.")
    if "title" in d:
        title = str(d["title"]).strip()[:80]
        if not title:
            return err("De titel mag niet leeg zijn.")
        set_setting("title", title)
    return jsonify(ok=True)


@app.put("/api/admin/pin")
@require("admin")
def set_pin():
    d = body()
    role = d.get("role")
    pin = str(d.get("pin", "")).strip()
    if role not in ROLES:
        return err("Onbekende rol.")
    if not (pin.isdigit() and 4 <= len(pin) <= 8):
        return err("Een pincode bestaat uit 4 t/m 8 cijfers.")
    if pin_owner(pin, exclude=role):
        return err("Deze pincode is al in gebruik voor een andere rol. Kies een andere.")
    set_setting(f"pin_{role}", generate_password_hash(pin))
    new_ver = str(int(get_setting(f"pinver_{role}", "0")) + 1)
    set_setting(f"pinver_{role}", new_ver)  # bestaande sessies van deze rol worden uitgelogd
    if role == "admin":
        set_setting("admin_default", "0")
        session["ver"] = new_ver  # huidige admin blijft ingelogd
    return jsonify(ok=True)


@app.delete("/api/admin/pin/<role>")
@require("admin")
def remove_pin(role):
    if role not in ("planner", "lezer"):
        return err("De admin-pincode kan niet verwijderd worden.")
    db = get_db()
    db.execute("DELETE FROM settings WHERE key=?", (f"pin_{role}",))
    db.commit()
    set_setting(f"pinver_{role}", str(int(get_setting(f"pinver_{role}", "0")) + 1))
    return jsonify(ok=True)


@app.delete("/api/admin/locks")
@require("admin")
def clear_locks():
    db = get_db()
    db.execute("DELETE FROM attempts")
    db.commit()
    return jsonify(ok=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "80")))
