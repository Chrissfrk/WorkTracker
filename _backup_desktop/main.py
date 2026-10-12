import os
import sys
import re
import sqlite3
import csv
from datetime import datetime, date
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QTextEdit, QTableWidget,
                             QTableWidgetItem, QHeaderView, QMessageBox,
                             QDateEdit, QTimeEdit, QFileDialog, QFrame,
                             QDialog, QButtonGroup, QScrollArea)
from PyQt6.QtCore import Qt, QDate, QTime, QSize
from PyQt6.QtGui import QFont, QColor, QPalette, QIcon
import pdfplumber

# --- Θέμα (Theme) ---

COLORS = {
    'bg': '#0F172A',
    'surface': '#1E293B',
    'surface_alt': '#273449',
    'border': '#334155',
    'text': '#E2E8F0',
    'muted': '#94A3B8',
    'primary': '#6366F1',
    'primary_hover': '#818CF8',
    'green': '#34D399',
    'amber': '#FBBF24',
    'danger': '#F87171',
}

# Εικονίδια (βέλη) για τα dropdown - το Qt stylesheet θέλει forward slashes
ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets").replace("\\", "/")

GR_MONTHS = ["Ιανουάριος", "Φεβρουάριος", "Μάρτιος", "Απρίλιος", "Μάιος", "Ιούνιος",
             "Ιούλιος", "Αύγουστος", "Σεπτέμβριος", "Οκτώβριος", "Νοέμβριος", "Δεκέμβριος"]
GR_DAYS = ["Δευ", "Τρί", "Τετ", "Πέμ", "Παρ", "Σάβ", "Κυρ"]

