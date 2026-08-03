#!/usr/bin/env python
"""
=============================================================
create_admin.py — CRM v0.1 bootstrap: create/fix a CRM login
=============================================================
Version : 1.4
Author  : Built for Asian Properties / Srikanth

CHANGELOG
---------
v1.4  — BASE_DIR updated from C:\CLS to D:\CLS — drive migration, 2026-08.

v1.3  — NEW 'manager' role (oversight tier), matching cls_db.py v2.9 /
  app.py v0.9.5. Role choice is now validated against cls_db.CRM_ROLES
  (single source of truth) instead of a literal tuple here, so this
  script can never drift out of sync with the roles the app recognises.
  A manager is prompted for an owner_match_name just like a salesperson,
  because managers carry their own leads too ("player-coach"): they SEE
  every lead but WRITE only to their own, so they still need the Sell.do
  "Attended By" link. Admins are still asked for nothing extra (they see
  and write everything). The owner-name prompt now explains the manager
  case accurately (it identifies THEIR OWN leads — it does not restrict
  what a manager can see).

v1.2  — Salesperson logins now prompt for owner_match_name — the
  exact text (case-insensitive) that appears in Sell.do's "Attended
  By" field for that person, which is what leads.lead_owner holds.
  Without this, a salesperson would see either everyone's leads or
  nobody's, depending how their name happens to be typed.
  Also: if the email you enter already exists (e.g. fixing Elohar's
  account after the fact), this now offers to UPDATE that person's
  owner_match_name instead of just failing with "already exists".

v1.1  — Fixed missing sys.path insert. v1.0 did `import cls_db`
  directly, which only works if this script's own folder contains
  cls_db.py. Since cls_db.py actually lives one level up at C:\\CLS\\
  (this script lives in C:\\CLS\\crm\\), that import failed with
  ModuleNotFoundError. Now inserts C:\\CLS onto sys.path first, same
  pattern app.py already used correctly.

WHAT THIS DOES
--------------
Ensures cls.db has the 'users' table (calls cls_db.init_db(), which
is safe/idempotent — it only CREATEs/ALTERs tables that don't exist
yet and never touches existing data), then either creates a new login
or fixes an existing one's owner_match_name.

Run this once per person you need to onboard before v0.5 gets an
in-app "add teammate" screen.

USAGE
-----
  python create_admin.py
=============================================================
"""

import getpass
import sys
import os

# ── Import cls_db.py the same way app.py does — it lives in C:\CLS,
# one folder up from this script's C:\CLS\crm\ location. Without this,
# Python only looks in this script's own folder and site-packages, and
# never finds it (ModuleNotFoundError: No module named 'cls_db').
BASE_DIR = r"D:\CLS"
sys.path.insert(0, BASE_DIR)
import cls_db  # noqa: E402  (must follow the sys.path insert above)


def prompt_owner_match_name(role="salesperson"):
    print()
    if role == "manager":
        # A manager SEES every lead regardless of this value — it only
        # identifies the manager's OWN leads, so they can work them and
        # be attributed correctly. It does not restrict their view.
        print("This links the manager to their OWN leads (they still see")
        print("everyone's). Managers carry their own pipeline too, so we")
        print("need the exact Sell.do 'Attended By' text for their leads.")
    else:
        print("This person needs to be linked to how Sell.do identifies them,")
        print("so they only see their own leads (not everyone's).")
    print("Open Sell.do, find one of their leads, and copy the exact")
    print("'Attended By' text (e.g. 'Elohar Peddi'). Matching is")
    print("case-insensitive, but spelling must be exact otherwise.")
    return input("Owner name (as in Sell.do 'Attended By'): ").strip()


def main():
    cls_db.init_db()  # safe — only creates/alters what's missing, never touches data

    print("=" * 55)
    print(" CREATE OR FIX A CRM LOGIN")
    print("=" * 55)

    email = input("Email (login id)   : ").strip()

    conn = cls_db._connect()
    existing = conn.execute("SELECT * FROM users WHERE email=?", (cls_db.norm_email(email),)).fetchone()
    conn.close()

    if existing:
        print(f"\nA login already exists for {email} (role={existing['role']}).")
        choice = input("Update their owner_match_name now? [y/N]: ").strip().lower()
        if choice != "y":
            print("Nothing changed.")
            sys.exit(0)

        owner_match_name = prompt_owner_match_name()
        ok = cls_db.update_user_owner_match(email, owner_match_name)
        if ok:
            print(f"\n[OK] Updated {email} -> owner_match_name = '{owner_match_name}'")
        else:
            print("[FAIL] Could not find that user to update.")
            sys.exit(1)
        return

    # ── New user ──
    full_name = input("Full name          : ").strip()

    # Validate against cls_db.CRM_ROLES — the ONE place valid roles are
    # defined (admin > manager > salesperson). Keeps this script from ever
    # drifting from what the app actually recognises.
    role = ""
    role_prompt = "Role [" + "/".join(cls_db.CRM_ROLES) + "]: "
    while role not in cls_db.CRM_ROLES:
        role = input(role_prompt).strip().lower()

    # Both salespeople and managers carry their own leads, so both get an
    # owner_match_name. Admins see/write everything and need none.
    owner_match_name = None
    if role in ("salesperson", "manager"):
        owner_match_name = prompt_owner_match_name(role)

    password = getpass.getpass("Password           : ")
    password2 = getpass.getpass("Confirm password   : ")

    if password != password2:
        print("[FAIL] Passwords did not match. Nothing created.")
        sys.exit(1)

    if len(password) < 8:
        print("[FAIL] Password must be at least 8 characters. Nothing created.")
        sys.exit(1)

    try:
        user_id = cls_db.create_user(full_name, email, password, role, owner_match_name)
    except ValueError as e:
        print(f"[FAIL] {e}")
        sys.exit(1)

    print(f"\n[OK] Created user_id={user_id}  ({email}, role={role})")
    if owner_match_name:
        print(f"     Linked to Sell.do owner: '{owner_match_name}'")
    print("     You can now log in at /login with this email + password.")


if __name__ == "__main__":
    main()
