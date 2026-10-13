# Work Tracker

A small Flask web app for logging shifts, transfers and the November fund. It runs on PythonAnywhere (free tier) and works from any browser, on laptop or phone.

Each person has their own account and only sees their own records. To create an account, people need the **invite code** you set (`INVITE_CODE`). Without it, sign-up is closed.

> **The first account ever created gets all records from the old single-user database.** Create your own account first, before you share the invite code.

## Run locally

1. Put an invite code in the `.env` file next to `app.py`: `INVITE_CODE=anything-you-like`
2. Double-click `run_local.bat`. A browser opens at http://localhost:5000.
3. Click **Δημιουργία λογαριασμού**, enter the invite code, and pick a username and password.
4. To stop, close the black window.

To try it on your phone over the same Wi-Fi, open `http://<PC-IP>:5000`. Find the PC's IP with `ipconfig`. Windows may ask to allow Python through the firewall.

## Deploy to PythonAnywhere (first time)

1. Create a free **Beginner** account at https://www.pythonanywhere.com. Your username becomes the URL: `https://<username>.pythonanywhere.com`.
2. On your PC, build the zip **including the database**:
   ```powershell
   .\make_upload_zip.ps1 -WithDb
   ```
3. In PythonAnywhere, go to **Files** and upload `worktracker.zip` into `/home/<username>/`.
4. Go to **Consoles → Bash** and run:
   ```bash
   mkdir -p ~/WorkTracker && cd ~/WorkTracker && unzip -o ~/worktracker.zip && rm ~/worktracker.zip
   mkvirtualenv worktracker --python=python3.13
   pip install -r requirements.txt
   python -c "import secrets; print(secrets.token_hex(32))"   # copy this for SECRET_KEY
   ```
   If `python3.13` isn't available, use `python3.12`. The app works with any Python 3.9+.
5. Go to **Web → Add a new web app → Next → Manual configuration → Python 3.13**. Then set:
   - **Source code:** `/home/<username>/WorkTracker`
   - **Virtualenv:** `/home/<username>/.virtualenvs/worktracker`
   - **Force HTTPS:** Enabled
6. On the same page, click the **WSGI configuration file** link. Delete everything in it and paste:
   ```python
   import os, sys

   os.environ["INVITE_CODE"] = "the-code-you-give-to-coworkers"
   os.environ["SECRET_KEY"] = "the-value-from-step-4"
   os.environ["SECURE_COOKIES"] = "1"   # login cookie only over HTTPS

   path = "/home/<username>/WorkTracker"
   if path not in sys.path:
       sys.path.insert(0, path)

   from app import app as application
   ```
   Save, go back to the Web tab and press **Reload**.
7. Open `https://<username>.pythonanywhere.com`. If you uploaded a database where you already have an account, log in. Otherwise click **Δημιουργία λογαριασμού** and create yours **first**, so your existing records go to you. Then share the URL and the invite code with others.

## Admin panel

Admins get a **Διαχείριση** button in the app's top bar, which opens `/admin`. It runs inside the same web app: no extra process, worker or dependency.

Admins manage **accounts, not data**: the panel never shows anyone's shifts, hours or pay.

- **Επισκόπηση:** counts of users and active users, recent activity, and warnings about errors or repeated failed logins.
- **Χρήστες:** search, filter, sort and page through users. Open a user to see when they joined, their last login and their recent activity. From there you can give them a new temporary password (shown once), disable or re-enable the account, or delete it along with its records (you must type the username to confirm).
- **Δραστηριότητα:** logins, failed logins, sign-ups, admin actions and server errors. Only the latest 5,000 entries are kept.
- **Ρυθμίσεις:** open or close sign-ups and change or regenerate the invite code. This takes effect immediately, with no Reload needed. The value set here overrides `INVITE_CODE` in the WSGI file.
- **Σύστημα:** Python, Flask and SQLite versions, time since restart, process memory, database size, and recent errors.

### Who is an admin

For safety, admin rights can only be granted or removed from a **Bash console**, never from the website. Admin accounts can't be disabled, deleted or have their password reset from the panel.

```bash
cd ~/WorkTracker && workon worktracker
flask --app app set-admin <username>            # make someone an admin
flask --app app set-admin <username> --revoke   # remove admin rights
```

The database gets the new columns and tables automatically the first time the updated app starts.

## Managing users from the console

```bash
cd ~/WorkTracker && workon worktracker
flask --app app list-users                  # who exists + how many records each has
flask --app app reset-password <username>   # set a new password for someone who forgot theirs
```

- **Close sign-ups:** use Διαχείριση → Ρυθμίσεις, or remove the `INVITE_CODE` line from the WSGI file and press Reload.
- **Change the invite code:** use Διαχείριση → Ρυθμίσεις, or edit the line in the WSGI file and press Reload.

### On your phone
Open the URL, log in, then add it to your home screen:
- **iPhone (Safari):** Share → *Add to Home Screen*
- **Android (Chrome):** ⋮ → *Add to Home screen* / *Install app*

It then opens like a normal app, and you stay logged in for a year.

## Updating code

```powershell
.\make_upload_zip.ps1          # without -WithDb, so the live data isn't overwritten
```
Upload it to `/home/<username>/`, then in Bash run `cd ~/WorkTracker && unzip -o ~/worktracker.zip && rm ~/worktracker.zip`, and press **Reload** on the Web tab.

## Upkeep (free tier)

- **Every 3 months:** go to the Web tab and click **"Run until 3 months from today"**. You'll get a reminder email. If you miss it, the site is disabled but your data is kept.
- **Backups:** use the **Export CSV** button in the app, or download `WorkTracker/work_data.db` from the Files tab.

## Files

- `app.py`: Flask routes, accounts, CSRF protection, console admin commands
- `admin.py`: the admin panel (`/admin`)
- `core.py`: pay calculation, bulk-text and PDF parsing, SQLite access, settings and activity log
- `tests/`: automated checks, run with `python -m unittest discover tests` (they use a temporary database)
- `templates/`, `static/`: UI (HTML/CSS/JS, icons)
- `work_data.db`: the database
- `_backup_desktop/`: the old PyQt desktop version (not uploaded)
