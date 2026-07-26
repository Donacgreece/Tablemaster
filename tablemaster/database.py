"""SQLite connection and initialization helpers."""

import os
import sqlite3

DATABASE_PATH = os.environ.get("TABLEMASTER_DATABASE_PATH", "database.db")
AUDIT_DATABASE_PATH = os.environ.get("TABLEMASTER_AUDIT_DATABASE_PATH", "audit_logs.db")

# Συνάρτηση για τη σύνδεση με τη βάση δεδομένων SQLite
def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def get_audit_db_connection():
    conn = sqlite3.connect(AUDIT_DATABASE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_audit_db():
    conn = sqlite3.connect(AUDIT_DATABASE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    with open('audit_schema.sql', 'r', encoding='utf-8') as f:
        conn.executescript(f.read())
    conn.close()

# Συνάρτηση για την αρχικοποίηση της βάσης δεδομένων από το schema.sql
def init_db():
    conn = get_db_connection()
    with open('schema.sql', 'r', encoding='utf-8') as f:
        conn.executescript(f.read())

    # Εξασφάλιση ότι υπάρχει προεπιλεγμένη τιμή για το session_timeout
    existing_timeout = conn.execute('SELECT value FROM settings WHERE name = "session_timeout"').fetchone()
    if not existing_timeout:
        conn.execute('INSERT INTO settings (name, value) VALUES (?, ?)', ('session_timeout', '10'))

    conn.commit()
    conn.close()

# Συνάρτηση για τη δημιουργία ενός διαχειριστή αν δεν υπάρχει
def create_admin_if_not_exists():
    conn = get_db_connection()
    # Ελέγχουμε αν υπάρχει ήδη χρήστης με ρόλο 'admin'
    admin_exists = conn.execute('SELECT * FROM users WHERE role = ?', ('admin',)).fetchone()
    if not admin_exists:
        # Αν δεν υπάρχει, δημιουργούμε έναν χρήστη διαχειριστή
        conn.execute('INSERT INTO users (first_name, last_name, pin, role) VALUES (?, ?, ?, ?)',
                    ('Admin', 'User', '4101', 'admin'))
        conn.commit()
    conn.close()
