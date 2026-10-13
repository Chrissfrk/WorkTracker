"""Έλεγχοι για τη Διαχείριση, την ασφάλεια των φορμών και τη βασική λειτουργία της εφαρμογής.

Τρέχουν σε προσωρινή βάση (όχι στο work_data.db):  python -m unittest discover tests
"""
import os
import re
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SECRET_KEY", "test")
os.environ["INVITE_CODE"] = "invite-from-env"

import core  # noqa: E402

TMP = tempfile.TemporaryDirectory()
core.DB_NAME = os.path.join(TMP.name, "test.db")

from app import app  # noqa: E402  (το import τρέχει το init_db στην προσωρινή βάση)
from werkzeug.security import generate_password_hash  # noqa: E402

app.config["TESTING"] = True


@app.route("/boom-test")
def boom():
    raise ValueError("secret detail")


def db(sql, params=()):
    conn = sqlite3.connect(core.DB_NAME)
    try:
        rows = conn.execute(sql, params).fetchall()
        conn.commit()
        return rows
    finally:
        conn.close()


class Base(unittest.TestCase):
    def setUp(self):
        db("DELETE FROM records")
        db("DELETE FROM users")
        db("DELETE FROM settings")
        db("DELETE FROM activity")
        self.admin_id = core.create_user("boss", generate_password_hash("adminpass"))
        core.set_admin(self.admin_id, True)
        self.user_id = core.create_user("maria", generate_password_hash("userpass"))
        core.insert_bulk_to_db(self.user_id, [core.make_record("2026-10-01", "shift", "08:00", "16:00"),
                                              core.make_record("2026-10-02", "transfer")])

    def client_for(self, username=None, password=None):
        client = app.test_client()
        if username:
            r = self.post(client, "/login", {"username": username, "password": password}, page="/login")
            self.assertEqual(r.status_code, 302, "η σύνδεση απέτυχε")
        return client

    @staticmethod
    def token(client, page="/"):
        html = client.get(page).get_data(as_text=True)
        return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)

    def post(self, client, path, data=None, page="/"):
        return client.post(path, data={**(data or {}), "csrf_token": self.token(client, page)})


class AccessControl(Base):
    ADMIN_PAGES = ["/admin/", "/admin/users", "/admin/users/999", "/admin/activity",
                   "/admin/settings", "/admin/system"]

    def test_anonymous_is_sent_to_login(self):
        client = self.client_for()
        for path in self.ADMIN_PAGES:
            r = client.get(path)
            self.assertEqual(r.status_code, 302, path)
            self.assertIn("/login", r.headers["Location"])

    def test_regular_user_gets_404_everywhere(self):
        client = self.client_for("maria", "userpass")
        for path in self.ADMIN_PAGES:
            self.assertEqual(client.get(path).status_code, 404, path)
        for path in [f"/admin/users/{self.admin_id}/delete", f"/admin/users/{self.user_id}/status",
                     f"/admin/users/{self.user_id}/password", "/admin/settings"]:
            self.assertEqual(self.post(client, path, {"confirm": "maria", "action": "disable"}).status_code, 404, path)
        self.assertEqual(db("SELECT COUNT(*) FROM users")[0][0], 2)

    def test_admin_sees_every_page(self):
        client = self.client_for("boss", "adminpass")
        self.assertEqual(client.get("/admin/users/999").status_code, 404)  # Ανύπαρκτος χρήστης
        for path in [p for p in self.ADMIN_PAGES if p != "/admin/users/999"] + [f"/admin/users/{self.user_id}", "/admin/users?q=%25&role=admin&sort=login&page=9",
                                        "/admin/activity?kind=auth"]:
            r = client.get(path)
            self.assertEqual(r.status_code, 200, path)
            self.assertEqual(r.headers["Cache-Control"], "no-store")

    def test_admin_link_only_for_admins(self):
        self.assertNotIn("/admin/", self.client_for("maria", "userpass").get("/").get_data(as_text=True))
        self.assertIn("/admin/", self.client_for("boss", "adminpass").get("/").get_data(as_text=True))

    def test_revoking_admin_takes_effect_immediately(self):
        client = self.client_for("boss", "adminpass")
        core.set_admin(self.admin_id, False)
        self.assertEqual(client.get("/admin/").status_code, 404)

    def test_no_web_route_grants_admin(self):
        client = self.client_for("maria", "userpass")
        self.post(client, "/admin/settings", {"is_admin": "1"})
        self.post(client, "/register", {"is_admin": "1"})
        self.assertEqual(db("SELECT is_admin FROM users WHERE id=?", (self.user_id,))[0][0], 0)