def build_stylesheet(c):
    return f"""
    QMainWindow, QDialog {{ background-color: {c['bg']}; }}
    QWidget {{ color: {c['text']}; }}
    QLabel {{ background: transparent; }}

    QLabel#appTitle {{ font-size: 20pt; font-weight: 700; }}
    QLabel#appSubtitle, QLabel#muted, QLabel#fieldLabel {{ color: {c['muted']}; }}
    QLabel#fieldLabel {{ font-size: 10pt; font-weight: 600; }}
    QLabel#sectionTitle {{ font-size: 14pt; font-weight: 600; }}
    QLabel#cardTitle {{ color: {c['muted']}; font-size: 9.5pt; font-weight: 600; }}
    QLabel#cardValue {{ font-size: 19pt; font-weight: 700; }}
    QLabel#cardSub {{ color: {c['muted']}; font-size: 9.5pt; }}
    QLabel#preview {{
        background-color: {c['bg']};
        border: 1px dashed {c['border']};
        border-radius: 8px;
        padding: 10px 12px;
        color: {c['muted']};
    }}

    QFrame#card {{
        background-color: {c['surface']};
        border: 1px solid {c['border']};
        border-radius: 14px;
    }}
    QFrame#card[editing="true"] {{ border: 2px solid {c['primary']}; }}

    QScrollArea, QWidget#sidebar {{ background: transparent; border: none; }}

    QTextEdit, QDateEdit, QTimeEdit {{
        background-color: {c['bg']};
        border: 1px solid {c['border']};
        border-radius: 8px;
        padding: 9px 12px;
        selection-background-color: {c['primary']};
    }}
    QTextEdit:focus, QDateEdit:focus, QTimeEdit:focus {{
        border: 1px solid {c['primary']};
    }}
    QTimeEdit:disabled {{ color: {c['border']}; }}
    QDateEdit::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: center right;
        border: none;
        width: 28px;
    }}
    QDateEdit::down-arrow, QTimeEdit::down-arrow {{
        image: url({ASSETS_DIR}/chevron-down.svg);
        width: 12px;
        height: 12px;
    }}
    QTimeEdit::up-arrow {{ image: url({ASSETS_DIR}/chevron-up.svg); width: 10px; height: 10px; }}
    QTimeEdit::down-arrow {{ width: 10px; height: 10px; }}
    QTimeEdit::up-button, QTimeEdit::down-button {{
        subcontrol-origin: border;
        border: none;
        background: transparent;
        width: 24px;
    }}
    QTimeEdit::up-button {{ subcontrol-position: top right; margin-top: 4px; }}
    QTimeEdit::down-button {{ subcontrol-position: bottom right; margin-bottom: 4px; }}
    QTimeEdit::up-button:hover, QTimeEdit::down-button:hover {{ background-color: {c['surface_alt']}; border-radius: 4px; }}

    QPushButton {{
        background-color: {c['surface_alt']};
        border: 1px solid {c['border']};
        border-radius: 8px;
        padding: 9px 16px;
        font-weight: 600;
    }}
    QPushButton:hover {{ background-color: {c['border']}; }}
    QPushButton[variant="primary"] {{
        background-color: {c['primary']};
        border: 1px solid {c['primary']};
        color: white;
    }}
    QPushButton[variant="primary"]:hover {{
        background-color: {c['primary_hover']};
        border-color: {c['primary_hover']};
    }}
    QPushButton[variant="danger"] {{
        background-color: transparent;
        border: 1px solid #7F1D1D;
        color: {c['danger']};
    }}
    QPushButton[variant="danger"]:hover {{ background-color: #3B1D27; }}

    QPushButton[variant="segment"] {{
        background-color: {c['bg']};
        padding: 10px;
    }}
    QPushButton[variant="segment"]:checked {{
        background-color: {c['primary']};
        border-color: {c['primary']};
        color: white;
    }}

    QPushButton[variant="icon"], QPushButton[variant="icon-danger"] {{
        background-color: transparent;
        border: none;
        border-radius: 6px;
        padding: 6px;
    }}
    QPushButton[variant="icon"]:hover {{ background-color: {c['border']}; }}
    QPushButton[variant="icon-danger"]:hover {{ background-color: #3B1D27; }}

    QTableWidget {{
        font-size: 11pt;
        background-color: {c['surface']};
        border: none;
        gridline-color: transparent;
        outline: none;
    }}
    QTableWidget::item {{
        border-bottom: 1px solid {c['border']};
        padding-left: 10px;
        padding-right: 10px;
    }}
    QTableWidget::item:selected {{ background-color: #312E81; color: white; }}
    QHeaderView::section {{
        background-color: {c['surface']};
        color: {c['muted']};
        border: none;
        border-bottom: 1px solid {c['border']};
        padding: 10px;
        font-weight: 600;
    }}
    QTableCornerButton::section {{ background-color: {c['surface']}; border: none; }}

    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
    QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
    QScrollBar::handle {{ background: {c['border']}; border-radius: 3px; min-height: 30px; min-width: 30px; }}
    QScrollBar::handle:hover {{ background: {c['muted']}; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}

    QCalendarWidget QWidget#qt_calendar_navigationbar {{ background-color: {c['surface_alt']}; }}
    QCalendarWidget QToolButton {{ background: transparent; color: {c['text']}; padding: 4px 8px; }}
    QCalendarWidget QAbstractItemView {{
        background-color: {c['surface']};
        selection-background-color: {c['primary']};
    }}
    """

def apply_theme(app):
    app.setStyle("Fusion")

    font = QFont("Segoe UI", 11)
    app.setFont(font)

    # Σκούρα παλέτα ώστε και τα στοιχεία χωρίς stylesheet (π.χ. ημερολόγιο, μηνύματα) να ταιριάζουν
    c = COLORS
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(c['bg']))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(c['text']))
    palette.setColor(QPalette.ColorRole.Base, QColor(c['surface']))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(c['surface_alt']))
    palette.setColor(QPalette.ColorRole.Text, QColor(c['text']))
    palette.setColor(QPalette.ColorRole.Button, QColor(c['surface_alt']))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(c['text']))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(c['primary']))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("white"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(c['surface']))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(c['text']))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(c['muted']))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(c['border']))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(c['border']))
    app.setPalette(palette)

    app.setStyleSheet(build_stylesheet(c))

