import os
import re
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo
import pdfplumber

# --- Ρυθμίσεις ---

# Απόλυτη διαδρομή ώστε να δουλεύει ανεξάρτητα από τον τρέχοντα φάκελο (π.χ. στο PythonAnywhere)
DB_NAME = os.path.join(os.path.dirname(os.path.abspath(__file__)), "work_data.db")

# Ο server τρέχει σε UTC, οπότε το "σήμερα" υπολογίζεται σε ώρα Ελλάδας
TZ = ZoneInfo("Europe/Athens")

GR_MONTHS = ["Ιανουάριος", "Φεβρουάριος", "Μάρτιος", "Απρίλιος", "Μάιος", "Ιούνιος",
             "Ιούλιος", "Αύγουστος", "Σεπτέμβριος", "Οκτώβριος", "Νοέμβριος", "Δεκέμβριος"]
GR_MONTHS_SHORT = ["Ιαν", "Φεβ", "Μαρ", "Απρ", "Μαΐ", "Ιουν", "Ιουλ", "Αυγ", "Σεπ", "Οκτ", "Νοε", "Δεκ"]
GR_DAYS = ["Δευ", "Τρί", "Τετ", "Πέμ", "Παρ", "Σάβ", "Κυρ"]

def now_local():
    return datetime.now(TZ)

def connect():
    return sqlite3.connect(DB_NAME)

# --- Λογική ---

