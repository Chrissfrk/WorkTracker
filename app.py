import os
import re
import csv
import io
import hmac
import secrets
from datetime import timedelta
import click
from flask import (Flask, render_template, request, redirect, url_for, session,
                   flash, Response, g)
from werkzeug.security import generate_password_hash, check_password_hash
import core

# Τοπικά οι ρυθμίσεις (INVITE_CODE κλπ) διαβάζονται από το .env — στον server από το WSGI αρχείο
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:
    pass

app = Flask(__name__)
# Χωρίς SECRET_KEY παράγεται τυχαίο κλειδί (απλώς χρειάζεται νέα σύνδεση μετά από κάθε restart)
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
app.permanent_session_lifetime = timedelta(days=365) # Μένει συνδεδεμένο στο κινητό
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024 # Όριο για τα PDF

# Κωδικός πρόσκλησης για νέους λογαριασμούς (χωρίς αυτόν η εγγραφή είναι κλειστή)
INVITE_CODE = os.environ.get("INVITE_CODE", "")

USERNAME_RE = re.compile(r"^[\w.-]{3,30}$")
MIN_PASSWORD = 6

core.init_db()

# --- Σύνδεση / Εγγραφή ---

@app.before_request
def load_user():
    g.user = None
    user_id = session.get("user_id")
    if user_id is not None:
        g.user = core.get_user(user_id)
        if g.user is None:
            session.clear()
    # Η αρχική (index) δείχνει την παρουσίαση της εφαρμογής σε όσους δεν έχουν συνδεθεί
    if g.user is None and request.endpoint not in ("login", "register", "static", "home", "index"):
        return redirect(url_for("login"))

@app.context_processor
def inject_globals():
    return {"current_user": g.get("user"), "registration_open": bool(INVITE_CODE)}