def make_button(text, slot, variant=None):
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    if variant:
        btn.setProperty("variant", variant)
    btn.clicked.connect(slot)
    return btn

def make_label(text, object_name):
    lbl = QLabel(text)
    lbl.setObjectName(object_name)
    return lbl

def make_card():
    card = QFrame()
    card.setObjectName("card")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(20, 18, 20, 18)
    layout.setSpacing(10)
    return card, layout

class StatCard(QFrame):
    def __init__(self, title, accent=None):
        super().__init__()
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(2)

        layout.addWidget(make_label(title, "cardTitle"))
        self.value = make_label("-", "cardValue")
        if accent:
            self.value.setStyleSheet(f"color: {accent};")
        layout.addWidget(self.value)
        self.sub = make_label("", "cardSub")
        self.sub.setWordWrap(True)
        layout.addWidget(self.sub)

    def set_values(self, value, sub):
        self.value.setText(value)
        self.sub.setText(sub)

# --- Λογική & Βάση Δεδομένων ---

DB_NAME = "work_data.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT,
                    type TEXT,
                    description TEXT,
                    hours REAL,
                    total_eur REAL,
                    direct_eur REAL,
                    fund_eur REAL
                )''')
    conn.commit()
    conn.close()

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

def parse_bulk_text(text, current_year=date.today().year):
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
    hours = (h2 + m2 / 60.0) - (h1 + m1 / 60.0)
    if hours < 0:
        hours += 24
    hours = round(hours, 2)

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

def parse_pdf_schedule(filepath):
    """
    Διαβάζει το εβδομαδιαίο πρόγραμμα PDF (Intercruises). Κάθε κελί του πίνακα περιέχει
    την ημερομηνία και από κάτω τις εργασίες (κωδικός + ώρες), π.χ.
    '12/10/2026\\nSTF-PIR-RBR-\\n12OCT26\\n06:30 - 14:30'.
    """


    records = []
    date_pattern = re.compile(r'(\d{1,2})/(\d{1,2})/(\d{4})')
    time_pattern = re.compile(r'(\d{1,2}):(\d{2})\s*[-–—]\s*(\d{1,2}):(\d{2})')

    with pdfplumber.open(filepath) as pdf:
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

def filter_existing_records(records):
    """Αφαιρεί τις εγγραφές που υπάρχουν ήδη στη βάση (π.χ. όταν ξαναεισάγεται το ίδιο πρόγραμμα)."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    seen = {}
    new_records = []
    for rec in records:
        key = (rec['date'], rec['type'], rec['desc'])
        if key not in seen:
            c.execute("SELECT COUNT(*) FROM records WHERE date=? AND type=? AND description=?", key)
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

# --- Παράθυρο Μαζικής Εισαγωγής ---
class BulkImportDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Μαζική Εισαγωγή")
        self.setMinimumSize(480, 440)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(10)

        layout.addWidget(make_label("Μαζική Εισαγωγή", "sectionTitle"))
        hint = make_label("Μία εγγραφή ανά γραμμή. Γράψτε «edit» μπροστά για να "
                          "αντικαταστήσετε τη βάρδια εκείνης της ημέρας.", "muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.text = QTextEdit()
        self.text.setPlaceholderText("π.χ.\n1/5 11-19\nedit 10/5 9:30-16\n15/5 transfer")
        layout.addWidget(self.text, 1)

        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(make_button("Ακύρωση", self.reject))
        buttons.addWidget(make_button("Προσθήκη", self.accept, "primary"))
        layout.addLayout(buttons)

    def get_text(self):
        return self.text.toPlainText()

# --- Γραφικό Περιβάλλον (GUI) ---

class WorkTrackerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Work Tracker - Διαχείριση Ωρών & Ταμείου")
        self.setMinimumSize(1100, 650)
        self.editing_id = None # id της εγγραφής που επεξεργαζόμαστε (None = νέα καταχώριση)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(24, 18, 24, 18)
        main_layout.setSpacing(16)

        # Κεφαλίδα
        header = QHBoxLayout()
        header.setSpacing(10)
        titles = QVBoxLayout()
        titles.setSpacing(0)
        titles.addWidget(make_label("Work Tracker", "appTitle"))
        titles.addWidget(make_label("Διαχείριση Ωρών & Ταμείου", "appSubtitle"))
        header.addLayout(titles)
        header.addStretch()
        header.addWidget(make_button("Μαζική Εισαγωγή", self.open_bulk_import))
        header.addWidget(make_button("Εισαγωγή PDF Προγράμματος", self.import_from_pdf, "primary"))
        main_layout.addLayout(header)

        # Κάρτες Στατιστικών
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(16)
        self.card_month = StatCard("Τρέχων Μήνας · Άμεση Πληρωμή", COLORS['green'])
        self.card_total = StatCard("Γενικό Σύνολο · Άμεση Πληρωμή")
        self.card_fund = StatCard("Ταμείο Νοέμβρη", COLORS['amber'])
        self.card_avg = StatCard("Μέση Μηνιαία Πληρωμή")
        for card in (self.card_month, self.card_total, self.card_fund, self.card_avg):
            stats_layout.addWidget(card, 1)
        main_layout.addLayout(stats_layout)

        body = QHBoxLayout()
        body.setSpacing(20)
        main_layout.addLayout(body, 1)

        # Πλαϊνή στήλη (με scroll ώστε η φόρμα να μην κόβεται ποτέ σε μικρές οθόνες)
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(16)
        sidebar_scroll = QScrollArea()
        sidebar_scroll.setWidget(sidebar)
        sidebar_scroll.setWidgetResizable(True)
        sidebar_scroll.setFixedWidth(400)
        sidebar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body.addWidget(sidebar_scroll)

        # Φόρμα Καταχώρισης / Επεξεργασίας
        self.form_card, form_layout = make_card()
        form_layout.setContentsMargins(24, 20, 24, 24)
        form_layout.setSpacing(8)
        self.form_title = make_label("Νέα Καταχώριση", "sectionTitle")
        form_layout.addWidget(self.form_title)
        form_layout.addSpacing(6)

        self.date_input = QDateEdit()
        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat("dd/MM/yyyy")
        self.date_input.setDate(QDate.currentDate())
        form_layout.addWidget(make_label("Ημερομηνία", "fieldLabel"))
        form_layout.addWidget(self.date_input)
        form_layout.addSpacing(6)

        form_layout.addWidget(make_label("Τύπος", "fieldLabel"))
        type_row = QHBoxLayout()
        type_row.setSpacing(8)
        self.type_group = QButtonGroup(self)
        self.btn_shift = QPushButton("Βάρδια")
        self.btn_transfer = QPushButton("Transfer (40 €)")
        for btn in (self.btn_shift, self.btn_transfer):
            btn.setCheckable(True)
            btn.setProperty("variant", "segment")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.type_group.addButton(btn)
            type_row.addWidget(btn)
        self.btn_shift.setChecked(True)
        self.btn_shift.toggled.connect(self.on_type_changed)
        form_layout.addLayout(type_row)
        form_layout.addSpacing(6)

        self.start_time = QTimeEdit()
        self.end_time = QTimeEdit()
        time_row = QHBoxLayout()
        time_row.setSpacing(12)
        for label, widget in (("Από", self.start_time), ("Έως", self.end_time)):
            widget.setDisplayFormat("HH:mm")
            widget.timeChanged.connect(self.update_preview)
            col = QVBoxLayout()
            col.setSpacing(8)
            col.addWidget(make_label(label, "fieldLabel"))
            col.addWidget(widget)
            time_row.addLayout(col)
        form_layout.addLayout(time_row)
        form_layout.addSpacing(6)

        # Ζωντανή προεπισκόπηση πληρωμής
        self.lbl_preview = make_label("", "preview")
        self.lbl_preview.ensurePolished()
        self.lbl_preview.setMinimumHeight(self.lbl_preview.fontMetrics().lineSpacing() * 2 + 26) # Πάντα χώρος για 2 γραμμές
        form_layout.addWidget(self.lbl_preview)
        form_layout.addSpacing(6)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.btn_cancel_edit = make_button("Ακύρωση", self.reset_form)
        self.btn_cancel_edit.hide()
        self.btn_submit = make_button("Προσθήκη", self.submit_entry, "primary")
        btn_row.addWidget(self.btn_cancel_edit, 1)
        btn_row.addWidget(self.btn_submit, 2)
        form_layout.addLayout(btn_row)

        # Σταθερό ύψος ώστε τα πεδία να μη συμπιέζονται ποτέ
        for widget in (self.date_input, self.start_time, self.end_time,
                       self.btn_shift, self.btn_transfer, self.btn_cancel_edit, self.btn_submit):
            widget.setMinimumHeight(46)

        sidebar_layout.addWidget(self.form_card)
        sidebar_layout.addStretch()

        # Πίνακας Δεδομένων
        table_card, table_layout = make_card()
        body.addWidget(table_card, 1)

        table_header = QHBoxLayout()
        table_header.setSpacing(10)
        table_header.addWidget(make_label("Καταχωρίσεις", "sectionTitle"))
        self.lbl_count = make_label("", "muted")
        table_header.addWidget(self.lbl_count)
        table_header.addStretch()
        table_header.addWidget(make_button("Εξαγωγή CSV", self.export_csv))
        table_layout.addLayout(table_header)

        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(["ID", "Ημερομηνία", "Τύπος", "Ωράριο", "Ώρες", "Σύνολο", "Άμεση Πλ.", "Ταμείο Νοέμβρη", ""])
        self.table.hideColumn(0)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(8, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(8, 96)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.table.horizontalHeader().setHighlightSections(False)
        for col in range(4, 8): # Αριθμητικές στήλες στοιχισμένες δεξιά όπως οι τιμές τους
            self.table.horizontalHeaderItem(col).setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(48)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        # Διπλό κλικ σε γραμμή = επεξεργασία
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.doubleClicked.connect(lambda index: self.start_edit(int(self.table.item(index.row(), 0).text())))
        table_layout.addWidget(self.table)

        self.update_preview()
        self.load_data()

    def import_from_pdf(self):
        try:
            import pdfplumber
        except ImportError:
            QMessageBox.critical(self, "Σφάλμα Βιβλιοθήκης", "Απαιτείται η βιβλιοθήκη pdfplumber.\nΕγκαταστήστε την τρέχοντας: pip install pdfplumber")
            return

        path, _ = QFileDialog.getOpenFileName(self, "Επιλογή Αρχείου PDF", "", "PDF Files (*.pdf)")
        if not path:
            return

        try:
            records = parse_pdf_schedule(path)
            if not records:
                QMessageBox.warning(self, "Καμία Εγγραφή", "Δεν βρέθηκαν βάρδιες στο PDF (ελέγξτε τη μορφή του αρχείου).")
                return

            new_records = filter_existing_records(records)
            skipped = len(records) - len(new_records)
            if new_records:
                self.insert_bulk_to_db(new_records)
                self.load_data()

            shifts = sum(1 for r in new_records if r['type'] == 'shift')
            transfers = len(new_records) - shifts
            msg = f"Προστέθηκαν {len(new_records)} εγγραφές από το PDF ({shifts} βάρδιες, {transfers} transfer)."
            if skipped:
                msg += f"\nΠαραλείφθηκαν {skipped} που υπήρχαν ήδη."
            QMessageBox.information(self, "Επιτυχία", msg)

        except Exception as e:
            QMessageBox.critical(self, "Σφάλμα", f"Αποτυχία ανάγνωσης αρχείου:\n{str(e)}")

    # --- Φόρμα Καταχώρισης / Επεξεργασίας ---

    def current_type(self):
        return "shift" if self.btn_shift.isChecked() else "transfer"

    def on_type_changed(self):
        is_shift = self.current_type() == "shift"
        self.start_time.setEnabled(is_shift)
        self.end_time.setEnabled(is_shift)
        self.update_preview()

    def form_hours(self):
        t1 = self.start_time.time()
        t2 = self.end_time.time()
        hours = (t2.hour() + t2.minute()/60.0) - (t1.hour() + t1.minute()/60.0)
        if hours < 0: hours += 24
        return round(hours, 2)

    def update_preview(self):
        if self.current_type() == "transfer":
            pay = calculate_pay("transfer", 0)
            self.lbl_preview.setText(f"Σταθερή αμοιβή {pay['total']:.2f} €\n"
                                     f"Άμεση {pay['direct']:.2f} € · Ταμείο {pay['fund']:.2f} €")
            return
        hours = self.form_hours()
        if hours == 0:
            self.lbl_preview.setText("Ορίστε ώρα έναρξης και λήξης")
            return
        pay = calculate_pay("shift", hours)
        self.lbl_preview.setText(f"Διάρκεια {format_hours_to_clock(hours)} · Σύνολο {pay['total']:.2f} €\n"
                                 f"Άμεση {pay['direct']:.2f} € · Ταμείο {pay['fund']:.2f} €")

    def set_form_editing(self, editing):
        self.form_card.setProperty("editing", editing)
        self.form_card.style().unpolish(self.form_card)
        self.form_card.style().polish(self.form_card)
        self.form_title.setText("Επεξεργασία Καταχώρισης" if editing else "Νέα Καταχώριση")
        self.btn_submit.setText("Αποθήκευση" if editing else "Προσθήκη")
        self.btn_cancel_edit.setVisible(editing)

    def start_edit(self, rec_id):
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT date, type, description FROM records WHERE id=?", (rec_id,))
        res = c.fetchone()
        conn.close()
        if not res: return
        date_raw, rec_type, desc = res

        self.editing_id = rec_id
        self.date_input.setDate(QDate.fromString(date_raw, "yyyy-MM-dd"))
        (self.btn_shift if rec_type == "shift" else self.btn_transfer).setChecked(True)
        if rec_type == "shift" and " - " in desc:
            t1, t2 = desc.split(" - ")
            self.start_time.setTime(QTime.fromString(t1, "HH:mm"))
            self.end_time.setTime(QTime.fromString(t2, "HH:mm"))
        self.on_type_changed()
        self.set_form_editing(True)
        self.select_row_by_id(rec_id)

    def reset_form(self):
        self.editing_id = None
        self.date_input.setDate(QDate.currentDate())
        self.btn_shift.setChecked(True)
        self.start_time.setTime(QTime(0, 0))
        self.end_time.setTime(QTime(0, 0))
        self.on_type_changed()
        self.set_form_editing(False)
        self.table.clearSelection()

    def submit_entry(self):
        date_str = self.date_input.date().toString("yyyy-MM-dd")
        rec_type = self.current_type()

        if rec_type == "transfer":
            pay = calculate_pay("transfer", 0)
            desc = "Transfer"
        else:
            hours = self.form_hours()
            if hours == 0:
                QMessageBox.warning(self, "Σφάλμα", "Η διάρκεια δεν μπορεί να είναι 0.")
                return
            pay = calculate_pay("shift", hours)
            desc = f"{self.start_time.time().toString('HH:mm')} - {self.end_time.time().toString('HH:mm')}"

        if self.editing_id is None:
            self.insert_bulk_to_db([{'action': 'insert', 'date': date_str, 'type': rec_type, 'desc': desc, 'hours': pay['hours'], 'total': pay['total'], 'direct': pay['direct'], 'fund': pay['fund']}])
            self.load_data()
        else:
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute("UPDATE records SET date=?, type=?, description=?, hours=?, total_eur=?, direct_eur=?, fund_eur=? WHERE id=?",
                      (date_str, rec_type, desc, pay['hours'], pay['total'], pay['direct'], pay['fund'], self.editing_id))
            conn.commit()
            conn.close()
            self.load_data()
            self.reset_form()

    def delete_record(self, rec_id):
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT date, description FROM records WHERE id=?", (rec_id,))
        res = c.fetchone()
        conn.close()
        if not res: return

        box = QMessageBox(self)
        box.setWindowTitle("Διαγραφή")
        box.setText(f"Διαγραφή της εγγραφής;\n\n{format_date_display(res[0])}  ·  {res[1]}")
        btn_delete = box.addButton("Διαγραφή", QMessageBox.ButtonRole.DestructiveRole)
        box.addButton("Ακύρωση", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() != btn_delete:
            return

        conn = sqlite3.connect(DB_NAME)
        conn.execute("DELETE FROM records WHERE id=?", (rec_id,))
        conn.commit()
        conn.close()
        if self.editing_id == rec_id:
            self.reset_form()
        self.load_data()

    def select_row_by_id(self, rec_id):
        for row in range(self.table.rowCount()):
            if int(self.table.item(row, 0).text()) == rec_id:
                self.table.selectRow(row)
                return

    def make_row_actions(self, rec_id):
        cell = QWidget()
        layout = QHBoxLayout(cell)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        for icon, tip, variant, slot in (("pencil.svg", "Επεξεργασία", "icon", self.start_edit),
                                          ("trash.svg", "Διαγραφή", "icon-danger", self.delete_record)):
            btn = QPushButton()
            btn.setIcon(QIcon(f"{ASSETS_DIR}/{icon}"))
            btn.setIconSize(QSize(18, 18))
            btn.setToolTip(tip)
            btn.setProperty("variant", variant)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _checked=False, s=slot: s(rec_id))
            layout.addWidget(btn)
        return cell

    # --- Μαζική Εισαγωγή ---

    def open_bulk_import(self):
        dlg = BulkImportDialog(self)
        if not dlg.exec():
            return
        text = dlg.get_text()
        if not text.strip(): return

        records, errors = parse_bulk_text(text)
        if errors:
            QMessageBox.warning(self, "Σφάλματα Ανάλυσης", "Τα παρακάτω δεν προστέθηκαν:\n\n" + "\n".join(errors))

        if records:
            self.insert_bulk_to_db(records)
            self.load_data()
            QMessageBox.information(self, "Επιτυχία", f"Ολοκληρώθηκαν {len(records)} ενέργειες (Προσθήκες / Ενημερώσεις).")

    def insert_bulk_to_db(self, records):
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        for rec in records:
            if rec['action'] == 'edit':
                # Διαγράφει την προηγούμενη βάρδια της ίδιας μέρας (ανάλογα τον τύπο)
                c.execute("DELETE FROM records WHERE date=? AND type=?", (rec['date'], rec['type']))
                
            c.execute("INSERT INTO records (date, type, description, hours, total_eur, direct_eur, fund_eur) VALUES (?, ?, ?, ?, ?, ?, ?)",
                      (rec['date'], rec['type'], rec['desc'], rec['hours'], rec['total'], rec['direct'], rec['fund']))
        conn.commit()
        conn.close()

    def load_data(self):
        self.table.setRowCount(0)
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        
        c.execute("SELECT * FROM records ORDER BY date DESC, id DESC")
        rows = c.fetchall()
        right_align = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        left_align = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        self.table.ensurePolished()
        bold_font = QFont(self.table.font())
        bold_font.setBold(True)
        for row_idx, row_data in enumerate(rows):
            self.table.insertRow(row_idx)
            for col_idx, col_data in enumerate(row_data):
                color = None
                if col_idx == 4: # Μετατροπή δεκαδικών ωρών σε ΗΗ:ΜΜ για UI
                    val = format_hours_to_clock(col_data)
                elif col_idx in [5, 6, 7]:
                    val = f"{col_data:.2f} €"
                elif col_idx == 1: # Μορφοποίηση Ημερομηνίας σε ΗΗ/ΜΜ/ΕΕΕΕ στο UI
                    val = format_date_display(col_data)
                elif col_idx == 2:
                    val = "Βάρδια" if col_data == "shift" else "Transfer"
                    color = COLORS['primary_hover'] if col_data == "shift" else COLORS['amber']
                elif col_idx == 3 and row_data[2] == "transfer":
                    val = "-"
                else:
                    val = str(col_data)

                item = QTableWidgetItem(val)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                item.setTextAlignment(right_align if col_idx >= 4 else left_align)
                if color:
                    item.setForeground(QColor(color))
                if col_idx in [2, 5]:
                    item.setFont(bold_font)
                self.table.setItem(row_idx, col_idx, item)
            self.table.setCellWidget(row_idx, 8, self.make_row_actions(row_data[0]))

        self.lbl_count.setText(f"{len(rows)} εγγραφές")
        if self.editing_id is not None:
            self.select_row_by_id(self.editing_id)

        # Στατιστικά
        now = datetime.now()
        current_month = now.strftime("%Y-%m")
        c.execute("SELECT SUM(hours), SUM(direct_eur), SUM(fund_eur) FROM records WHERE date LIKE ?", (f"{current_month}%",))
        m_hrs, m_dir, m_fnd = c.fetchone()
        c.execute("SELECT SUM(hours), SUM(total_eur), SUM(direct_eur), SUM(fund_eur) FROM records")
        g_hrs, g_tot, g_dir, g_fnd = c.fetchone()
        c.execute("SELECT substr(date, 1, 7) as month, SUM(direct_eur) as m_pay FROM records GROUP BY month ORDER BY m_pay DESC")
        monthly_stats = c.fetchall()
        conn.close()

        m_hrs_str = format_hours_to_clock(m_hrs or 0)
        g_hrs_str = format_hours_to_clock(g_hrs or 0)

        self.card_month.set_values(f"{m_dir or 0:.2f} €",
                                   f"{GR_MONTHS[now.month - 1]} {now.year} · Ώρες: {m_hrs_str}")
        self.card_total.set_values(f"{g_dir or 0:.2f} €",
                                   f"Ώρες: {g_hrs_str} · Σύνολο: {g_tot or 0:.2f} €")
        self.card_fund.set_values(f"{g_fnd or 0:.2f} €",
                                  f"Αυτόν τον μήνα: {m_fnd or 0:.2f} €")

        if monthly_stats and monthly_stats[0][1]:
            year, month = monthly_stats[0][0].split("-")
            best_month = f"{GR_MONTHS[int(month) - 1]} {year} ({monthly_stats[0][1]:.2f} €)"
        else:
            best_month = "N/A"
        avg_pay = (g_dir / len(monthly_stats)) if monthly_stats and g_dir else 0
        self.card_avg.set_values(f"{avg_pay:.2f} €", f"Καλύτερος μήνας: {best_month}")

    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Αποθήκευση CSV", "work_data.csv", "CSV Files (*.csv)")
        if not path: return
        
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT date, type, description, hours, total_eur, direct_eur, fund_eur FROM records ORDER BY date")
        rows = c.fetchall()
        conn.close()
        
        try:
            with open(path, mode='w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f, delimiter=';')
                writer.writerow(["Ημερομηνία", "Τύπος", "Περιγραφή", "Ώρες", "Σύνολο (€)", "Άμεση Πληρωμή (€)", "Ταμείο Νοέμβρη (€)"])
                
                # Μετατροπή μορφών πριν την εγγραφή στο CSV για συμβατότητα με Excel
                formatted_rows = []
                for r in rows:
                    gr_date = datetime.strptime(r[0], "%Y-%m-%d").strftime("%d/%m/%Y")
                    hr_fmt = format_hours_to_clock(r[3])
                    formatted_rows.append([gr_date, r[1], r[2], hr_fmt, r[4], r[5], r[6]])
                    
                writer.writerows(formatted_rows)
            QMessageBox.information(self, "Επιτυχία", "Η εξαγωγή ολοκληρώθηκε!")
        except Exception as e:
            QMessageBox.critical(self, "Σφάλμα", f"Αποτυχία εξαγωγής:\n{str(e)}")

if __name__ == "__main__":
    init_db()
    app = QApplication(sys.argv)
    apply_theme(app)
    window = WorkTrackerApp()
    window.showMaximized()
    sys.exit(app.exec())