"""Διαχείριση: σελίδες μόνο για διαχειριστές, μέσα στην ίδια εφαρμογή (χωρίς ξεχωριστή διεργασία).

Ο διαχειριστής διαχειρίζεται λογαριασμούς, όχι δεδομένα: οι βάρδιες και τα ποσά κάθε χρήστη δεν εμφανίζονται εδώ.

Κάθε σελίδα φέρνει μόνο τις στήλες και τις γραμμές που δείχνει (σελιδοποίηση, φίλτρα στη βάση).
Ο ρόλος διαχειριστή δίνεται μόνο από τη γραμμή εντολών (flask --app app set-admin), ποτέ από εδώ.
"""
import os
import re
import sqlite3
import sys
import platform
import secrets
import time
from datetime import datetime, timedelta
from importlib.metadata import version, PackageNotFoundError
from flask import Blueprint, render_template, request, redirect, url_for, flash, g, abort
from werkzeug.security import generate_password_hash
import core

bp = Blueprint("admin", __name__, url_prefix="/admin")

STARTED_AT = time.time()
PER_PAGE = 25
DISK_QUOTA = 512 * 1024 * 1024  # Δωρεάν λογαριασμός PythonAnywhere
INVITE_RE = re.compile(r"^\S{4,64}$")

# Ετικέτα και χρώμα για κάθε είδος γεγονότος
ACTIONS = {
    "login": ("Σύνδεση", "blue"),
    "login_failed": ("Αποτυχία σύνδεσης", "orange"),
    "login_locked": ("Παύση συνδέσεων (πολλές αποτυχίες)", "red"),
    "password_changed": ("Αλλαγή κωδικού", "purple"),
    "register": ("Νέος λογαριασμός", "green"),
    "admin.reset_password": ("Νέος προσωρινός κωδικός", "purple"),
    "admin.disable": ("Απενεργοποίηση χρήστη", "orange"),
    "admin.enable": ("Ενεργοποίηση χρήστη", "green"),
    "admin.delete_user": ("Διαγραφή χρήστη", "red"),
    "admin.settings": ("Αλλαγή ρυθμίσεων", "indigo"),
    "cli.set_admin": ("Νέος διαχειριστής (console)", "indigo"),
    "cli.revoke_admin": ("Αφαίρεση διαχειριστή (console)", "indigo"),
    "cli.reset_password": ("Αλλαγή κωδικού (console)", "purple"),
    "error": ("Σφάλμα", "red"),
}
ACTIVITY_KINDS = {
    "": ("Όλα", None),
    "auth": ("Συνδέσεις", "action IN ('login', 'login_failed', 'login_locked', 'register', 'password_changed')"),
    "admin": ("Διαχείριση", "(action LIKE 'admin.%' OR action LIKE 'cli.%')"),
    "error": ("Σφάλματα", "action = 'error'"),
}
USER_SORTS = {
    "new": ("Νεότεροι", "u.id DESC"),
    "name": ("Όνομα", "u.username COLLATE NOCASE"),
    "login": ("Τελευταία σύνδεση", "u.last_login_at IS NULL, u.last_login_at DESC"),
}
USER_FILTERS = {
    "": ("Όλοι", ""),
    "admin": ("Διαχειριστές", "AND u.is_admin = 1"),
    "disabled": ("Απενεργοποιημένοι", "AND u.disabled = 1"),
}


@bp.before_request
def require_admin():
    # Η σύνδεση ελέγχεται ήδη στο app.load_user· εδώ ο ρόλος. Οι υπόλοιποι βλέπουν 404, σαν να μην υπάρχει.
    if g.user is None or not g.user["is_admin"]:
        abort(404)


@bp.after_request
def no_store(response):
    response.headers["Cache-Control"] = "no-store"
    return response


@bp.app_template_filter("when")
def format_when(value):
    """'2026-10-13T14:05:09+03:00' -> '13/10/2026 14:05'"""
    if not value:
        return "—"
    try:
        return datetime.fromisoformat(value).strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return value


@bp.app_template_filter("size")
def format_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


# --- Βοηθητικά ---

def query(sql, params=(), one=False):
    conn = core.connect()
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(sql, params)
        return cur.fetchone() if one else cur.fetchall()
    finally:
        conn.close()