def start_session(user_id):
    session.clear()
    session.permanent = True
    session["user_id"] = user_id

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        user = core.get_user_by_name(username)
        if user and check_password_hash(user["password_hash"], request.form.get("password", "")):
            start_session(user["id"])
            return redirect(url_for("index"))
        flash("Λάθος όνομα χρήστη ή κωδικός.", "error")
        return render_template("login.html", username=username)
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if not INVITE_CODE:
        flash("Η δημιουργία λογαριασμών είναι κλειστή.", "error")
        return redirect(url_for("login"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        error = None
        if not hmac.compare_digest(request.form.get("invite", "").strip(), INVITE_CODE):
            error = "Λάθος κωδικός πρόσκλησης."
        elif not USERNAME_RE.match(username):
            error = "Το όνομα χρήστη πρέπει να έχει 3-30 χαρακτήρες (γράμματα, αριθμοί, . _ -)."
        elif len(password) < MIN_PASSWORD:
            error = f"Ο κωδικός πρέπει να έχει τουλάχιστον {MIN_PASSWORD} χαρακτήρες."
        elif password != request.form.get("confirm", ""):
            error = "Οι κωδικοί δεν ταιριάζουν."
        else:
            user_id = core.create_user(username, generate_password_hash(password))
            if user_id is None:
                error = "Το όνομα χρήστη υπάρχει ήδη."
            else:
                start_session(user_id)
                flash(f"Καλώς ήρθες, {username}!", "success")
                return redirect(url_for("index"))
        flash(error, "error")
        return render_template("register.html", username=username)
    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# --- Εντολές διαχείρισης (π.χ. στο Bash console του PythonAnywhere) ---

@app.cli.command("list-users")
def list_users_command():
    """Εμφανίζει τους χρήστες και πόσες εγγραφές έχει ο καθένας."""
    for username, created_at, count in core.list_users():
        click.echo(f"{username:20} {created_at or '':20} {count} εγγραφές")

@app.cli.command("reset-password")
@click.argument("username")
@click.password_option()
def reset_password_command(username, password):
    """Ορίζει νέο κωδικό σε χρήστη που τον ξέχασε."""
    user = core.get_user_by_name(username)
    if not user:
        raise click.ClickException(f"Δεν υπάρχει χρήστης '{username}'.")
    core.set_password(user["id"], generate_password_hash(password))
    click.echo(f"Ο κωδικός του '{user['username']}' άλλαξε.")

# --- Παρουσίαση (δημόσια) ---

@app.route("/welcome")
def home():
    return render_template("home.html")

# --- Κεντρική Σελίδα ---

@app.route("/")
def index():
    if g.user is None:
        return render_template("home.html")

    editing = None
    edit_id = request.args.get("edit", type=int)
    if edit_id is not None:
        editing = core.get_record(g.user["id"], edit_id)

    form = {"date": core.now_local().strftime("%Y-%m-%d"), "type": "shift", "start": "", "end": ""}
    if editing:
        form["date"] = editing["date"]
        form["type"] = editing["type"]
        if editing["type"] == "shift" and " - " in editing["description"]:
            form["start"], form["end"] = editing["description"].split(" - ")

    records = []
    for r in core.list_records(g.user["id"]):
        records.append({
            "id": r["id"],
            "month": r["date"][:7],
            "date": core.format_date_display(r["date"]),
            "type": r["type"],
            "desc": "-" if r["type"] == "transfer" else r["description"],
            "hours": core.format_hours_to_clock(r["hours"]),
            "total": f"{r['total_eur']:.2f} €",
            "direct": f"{r['direct_eur']:.2f} €",
            "fund": f"{r['fund_eur']:.2f} €",
        })

    monthly = core.get_monthly_totals(g.user["id"])
    months = core.get_month_overview(monthly)
    # Επιλεγμένος μήνας από το ?month=YYYY-MM (αλλιώς ο τρέχων). Το app.js αλλάζει μήνα χωρίς επαναφόρτωση.
    month_index = next((i for i, m in enumerate(months) if m["key"] == request.args.get("month")),
                       next(i for i, m in enumerate(months) if m["current"]))

    # Οι εγγραφές εμφανίζονται ανά μήνα (είναι ήδη ταξινομημένες, νεότερες πρώτα)
    by_key = {m["key"]: m for m in months}
    record_groups = []
    for rec in records:
        if not record_groups or record_groups[-1]["key"] != rec["month"]:
            m = by_key.get(rec["month"], {})
            record_groups.append({"key": rec["month"], "label": m.get("label", rec["month"]),
                                  "direct": m.get("direct"), "records": []})
        record_groups[-1]["records"].append(rec)

    return render_template("index.html", stats=core.get_stats(monthly), records=records, record_groups=record_groups,
                           form=form, editing=editing, months=months, month_index=month_index)

# --- Καταχώριση / Επεξεργασία / Διαγραφή ---

def record_from_form():
    rec_type = "transfer" if request.form.get("type") == "transfer" else "shift"
    date_str = request.form.get("date", "")
    start = request.form.get("start") or "00:00"
    end = request.form.get("end") or "00:00"
    if not date_str:
        flash("Επιλέξτε ημερομηνία.", "error")
        return None
    rec = core.make_record(date_str, rec_type, start, end)
    if rec is None:
        flash("Η διάρκεια δεν μπορεί να είναι 0.", "error")
    return rec

@app.post("/records")
def create_record():
    rec = record_from_form()
    if rec:
        core.insert_bulk_to_db(g.user["id"], [rec])
        flash("Η εγγραφή προστέθηκε.", "success")
    return redirect(url_for("index"))

@app.post("/records/<int:rec_id>")
def save_record(rec_id):
    rec = record_from_form()
    if not rec:
        return redirect(url_for("index", edit=rec_id))
    core.update_record(g.user["id"], rec_id, rec)
    flash("Οι αλλαγές αποθηκεύτηκαν.", "success")
    return redirect(url_for("index"))

@app.post("/records/<int:rec_id>/delete")
def remove_record(rec_id):
    core.delete_record(g.user["id"], rec_id)
    flash("Η εγγραφή διαγράφηκε.", "success")
    return redirect(url_for("index"))

# --- Μαζική Εισαγωγή / PDF / CSV ---

@app.post("/bulk")
def bulk_import():
    text = request.form.get("text", "")
    if not text.strip():
        return redirect(url_for("index"))

    records, errors = core.parse_bulk_text(text)
    if errors:
        flash("Τα παρακάτω δεν προστέθηκαν:\n" + "\n".join(errors), "error")
    if records:
        core.insert_bulk_to_db(g.user["id"], records)
        flash(f"Ολοκληρώθηκαν {len(records)} ενέργειες (Προσθήκες / Ενημερώσεις).", "success")
    return redirect(url_for("index"))

@app.post("/import-pdf")
def import_pdf():
    files = [f for f in request.files.getlist("pdf") if f and f.filename]
    if not files:
        flash("Επιλέξτε αρχείο PDF.", "error")
        return redirect(url_for("index"))

    # Κάθε αρχείο διαβάζεται χωριστά, ώστε ένα χαλασμένο PDF να μην μπλοκάρει τα υπόλοιπα
    record_lists, errors = [], []
    for file in files:
        try:
            records = core.parse_pdf_schedule(io.BytesIO(file.read()))
        except Exception as e:
            errors.append(f"{file.filename}: αποτυχία ανάγνωσης ({e})")
            continue
        if not records:
            errors.append(f"{file.filename}: δεν βρέθηκαν βάρδιες (ελέγξτε τη μορφή του αρχείου)")
            continue
        record_lists.append(records)

    if errors:
        flash("Τα παρακάτω αρχεία δεν εισήχθησαν:\n" + "\n".join(errors), "error")
    if not record_lists:
        return redirect(url_for("index"))

    records = core.merge_schedule_records(record_lists)
    new_records = core.filter_existing_records(g.user["id"], records)
    skipped = len(records) - len(new_records)
    if new_records:
        core.insert_bulk_to_db(g.user["id"], new_records)

    shifts = sum(1 for r in new_records if r['type'] == 'shift')
    transfers = len(new_records) - shifts
    source = "το PDF" if len(record_lists) == 1 else f"{len(record_lists)} PDF"
    msg = f"Προστέθηκαν {len(new_records)} εγγραφές από {source} ({shifts} βάρδιες, {transfers} transfer)."
    if skipped:
        msg += f"\nΠαραλείφθηκαν {skipped} που υπήρχαν ήδη."
    flash(msg, "success")
    return redirect(url_for("index"))

@app.route("/export.csv")
def export_csv():
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=';')
    writer.writerow(["Ημερομηνία", "Τύπος", "Περιγραφή", "Ώρες", "Σύνολο (€)", "Άμεση Πληρωμή (€)", "Ταμείο Νοέμβρη (€)"])
    writer.writerows(core.export_rows(g.user["id"]))
    # utf-8-sig (BOM) ώστε το Excel να διαβάζει σωστά τα ελληνικά
    data = buf.getvalue().encode("utf-8-sig")
    return Response(data, mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=work_data.csv"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
