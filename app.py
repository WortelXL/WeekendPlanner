"""Familie Weekendplanner - Flask + SQLite.

Rollen (via pincode):
  admin   - alles: uitjes aanmaken/verwijderen, pincodes en beveiliging beheren
  planner - uitjes bewerken (planning, locatie, gegevens)
  lezer   - alleen inzien
"""
import os
import secrets
import sqlite3
import time
from datetime import timedelta
from functools import wraps

from flask import Flask, g, jsonify, request, send_from_directory, session
from werkzeug.security import check_password_hash, generate_password_hash

DATA_DIR = os.environ.get("DATA_DIR", "/data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "weekend.db")
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

ROLES = ("admin", "planner", "lezer")
RANK = {"lezer": 1, "planner": 2, "admin": 3}

EVENT_FIELDS = ["title", "start_date", "end_date", "description", "emoji",
                "location_name", "address", "location_notes", "details"]
PLAN_FIELDS = ["day", "time_start", "time_end", "activity", "who", "notes"]
CONTACT_FIELDS = ["name", "role", "phone", "email", "notes"]


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
    return {"ok": True}


# ---------------------------------------------------------------- login
@app.get("/api/me")
def me():
    role = session.get("role")
    if role not in RANK or session.get("ver") != get_setting(f"pinver_{role}", "0"):
        role = None
    return jsonify(role=role, title=get_setting("title", "Familieweekend"),
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
        "SELECT e.id, e.title, e.start_date, e.end_date, e.description, e.emoji, e.location_name, "
        "(SELECT COUNT(*) FROM planning p WHERE p.event_id=e.id) AS items "
        "FROM events e ORDER BY CASE WHEN e.start_date='' THEN 1 ELSE 0 END, e.start_date, e.id"
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.post("/api/events")
@require("admin")
def create_event():
    data = pick(body(), EVENT_FIELDS)
    if not data.get("title", "").strip():
        return err("Geef het uitje een naam.")
    data.setdefault("emoji", "🏕️")
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
    return jsonify(ev)


@app.put("/api/events/<int:event_id>")
@require("planner")
def update_event(event_id):
    if not event_or_404(event_id):
        return err("Uitje niet gevonden.", 404)
    data = pick(body(), EVENT_FIELDS)
    if "title" in data and not data["title"].strip():
        return err("De naam mag niet leeg zijn.")
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