def page_info(total, per_page=PER_PAGE):
    pages = max(1, -(-total // per_page))
    page = min(max(request.args.get("page", 1, type=int), 1), pages)
    return {"page": page, "pages": pages, "total": total, "offset": (page - 1) * per_page, "limit": per_page}


def like(text):
    """Αναζήτηση με LIKE όπου τα %, _ του χρήστη μετράνε ως απλοί χαρακτήρες."""
    return "%" + re.sub(r"([\\%_])", r"\\\1", text) + "%"


def days_ago(days):
    return (core.now_local() - timedelta(days=days)).isoformat(timespec="seconds")


def target_user(user_id):
    """Ο χρήστης μιας ενέργειας. Οι λογαριασμοί διαχειριστών (και ο δικός σου) αλλάζουν μόνο από το console."""
    user = core.get_user(user_id)
    if user is None:
        abort(404)
    if user["is_admin"]:
        flash("Οι λογαριασμοί διαχειριστών αλλάζουν μόνο από το Bash console.", "error")
        return None
    return user


# --- Επισκόπηση ---

@bp.get("/")
def dashboard():
    counts = query("""SELECT (SELECT COUNT(*) FROM users) AS users,
                             (SELECT COUNT(*) FROM users WHERE created_at >= :d30) AS new_users,
                             (SELECT COUNT(*) FROM users WHERE last_login_at >= :d30) AS active_users,
                             (SELECT COUNT(*) FROM users WHERE disabled = 1) AS disabled_users,
                             (SELECT COUNT(*) FROM records WHERE user_id IS NULL) AS orphan_records,
                             (SELECT COUNT(*) FROM activity WHERE action = 'error' AND at >= :d7) AS errors,
                             (SELECT COUNT(*) FROM activity WHERE action = 'login_failed' AND at >= :d1) AS failed_logins""",
                   {"d30": days_ago(30), "d7": days_ago(7), "d1": days_ago(1)}, one=True)
    activity = query("SELECT * FROM activity ORDER BY id DESC LIMIT 8")
    newest = query("SELECT id, username, created_at FROM users ORDER BY id DESC LIMIT 5")
    return render_template("admin/dashboard.html", section="dashboard", counts=counts, activity=activity,
                           newest=newest, actions=ACTIONS)


# --- Χρήστες ---

@bp.get("/users")
def users():
    q = request.args.get("q", "").strip()[:30]
    role = request.args.get("role", "") if request.args.get("role") in USER_FILTERS else ""
    sort = request.args.get("sort") if request.args.get("sort") in USER_SORTS else "new"
    where = f"WHERE u.username LIKE ? ESCAPE '\\' {USER_FILTERS[role][1]}"
    params = (like(q),)
    total = query(f"SELECT COUNT(*) FROM users u {where}", params, one=True)[0]
    p = page_info(total)
    rows = query(f"""SELECT u.id, u.username, u.created_at, u.last_login_at, u.is_admin, u.disabled, u.must_change_password
                     FROM users u {where} ORDER BY {USER_SORTS[sort][1]} LIMIT ? OFFSET ?""",
                 (*params, p["limit"], p["offset"]))
    return render_template("admin/users.html", section="users", users=rows, p=p, q=q, role=role, sort=sort,
                           sorts=USER_SORTS, roles=USER_FILTERS)


@bp.get("/users/<int:user_id>")
def user_detail(user_id):
    user = query("""SELECT id, username, created_at, last_login_at, is_admin, disabled, must_change_password
                    FROM users WHERE id=?""",
                 (user_id,), one=True)
    if user is None:
        abort(404)
    activity = query("SELECT * FROM activity WHERE actor_id=? OR target=? ORDER BY id DESC LIMIT 10",
                     (user_id, user["username"]))
    return render_template("admin/user.html", section="users", user=user, activity=activity, actions=ACTIONS)


@bp.post("/users/<int:user_id>/status")
def user_status(user_id):
    user = target_user(user_id)
    if user:
        disable = request.form.get("action") == "disable"
        conn = core.connect()
        # Η απενεργοποίηση αυξάνει και το session_epoch, ώστε να κλείσουν αμέσως οι ανοιχτές συνδέσεις
        conn.execute("UPDATE users SET disabled=?, session_epoch = session_epoch + ? WHERE id=?",
                     (int(disable), int(disable), user_id))
        conn.commit()
        conn.close()
        core.log_activity("admin.disable" if disable else "admin.enable", g.user, target=user["username"])
        flash(f"Ο λογαριασμός «{user['username']}» {'απενεργοποιήθηκε' if disable else 'ενεργοποιήθηκε'}.", "success")
    return redirect(url_for(".user_detail", user_id=user_id))


@bp.post("/users/<int:user_id>/password")
def user_password(user_id):
    user = target_user(user_id)
    if not user:
        return redirect(url_for(".user_detail", user_id=user_id))
    password = secrets.token_urlsafe(9)
    core.set_password(user_id, generate_password_hash(password), temporary=True)
    core.clear_login_failures(user["username"])
    core.log_activity("admin.reset_password", g.user, target=user["username"])
    # Ο κωδικός εμφανίζεται μία φορά σε αυτή την απάντηση (όχι σε flash/cookie, όχι στο ημερολόγιο)
    return render_template("admin/password.html", section="users", user=user, password=password)


@bp.post("/users/<int:user_id>/delete")
def user_delete(user_id):
    user = target_user(user_id)
    if not user:
        return redirect(url_for(".user_detail", user_id=user_id))
    if request.form.get("confirm", "").strip().casefold() != user["username"].casefold():
        flash("Για διαγραφή, πληκτρολογήστε ακριβώς το όνομα του χρήστη.", "error")
        return redirect(url_for(".user_detail", user_id=user_id) + "#danger")
    conn = core.connect()
    with conn:
        conn.execute("DELETE FROM records WHERE user_id=?", (user_id,))
        conn.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.close()
    core.log_activity("admin.delete_user", g.user, target=user["username"])
    flash(f"Ο χρήστης «{user['username']}» και οι εγγραφές του διαγράφηκαν.", "success")
    return redirect(url_for(".users"))


# --- Δραστηριότητα ---

@bp.get("/activity")
def activity():
    kind = request.args.get("kind", "") if request.args.get("kind") in ACTIVITY_KINDS else ""
    where = f"WHERE {ACTIVITY_KINDS[kind][1]}" if ACTIVITY_KINDS[kind][1] else ""
    total = query(f"SELECT COUNT(*) FROM activity {where}", one=True)[0]
    p = page_info(total, 50)
    rows = query(f"SELECT * FROM activity {where} ORDER BY id DESC LIMIT ? OFFSET ?", (p["limit"], p["offset"]))
    return render_template("admin/activity.html", section="activity", activity=rows, p=p, kind=kind,
                           kinds=ACTIVITY_KINDS, actions=ACTIONS, keep=core.ACTIVITY_KEEP)


# --- Ρυθμίσεις ---

@bp.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        before = core.registration_state()
        values = {"registration": "on" if request.form.get("registration") == "on" else "off"}
        if request.form.get("action") == "generate":
            values["invite_code"] = secrets.token_urlsafe(8)
        else:
            code = request.form.get("invite_code", "").strip()
            if code and not INVITE_RE.match(code):
                flash("Ο κωδικός πρόσκλησης πρέπει να έχει 4–64 χαρακτήρες χωρίς κενά.", "error")
                return redirect(url_for(".settings"))
            # Αποθηκεύεται μόνο αν άλλαξε, ώστε ο κωδικός από το WSGI αρχείο να μένει η προεπιλογή
            if code and code != before["stored_code"]:
                values["invite_code"] = code
        core.set_settings(values)
        after = core.registration_state()
        changes = []
        if before["open"] != after["open"]:
            changes.append("εγγραφές " + ("ανοιχτές" if after["open"] else "κλειστές"))
        if before["stored_code"] != after["stored_code"]:
            changes.append("νέος κωδικός πρόσκλησης")  # Ο ίδιος ο κωδικός δεν καταγράφεται
        if changes:
            core.log_activity("admin.settings", g.user, detail=", ".join(changes))
            flash("Οι ρυθμίσεις αποθηκεύτηκαν.", "success")
        return redirect(url_for(".settings"))
    return render_template("admin/settings.html", section="settings", invite=core.registration_state())


# --- Σύστημα ---

def process_memory():
    """Μνήμη της τρέχουσας διεργασίας (Linux/PythonAnywhere): τρέχουσα και μέγιστη. None αλλού."""
    try:
        with open("/proc/self/status") as f:
            fields = dict(line.split(":", 1) for line in f if ":" in line)
        return {"rss": int(fields["VmRSS"].split()[0]) * 1024, "peak": int(fields["VmHWM"].split()[0]) * 1024}
    except (OSError, KeyError, ValueError):
        return None


def package_version(name):
    try:
        return version(name)
    except PackageNotFoundError:
        return "—"


@bp.get("/system")
def system():
    base = os.path.dirname(os.path.abspath(__file__))
    code_files = [os.path.join(base, name) for name in ("app.py", "core.py", "admin.py")]
    db_size = sum(os.path.getsize(core.DB_NAME + ext) for ext in ("", "-wal") if os.path.exists(core.DB_NAME + ext))
    counts = query("""SELECT (SELECT COUNT(*) FROM users) AS users,
                             (SELECT COUNT(*) FROM activity) AS activity""", one=True)
    errors = query("SELECT * FROM activity WHERE action = 'error' ORDER BY id DESC LIMIT 10")
    error_count = query("SELECT COUNT(*) FROM activity WHERE action = 'error' AND at >= ?", (days_ago(7),), one=True)[0]
    info = {
        "deployed": datetime.fromtimestamp(max(os.path.getmtime(f) for f in code_files if os.path.exists(f)), core.TZ),
        "uptime": timedelta(seconds=int(time.time() - STARTED_AT)),
        "python": platform.python_version(),
        "flask": package_version("flask"),
        "pdfplumber": package_version("pdfplumber"),
        "sqlite": sqlite3.sqlite_version,
        "pdf_loaded": "pdfplumber" in sys.modules,
        "memory": process_memory(),
        "db_size": db_size,
        "db_share": db_size / DISK_QUOTA * 100,
    }
    return render_template("admin/system.html", section="system", info=info, counts=counts, errors=errors,
                           error_count=error_count, keep=core.ACTIVITY_KEEP)