def init_db():
    conn = connect()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    password_hash TEXT NOT NULL,
                    created_at TEXT
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT,
                    type TEXT,
                    description TEXT,
                    hours REAL,
                    total_eur REAL,
                    direct_eur REAL,
                    fund_eur REAL,
                    user_id INTEGER REFERENCES users(id)
                )''')
    # Μετάβαση από την παλιά βάση (ενός χρήστη): προσθήκη στήλης user_id
    columns = [row[1] for row in c.execute("PRAGMA table_info(records)")]
    if "user_id" not in columns:
        c.execute("ALTER TABLE records ADD COLUMN user_id INTEGER REFERENCES users(id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_records_user_date ON records(user_id, date)")
    conn.commit()
    conn.close()

# --- Χρήστες ---

def create_user(username, password_hash):
    """Δημιουργεί χρήστη. Ο πρώτος χρήστης παίρνει τις εγγραφές της παλιάς βάσης (χωρίς user_id).
    Επιστρέφει το id ή None αν το όνομα υπάρχει ήδη."""
    conn = connect()
    try:
        c = conn.cursor()
        c.execute("INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                  (username, password_hash, now_local().isoformat(timespec="seconds")))
        user_id = c.lastrowid
        if c.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1:
            c.execute("UPDATE records SET user_id=? WHERE user_id IS NULL", (user_id,))
        conn.commit()
        return user_id
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()

def get_user_by_name(username):
    conn = connect()
    conn.row_factory = sqlite3.Row
    res = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    conn.close()
    return dict(res) if res else None

def get_user(user_id):
    conn = connect()
    conn.row_factory = sqlite3.Row
    res = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    return dict(res) if res else None

def set_password(user_id, password_hash):
    conn = connect()
    conn.execute("UPDATE users SET password_hash=? WHERE id=?", (password_hash, user_id))
    conn.commit()
    conn.close()

def list_users():
    conn = connect()
    rows = conn.execute("""SELECT u.username, u.created_at, COUNT(r.id) FROM users u
                           LEFT JOIN records r ON r.user_id = u.id GROUP BY u.id ORDER BY u.id""").fetchall()
    conn.close()
    return rows

def calculate_pay(record_type, hours):
    if record_type == "transfer":
        return {"hours": 0.0, "total": 40.0, "direct": 30.0, "fund": 10.0}
    else:
        total = hours * 10.0
        return {"hours": hours, "total": total, "direct": total * 0.75, "fund": total * 0.25}

def format_hours_to_clock(decimal_hours):
    """Μετατρέπει το 6.75 σε '6:45' """
    if decimal_hours == 0: return "-"
    h = int(decimal_hours)
    m = int(round((decimal_hours - h) * 60))
    return f"{h}:{m:02d}"

def shift_hours(h1, m1, h2, m2):
    hours = (h2 + m2 / 60.0) - (h1 + m1 / 60.0)
    if hours < 0: hours += 24
    return round(hours, 2)

def parse_bulk_text(text, current_year=None):
    if current_year is None:
        current_year = now_local().year
    records = []
    errors = []
    lines = text.strip().split('\n')

    for i, line in enumerate(lines):
        clean_line = line.strip()
        if not clean_line:
            continue

        # Εντοπισμός λέξης κλειδιού "edit"
        action = 'insert'
        if re.match(r'^edit\s+', clean_line, re.IGNORECASE):
            action = 'edit'
            clean_line = re.sub(r'^edit\s+', '', clean_line, flags=re.IGNORECASE).strip()

        # Κανονικοποίηση παύλας
        normalized = re.sub(r'[–—−]', '-', clean_line)

        date_match = re.match(r'^(\d{1,2})[/.-](\d{1,2})[:\s]*(.*)$', normalized)
        if not date_match:
            errors.append(f"Γραμμή {i+1}: Μη έγκυρη μορφή ημερομηνίας -> {clean_line}")
            continue

        day, month, rest = date_match.groups()
        date_str = f"{current_year}-{int(month):02d}-{int(day):02d}"
        rest = rest.strip()

        # Transfer
        if 'transfer' in rest.lower():
            multiplier_match = re.search(r'(\d+)\s*transfer|transfer\s*x?\s*(\d+)', rest, re.IGNORECASE)
            count = 1
            if multiplier_match:
                count = int(multiplier_match.group(1) or multiplier_match.group(2) or 1)

            for _ in range(count):
                pay = calculate_pay("transfer", 0)
                records.append({'action': action, 'date': date_str, 'type': 'transfer', 'desc': 'Transfer', 'hours': pay['hours'], 'total': pay['total'], 'direct': pay['direct'], 'fund': pay['fund']})
            continue

        # Βάρδια
        time_match = re.search(r'(\d{1,2})(?::(\d{2}))?\s*-\s*(\d{1,2})(?::(\d{2}))?', rest)
        if time_match:
            h1, m1, h2, m2 = time_match.groups()
            m1 = int(m1) if m1 else 0
            m2 = int(m2) if m2 else 0

            t1 = int(h1) + m1 / 60.0
            t2 = int(h2) + m2 / 60.0

            hours = t2 - t1
            if hours < 0: hours += 24

            desc = f"{int(h1):02d}:{m1:02d} - {int(h2):02d}:{m2:02d}"
            pay = calculate_pay("shift", round(hours, 2))
            records.append({'action': action, 'date': date_str, 'type': 'shift', 'desc': desc, 'hours': pay['hours'], 'total': pay['total'], 'direct': pay['direct'], 'fund': pay['fund']})
        else:
            errors.append(f"Γραμμή {i+1}: Μη αναγνωρίσιμη βάρδια -> {clean_line}")

    return records, errors

def build_schedule_record(date_str, h1, m1, h2, m2):
    """Δημιουργεί εγγραφή από ώρες προγράμματος. Κανόνας: Ακριβώς 1 ώρα = Transfer."""
    hours = shift_hours(h1, m1, h2, m2)

    if hours == 1.0:
        pay = calculate_pay("transfer", 0)
        return {
            'action': 'insert', 'date': date_str, 'type': 'transfer',
            'desc': 'Transfer', 'hours': pay['hours'], 'total': pay['total'],
            'direct': pay['direct'], 'fund': pay['fund']
        }

    pay = calculate_pay("shift", hours)
    desc = f"{h1:02d}:{m1:02d} - {h2:02d}:{m2:02d}"
    return {
        'action': 'insert', 'date': date_str, 'type': 'shift',
        'desc': desc, 'hours': pay['hours'], 'total': pay['total'],
        'direct': pay['direct'], 'fund': pay['fund']
    }

def parse_pdf_schedule(file):
    """
    Διαβάζει το εβδομαδιαίο πρόγραμμα PDF (Intercruises). Δέχεται διαδρομή ή file-like αντικείμενο.
    Κάθε κελί του πίνακα περιέχει την ημερομηνία και από κάτω τις εργασίες (κωδικός + ώρες), π.χ.
    '12/10/2026\\nSTF-PIR-RBR-\\n12OCT26\\n06:30 - 14:30'.
    """
    records = []
    date_pattern = re.compile(r'(\d{1,2})/(\d{1,2})/(\d{4})')
    time_pattern = re.compile(r'(\d{1,2}):(\d{2})\s*[-–—]\s*(\d{1,2}):(\d{2})')

    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for row in table:
                    for cell in row:
                        if not cell:
                            continue
                        date_match = date_pattern.search(cell)
                        if not date_match:
                            continue
                        day, month, year = date_match.groups()
                        date_str = f"{year}-{int(month):02d}-{int(day):02d}"

                        # Μπορεί να υπάρχουν πολλές εργασίες στην ίδια μέρα
                        for time_match in time_pattern.finditer(cell[date_match.end():]):
                            h1, m1, h2, m2 = map(int, time_match.groups())
                            records.append(build_schedule_record(date_str, h1, m1, h2, m2))

    return records

def merge_schedule_records(record_lists):
    """
    Ενώνει τις εγγραφές από πολλά PDF. Αν δύο αρχεία καλύπτουν την ίδια μέρα (επικαλυπτόμενες εβδομάδες
    ή το ίδιο αρχείο δύο φορές), οι ίδιες βάρδιες κρατιούνται μία φορά: για κάθε (ημερομηνία, τύπος, ώρες)
    κρατάμε τον μέγιστο αριθμό εμφανίσεων σε ένα αρχείο, όχι το άθροισμα.
    """
    merged = {}
    for records in record_lists:
        counts = {}
        for rec in records:
            key = (rec['date'], rec['type'], rec['desc'])
            counts.setdefault(key, []).append(rec)
        for key, recs in counts.items():
            if len(recs) > len(merged.get(key, [])):
                merged[key] = recs
    return sorted((rec for recs in merged.values() for rec in recs), key=lambda r: r['date'])

def filter_existing_records(user_id, records):
    """Αφαιρεί τις εγγραφές που υπάρχουν ήδη στη βάση (π.χ. όταν ξαναεισάγεται το ίδιο πρόγραμμα)."""
    conn = connect()
    c = conn.cursor()
    seen = {}
    new_records = []
    for rec in records:
        key = (rec['date'], rec['type'], rec['desc'])
        if key not in seen:
            c.execute("SELECT COUNT(*) FROM records WHERE user_id=? AND date=? AND type=? AND description=?", (user_id, *key))
            seen[key] = c.fetchone()[0]
        if seen[key] > 0:
            seen[key] -= 1
        else:
            new_records.append(rec)
    conn.close()
    return new_records

def format_date_display(date_str):
    """'2026-10-15' -> 'Πέμ 15/10/2026'"""
    d = datetime.strptime(date_str, "%Y-%m-%d")
    return f"{GR_DAYS[d.weekday()]}  {d.strftime('%d/%m/%Y')}"

# --- Βάση Δεδομένων ---

def make_record(date_str, rec_type, start=None, end=None):
    """Εγγραφή από τη φόρμα. start/end σε μορφή 'HH:MM'. Επιστρέφει None αν η διάρκεια είναι 0."""
    if rec_type == "transfer":
        pay = calculate_pay("transfer", 0)
        desc = "Transfer"
    else:
        h1, m1 = map(int, start.split(":"))
        h2, m2 = map(int, end.split(":"))
        hours = shift_hours(h1, m1, h2, m2)
        if hours == 0:
            return None
        pay = calculate_pay("shift", hours)
        desc = f"{h1:02d}:{m1:02d} - {h2:02d}:{m2:02d}"
    return {'action': 'insert', 'date': date_str, 'type': rec_type, 'desc': desc,
            'hours': pay['hours'], 'total': pay['total'], 'direct': pay['direct'], 'fund': pay['fund']}

def insert_bulk_to_db(user_id, records):
    conn = connect()
    c = conn.cursor()
    for rec in records:
        if rec['action'] == 'edit':
            # Διαγράφει την προηγούμενη βάρδια της ίδιας μέρας (ανάλογα τον τύπο)
            c.execute("DELETE FROM records WHERE user_id=? AND date=? AND type=?", (user_id, rec['date'], rec['type']))

        c.execute("INSERT INTO records (user_id, date, type, description, hours, total_eur, direct_eur, fund_eur) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                  (user_id, rec['date'], rec['type'], rec['desc'], rec['hours'], rec['total'], rec['direct'], rec['fund']))
    conn.commit()
    conn.close()

def update_record(user_id, rec_id, rec):
    conn = connect()
    conn.execute("UPDATE records SET date=?, type=?, description=?, hours=?, total_eur=?, direct_eur=?, fund_eur=? WHERE id=? AND user_id=?",
                 (rec['date'], rec['type'], rec['desc'], rec['hours'], rec['total'], rec['direct'], rec['fund'], rec_id, user_id))
    conn.commit()
    conn.close()

def delete_record(user_id, rec_id):
    conn = connect()
    conn.execute("DELETE FROM records WHERE id=? AND user_id=?", (rec_id, user_id))
    conn.commit()
    conn.close()

def get_record(user_id, rec_id):
    conn = connect()
    conn.row_factory = sqlite3.Row
    res = conn.execute("SELECT * FROM records WHERE id=? AND user_id=?", (rec_id, user_id)).fetchone()
    conn.close()
    return dict(res) if res else None

def list_records(user_id):
    conn = connect()
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM records WHERE user_id=? ORDER BY date DESC, id DESC", (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_monthly_totals(user_id):
    """Σύνολα ανά μήνα, μόνο για τους μήνες που έχουν εγγραφές, σε χρονολογική σειρά (ένα query για όλη τη σελίδα)."""
    conn = connect()
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""SELECT substr(date, 1, 7) AS month, SUM(hours) AS hours, SUM(total_eur) AS total,
                                  SUM(direct_eur) AS direct, SUM(fund_eur) AS fund,
                                  SUM(type = 'shift') AS shifts, SUM(type = 'transfer') AS transfers
                           FROM records WHERE user_id=? GROUP BY month ORDER BY month""", (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_stats(monthly):
    """Γενικά στατιστικά από τα σύνολα του get_monthly_totals."""
    now = now_local()
    current = next((m for m in monthly if m['month'] == now.strftime("%Y-%m")), {})
    g_hrs = sum(m['hours'] or 0 for m in monthly)
    g_tot = sum(m['total'] or 0 for m in monthly)
    g_dir = sum(m['direct'] or 0 for m in monthly)
    g_fnd = sum(m['fund'] or 0 for m in monthly)

    best = max(monthly, key=lambda m: m['direct'] or 0, default=None)
    if best and best['direct']:
        year, month = best['month'].split("-")
        best_month = f"{GR_MONTHS[int(month) - 1]} {year} ({best['direct']:.2f} €)"
    else:
        best_month = "N/A"
    avg_pay = g_dir / len(monthly) if monthly else 0

    return {
        'total': (f"{g_dir or 0:.2f} €",
                  f"Ώρες: {format_hours_to_clock(g_hrs or 0)} · Σύνολο: {g_tot or 0:.2f} €"),
        'fund': (f"{g_fnd or 0:.2f} €", f"Αυτόν τον μήνα: {current.get('fund') or 0:.2f} €"),
        'avg': (f"{avg_pay:.2f} €", f"Καλύτερος μήνας: {best_month}"),
    }

def month_range(first, last):
    """'2026-11', '2027-02' -> '2026-11', '2026-12', '2027-01', '2027-02'"""
    year, month = map(int, first.split("-"))
    last_year, last_month = map(int, last.split("-"))
    while (year, month) <= (last_year, last_month):
        yield f"{year}-{month:02d}"
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)

def month_delta(direct, prev_direct, prev_key, key):
    """Σύγκριση της άμεσης πληρωμής με τον προηγούμενο μήνα."""
    diff = round(direct - prev_direct, 2)
    trend = "up" if diff > 0 else "down" if diff < 0 else "flat"
    text = {"up": "▲ ", "down": "▼ ", "flat": "± "}[trend] + f"{abs(diff):.2f} €"
    if prev_direct:
        text += f" ({diff / prev_direct * 100:+.0f}%)"
    prev_year, prev_month = map(int, prev_key.split("-"))
    vs = f"σε σχέση με τον {GR_MONTHS[prev_month - 1][:-1]}"  # Σεπτέμβριος -> τον Σεπτέμβριο
    if prev_year != int(key[:4]):
        vs += f" {prev_year}"
    return {"trend": trend, "text": text, "vs": vs}

def get_month_overview(monthly):
    """
    Όλοι οι μήνες από την πρώτη εγγραφή μέχρι τον τρέχοντα (ή την τελευταία εγγραφή, αν το πρόγραμμα
    φτάνει σε επόμενο μήνα), μαζί με όσους δεν έχουν εγγραφές, ώστε η σύγκριση να γίνεται πάντα με τον
    προηγούμενο ημερολογιακό μήνα. Οι τιμές επιστρέφονται έτοιμες για εμφάνιση (και ως JSON για το app.js).
    """
    by_month = {m['month']: m for m in monthly if re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", m['month'] or "")}
    current = now_local().strftime("%Y-%m")
    max_direct = max((m['direct'] or 0 for m in by_month.values()), default=0)

    months = []
    prev = None
    for key in month_range(min([*by_month, current]), max([*by_month, current])):
        data = by_month.get(key, {})
        direct = data.get('direct') or 0
        year, month = map(int, key.split("-"))
        months.append({
            'key': key,
            'label': f"{GR_MONTHS[month - 1]} {year}",
            'short': GR_MONTHS_SHORT[month - 1],
            'year': year,
            'current': key == current,
            'height': round(direct / max_direct * 100, 1) if max_direct else 0,
            'direct': f"{direct:.2f} €",
            'total': f"{data.get('total') or 0:.2f} €",
            'fund': f"{data.get('fund') or 0:.2f} €",
            'hours': format_hours_to_clock(data.get('hours') or 0),
            'counts': f"{data.get('shifts') or 0} · {data.get('transfers') or 0}",
            # Ο πρώτος μήνας δεν έχει προηγούμενο για σύγκριση
            'delta': month_delta(direct, prev[1], prev[0], key) if prev else None,
        })
        prev = (key, direct)
    return months

def export_rows(user_id):
    """Γραμμές για CSV, μορφοποιημένες για συμβατότητα με Excel."""
    conn = connect()
    rows = conn.execute("SELECT date, type, description, hours, total_eur, direct_eur, fund_eur FROM records WHERE user_id=? ORDER BY date", (user_id,)).fetchall()
    conn.close()
    formatted_rows = []
    for r in rows:
        gr_date = datetime.strptime(r[0], "%Y-%m-%d").strftime("%d/%m/%Y")
        formatted_rows.append([gr_date, r[1], r[2], format_hours_to_clock(r[3]), r[4], r[5], r[6]])
    return formatted_rows