class Csrf(Base):
    def test_post_without_token_is_rejected(self):
        client = self.client_for("maria", "userpass")
        r = client.post("/records", data={"date": "2026-10-05", "type": "transfer"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(db("SELECT COUNT(*) FROM records")[0][0], 2)

    def test_admin_post_without_token_is_rejected(self):
        client = self.client_for("boss", "adminpass")
        client.post(f"/admin/users/{self.user_id}/delete", data={"confirm": "maria"})
        self.assertEqual(db("SELECT COUNT(*) FROM users")[0][0], 2)

    def test_login_without_token_is_rejected(self):
        r = app.test_client().post("/login", data={"username": "maria", "password": "userpass"})
        self.assertEqual(db("SELECT last_login_at FROM users WHERE id=?", (self.user_id,))[0][0], None)

    def test_existing_features_still_work_with_token(self):
        client = self.client_for("maria", "userpass")
        self.post(client, "/records", {"date": "2026-10-05", "type": "transfer"})
        self.post(client, "/bulk", {"text": "6/10 9-17"})
        self.assertEqual(db("SELECT COUNT(*) FROM records WHERE user_id=?", (self.user_id,))[0][0], 4)
        rec_id = db("SELECT MAX(id) FROM records")[0][0]
        self.post(client, f"/records/{rec_id}/delete")
        self.assertEqual(db("SELECT COUNT(*) FROM records WHERE user_id=?", (self.user_id,))[0][0], 3)
        self.assertEqual(client.get("/export.csv").status_code, 200)


class UserManagement(Base):
    def test_reset_password_shows_once_and_ends_sessions(self):
        user_client = self.client_for("maria", "userpass")
        admin = self.client_for("boss", "adminpass")
        r = self.post(admin, f"/admin/users/{self.user_id}/password", page=f"/admin/users/{self.user_id}")
        html = r.get_data(as_text=True)
        password = re.search(r'id="new-password">([^<]+)<', html).group(1)
        self.assertEqual(r.headers["Cache-Control"], "no-store")
        self.assertEqual(user_client.get("/").status_code, 200)  # Η αρχική δείχνει την παρουσίαση...
        self.assertNotIn('id="entry-form"', user_client.get("/").get_data(as_text=True))  # ...όχι τα δεδομένα
        self.client_for("maria", password)
        log = db("SELECT detail FROM activity WHERE action='admin.reset_password'")
        self.assertEqual(len(log), 1)
        self.assertNotIn(password, str(db("SELECT * FROM activity")))

    def test_disable_and_enable(self):
        user_client = self.client_for("maria", "userpass")
        admin = self.client_for("boss", "adminpass")
        self.post(admin, f"/admin/users/{self.user_id}/status", {"action": "disable"})
        self.assertEqual(user_client.get("/export.csv").status_code, 302)
        r = self.post(app.test_client(), "/login", {"username": "maria", "password": "userpass"}, page="/login")
        self.assertEqual(r.status_code, 200)  # Μένει στη σελίδα σύνδεσης
        self.post(admin, f"/admin/users/{self.user_id}/status", {"action": "enable"})
        self.client_for("maria", "userpass")

    def test_delete_requires_typed_name(self):
        admin = self.client_for("boss", "adminpass")
        self.post(admin, f"/admin/users/{self.user_id}/delete", {"confirm": "wrong"})
        self.assertEqual(db("SELECT COUNT(*) FROM users")[0][0], 2)
        self.post(admin, f"/admin/users/{self.user_id}/delete", {"confirm": "Maria"})
        self.assertEqual(db("SELECT COUNT(*) FROM users")[0][0], 1)
        self.assertEqual(db("SELECT COUNT(*) FROM records")[0][0], 0)

    def test_admin_accounts_are_protected(self):
        other = core.create_user("boss2", generate_password_hash("x" * 8))
        core.set_admin(other, True)
        admin = self.client_for("boss", "adminpass")
        for uid in (self.admin_id, other):
            self.post(admin, f"/admin/users/{uid}/delete", {"confirm": "boss" if uid == self.admin_id else "boss2"})
            self.post(admin, f"/admin/users/{uid}/status", {"action": "disable"})
            self.post(admin, f"/admin/users/{uid}/password")
        self.assertEqual(db("SELECT COUNT(*) FROM users WHERE is_admin=1 AND disabled=0")[0][0], 2)
        self.client_for("boss", "adminpass")

    def test_search_escapes_wildcards_and_paginates(self):
        for i in range(30):
            core.create_user(f"user{i:02d}", "x")
        admin = self.client_for("boss", "adminpass")
        self.assertIn("Δεν βρέθηκαν χρήστες", admin.get("/admin/users?q=%25").get_data(as_text=True))
        page1 = admin.get("/admin/users?sort=name").get_data(as_text=True)
        page2 = admin.get("/admin/users?sort=name&page=2").get_data(as_text=True)
        self.assertIn("Σελίδα 1 από 2", page1)
        self.assertIn("user29", page2)
        self.assertNotIn("user29", page1)
        self.assertEqual(admin.get("/admin/users?sort=;DROP TABLE users").status_code, 200)


class Privacy(Base):
    """Ο διαχειριστής δεν βλέπει βάρδιες ή ποσά άλλων χρηστών."""

    def test_no_shifts_or_money_in_admin_pages(self):
        admin = self.client_for("boss", "adminpass")
        for path in ["/admin/", "/admin/users", f"/admin/users/{self.user_id}", "/admin/activity", "/admin/system"]:
            html = admin.get(path).get_data(as_text=True)
            for leak in ("€", "08:00", "Βάρδια", "Transfer", "Ταμείο", "Άμεση"):
                self.assertNotIn(leak, html, (path, leak))

    def test_records_browser_is_gone(self):
        admin = self.client_for("boss", "adminpass")
        self.assertEqual(admin.get("/admin/records").status_code, 404)
        rec_id = db("SELECT MIN(id) FROM records")[0][0]
        self.assertEqual(self.post(admin, f"/admin/records/{rec_id}/delete").status_code, 404)
        self.assertEqual(db("SELECT COUNT(*) FROM records")[0][0], 2)


class Settings(Base):
    def test_close_and_reopen_registration(self):
        admin = self.client_for("boss", "adminpass")
        self.post(admin, "/admin/settings", {"invite_code": "invite-from-env"})
        self.assertEqual(db("SELECT value FROM settings WHERE key='invite_code'"), [])  # Η τιμή του WSGI μένει προεπιλογή
        self.assertEqual(app.test_client().get("/register").status_code, 302)  # Κλειστό (χωρίς registration=on)
        self.post(admin, "/admin/settings", {"registration": "on", "invite_code": "new-code-123"})
        guest = app.test_client()
        self.assertEqual(guest.get("/register").status_code, 200)
        r = self.post(guest, "/register", {"invite": "invite-from-env", "username": "nikos", "password": "secret1",
                                           "confirm": "secret1"}, page="/register")
        self.assertEqual(r.status_code, 200)
        r = self.post(guest, "/register", {"invite": "new-code-123", "username": "nikos", "password": "secret1",
                                           "confirm": "secret1"}, page="/register")
        self.assertEqual(r.status_code, 302)
        self.assertNotIn("new-code-123", str(db("SELECT * FROM activity")))

    def test_invalid_code_rejected(self):
        admin = self.client_for("boss", "adminpass")
        self.post(admin, "/admin/settings", {"registration": "on", "invite_code": "has space"})
        self.assertEqual(db("SELECT value FROM settings WHERE key='invite_code'"), [])

    def test_generate(self):
        admin = self.client_for("boss", "adminpass")
        self.post(admin, "/admin/settings", {"registration": "on", "action": "generate"})
        self.assertEqual(len(db("SELECT value FROM settings WHERE key='invite_code'")), 1)


class Activity(Base):
    def test_logins_logged_without_secrets(self):
        self.post(app.test_client(), "/login", {"username": "maria", "password": "wrong"}, page="/login")
        self.post(app.test_client(), "/login", {"username": "my-password-typo", "password": "x"}, page="/login")
        self.client_for("maria", "userpass")
        log = str(db("SELECT * FROM activity"))
        self.assertNotIn("my-password-typo", log)
        self.assertNotIn("userpass", log)
        actions = [a for (a,) in db("SELECT action FROM activity ORDER BY id")]
        self.assertEqual(actions, ["login_failed", "login_failed", "login"])

    def test_log_is_bounded(self):
        for _ in range(5):
            core.log_activity("login")
        old = core.ACTIVITY_KEEP
        core.ACTIVITY_KEEP = 3
        try:
            core.log_activity("login")
        finally:
            core.ACTIVITY_KEEP = old
        self.assertEqual(db("SELECT COUNT(*) FROM activity")[0][0], 3)

    def test_server_error_is_logged_without_trace(self):
        app.config["TESTING"] = False
        app.config["PROPAGATE_EXCEPTIONS"] = False
        try:
            r = self.client_for("maria", "userpass").get("/boom-test")
        finally:
            app.config["TESTING"] = True
            app.config["PROPAGATE_EXCEPTIONS"] = None
        self.assertEqual(r.status_code, 500)
        self.assertNotIn("secret detail", r.get_data(as_text=True))
        self.assertEqual(db("SELECT target, detail FROM activity WHERE action='error'"), [("GET /boom-test", "ValueError")])


class Cli(Base):
    def test_set_admin_command(self):
        runner = app.test_cli_runner()
        result = runner.invoke(args=["set-admin", "maria"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(db("SELECT is_admin FROM users WHERE id=?", (self.user_id,))[0][0], 1)
        runner.invoke(args=["set-admin", "maria", "--revoke"])
        self.assertEqual(db("SELECT is_admin FROM users WHERE id=?", (self.user_id,))[0][0], 0)


class Migration(unittest.TestCase):
    def test_old_database_is_upgraded_and_old_sessions_survive(self):
        path = os.path.join(TMP.name, "old.db")
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE COLLATE NOCASE, "
                     "password_hash TEXT NOT NULL, created_at TEXT)")
        conn.execute("CREATE TABLE records (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, type TEXT, description TEXT, "
                     "hours REAL, total_eur REAL, direct_eur REAL, fund_eur REAL, user_id INTEGER)")
        conn.execute("INSERT INTO users (username, password_hash) VALUES ('old', 'x')")
        conn.commit()
        conn.close()
        current, core.DB_NAME = core.DB_NAME, path
        try:
            core.init_db()
            core.init_db()  # Δεύτερη φορά χωρίς σφάλμα
            user = core.get_user(1)
            self.assertEqual((user["is_admin"], user["disabled"], user["session_epoch"]), (0, 0, 0))
        finally:
            core.DB_NAME = current

    def test_session_from_before_upgrade_stays_valid(self):
        uid = core.create_user("legacy", generate_password_hash("legacypw"))
        client = app.test_client()
        with client.session_transaction() as s:
            s["user_id"] = uid  # Χωρίς "epoch", όπως οι συνεδρίες πριν την αναβάθμιση
        self.assertIn('id="entry-form"', client.get("/").get_data(as_text=True))


class Headers(Base):
    def test_security_headers(self):
        r = app.test_client().get("/login")
        self.assertEqual(r.headers["X-Frame-Options"], "DENY")
        self.assertEqual(r.headers["X-Content-Type-Options"], "nosniff")
        self.assertIn("SameSite=Lax", r.headers["Set-Cookie"])
        self.assertIn("HttpOnly", r.headers["Set-Cookie"])


if __name__ == "__main__":
    unittest.main()
