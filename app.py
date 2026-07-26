import os
import io
import re
import json
import time 
import uuid
import shutil
import zipfile
import socket
import sqlite3
import hashlib
import logging
import threading
import ipaddress
import subprocess
import pandas as pd
from datetime import datetime, timedelta
from escpos.printer import Network
from cryptography.fernet import Fernet
from werkzeug.utils import secure_filename
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file, send_from_directory



# Συνάρτηση για να πάρει τη MAC διεύθυνση της συσκευής
def get_mac_address():
    """
    Επιστρέφει τη MAC διεύθυνση της συσκευής χρησιμοποιώντας εντολές συστήματος.
    """
    try:
        if os.name == "nt":  # Windows
            output = subprocess.check_output("ipconfig /all", shell=True).decode('utf-8', errors='ignore')
            print("Έξοδος ipconfig:\n", output)  # Προσθήκη εκτύπωσης για έλεγχο
            mac_address = re.search(r"([A-F0-9]{2}[:-]){5}([A-F0-9]{2})", output, re.I)
        else:  # Unix/Linux/Mac
            output = subprocess.check_output("ifconfig", shell=True).decode()
            print("Έξοδος ifconfig:\n", output)  # Προσθήκη εκτύπωσης για έλεγχο
            mac_address = re.search(r"([a-f0-9]{2}(:[a-f0-9]{2}){5})", output)

        if mac_address:
            return mac_address.group(0).upper()  # Μετατροπή σε κεφαλαία γράμματα
        else:
            print("Δεν βρέθηκε MAC διεύθυνση.")
            return None

    except Exception as e:
        print(f"Σφάλμα κατά την ανάκτηση της MAC διεύθυνσης: {e}")
        return None

def decrypt_license_key(encrypted_key, key):
    fernet = Fernet(key)
    try:
        decrypted_key = fernet.decrypt(encrypted_key).decode()
        return decrypted_key
    except Exception:
        return None

def decrypt_license_key(encrypted_key, key):
    fernet = Fernet(key)
    try:
        decrypted_key = fernet.decrypt(encrypted_key).decode()
        return decrypted_key
    except Exception:
        return None

def get_encryption_key(file_path='encryption.key'):
    """
    Διαβάζει το κλειδί κρυπτογράφησης από το αρχείο.
    """
    try:
        with open(file_path, 'rb') as file:
            return file.read().strip()  # Αφαιρεί περιττά κενά και αλλαγές γραμμής
    except FileNotFoundError:
        print(f"Το αρχείο {file_path} δεν βρέθηκε. Παρακαλώ βεβαιωθείτε ότι υπάρχει.")
        return None

def check_license():
    """
    Ελέγχει την εγκυρότητα της άδειας χρήσης.
    """
    try:
        # Ανάγνωση του κρυπτογραφημένου License Key από το αρχείο
        with open('license.key', 'rb') as file:
            encrypted_key = file.read()

        # Ανάγνωση του κλειδιού κρυπτογράφησης από το αρχείο
        key = get_encryption_key()
        if key is None:
            print("Δεν βρέθηκε το κλειδί κρυπτογράφησης. Ελέγξτε το αρχείο encryption.key.")
            return False

        # Αποκρυπτογράφηση του License Key
        decrypted_key = decrypt_license_key(encrypted_key, key)

        # Ανάκτηση της MAC διεύθυνσης
        mac_address = get_mac_address()
        if not mac_address:
            print("Δεν ήταν δυνατή η ανάκτηση της MAC διεύθυνσης.")
            return False

        print(f"Η ανακτηθείσα MAC διεύθυνση είναι: {mac_address}")
        print(f"Το αποκρυπτογραφημένο License Key είναι: {decrypted_key}")

        # Δημιουργία του αναμενόμενου License Key
        normalized_mac = mac_address.replace(":", "").replace("-", "").upper()
        expected_license_key = f"LICENSE-{normalized_mac}"
        print(f"Το αναμενόμενο License Key είναι: {expected_license_key}")

        # Σύγκριση του αποκρυπτογραφημένου License Key με το αναμενόμενο
        if decrypted_key == expected_license_key:
            print("Η άδεια είναι έγκυρη.")
            return True
        else:
            print("Η άδεια δεν είναι έγκυρη.")
            return False
    except FileNotFoundError:
        print("Το αρχείο license.key δεν βρέθηκε.")
        return False

def get_license_key():
    """
    Επιστρέφει το αποκρυπτογραφημένο License Key από το αρχείο license.key.
    """
    try:
        # Ανάγνωση του κρυπτογραφημένου License Key από το αρχείο
        with open('license.key', 'rb') as file:
            encrypted_key = file.read()

        # Ανάγνωση του κλειδιού κρυπτογράφησης από το αρχείο
        key = get_encryption_key()
        if key is None:
            print("Δεν βρέθηκε το κλειδί κρυπτογράφησης. Ελέγξτε το αρχείο encryption.key.")
            return None

        # Αποκρυπτογράφηση του License Key
        decrypted_key = decrypt_license_key(encrypted_key, key)
        return decrypted_key
    except FileNotFoundError:
        print("Το αρχείο license.key δεν βρέθηκε.")
        return None
    
# Έλεγχος άδειας πριν την εκκίνηση της εφαρμογής
if not check_license():
    print("Η άδεια δεν είναι έγκυρη ή δεν βρέθηκε. Παρακαλώ αγοράστε μια έγκυρη άδεια.")
    
    # Δημιουργία μίας μίνι εφαρμογής Flask για εμφάνιση μηνύματος αγοράς άδειας
    app = Flask(__name__)

    @app.route('/')
    def license_error():
        return render_template('license_error.html')

    if __name__ == '__main__':
        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
else:

    # Αρχικοποίηση της εφαρμογής Flask
    app = Flask(__name__)

    # Ορίζουμε το μυστικό κλειδί για τη διαχείριση των sessions
    app.secret_key = os.environ.get('TABLEMASTER_SECRET_KEY', os.urandom(32))

    # Ρύθμιση του session για να λήγει μετά από 10 λεπτά
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=10)

    # Ορίζουμε το φάκελο για την αποθήκευση των ανεβασμένων αρχείων
    UPLOAD_FOLDER = 'uploads'
    # Ορίζουμε τους επιτρεπόμενους τύπους αρχείων
    ALLOWED_EXTENSIONS = {'xls', 'xlsx'}

    # Ρυθμίζουμε την εφαρμογή Flask να χρησιμοποιεί το φάκελο UPLOAD_FOLDER για την αποθήκευση αρχείων
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

    # Συνάρτηση για τη σύνδεση με τη βάση δεδομένων SQLite
    def get_db_connection():
        conn = sqlite3.connect('database.db', check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
    
    def get_audit_db_connection():
        conn = sqlite3.connect('audit_logs.db', check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_audit_db():
        conn = sqlite3.connect('audit_logs.db', check_same_thread=False)
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

    # Συνάρτηση για να ελέγξουμε αν το αρχείο που ανεβαίνει έχει επιτρεπόμενο τύπο
    def allowed_file(filename):
        return '.' in filename and \
            filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

    # Συνάρτηση για την επεξεργασία του αρχείου Excel
    def process_excel_file(file_path):
        # Ανοίγουμε το Excel αρχείο
        xls = pd.ExcelFile(file_path)

        # Δημιουργούμε ένα σύνολο για τα ονόματα των προϊόντων που είναι στο αρχείο Excel
        excel_products = set()
        excel_categories = set()

        # Διαπερνάμε όλες τις καρτέλες (sheets) του αρχείου
        for sheet_name in xls.sheet_names:
            # Αποσπάμε το όνομα της κατηγορίας και το ποσοστό ΦΠΑ από το όνομα της καρτέλας
            category_info = sheet_name.split('(')
            category_name = category_info[0].strip()
            vat_rate = category_info[1].rstrip('%)').strip() if len(category_info) > 1 else "24"  # Default 24% VAT

            # Προσθήκη της κατηγορίας στο σύνολο excel_categories
            excel_categories.add(category_name)

            # Διαβάζουμε τα δεδομένα της καρτέλας σε ένα DataFrame
            df = pd.read_excel(xls, sheet_name)

            # Σύνδεση με τη βάση δεδομένων
            conn = get_db_connection()

            # Ελέγχουμε αν η κατηγορία υπάρχει στη βάση δεδομένων και είναι απενεργοποιημένη
            category = conn.execute('SELECT id, is_active FROM categories WHERE name = ?', (category_name,)).fetchone()
            if not category:
                # Δημιουργία κατηγορίας αν δεν υπάρχει
                conn.execute('INSERT INTO categories (name, vat_rate, is_active) VALUES (?, ?, ?)', (category_name, vat_rate, 1))
                category_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
            else:
                category_id = category['id']
                if category['is_active'] == 0:
                    # Αν η κατηγορία είναι απενεργοποιημένη, την ενεργοποιούμε
                    conn.execute('UPDATE categories SET is_active = 1 WHERE id = ?', (category_id,))

            # Ανάγνωση και εισαγωγή των υποκατηγοριών (μία φορά για κάθε κατηγορία)
            subcategories = str(df['Subcategories'][0]).split(',') if 'Subcategories' in df.columns and pd.notna(df['Subcategories'][0]) else []
            for subcategory_name in subcategories:
                subcategory_name = subcategory_name.strip()
                if subcategory_name:
                    subcategory = conn.execute('SELECT id FROM subcategories WHERE name = ? AND category_id = ?', (subcategory_name, category_id)).fetchone()
                    if not subcategory:
                        conn.execute('INSERT INTO subcategories (name, category_id) VALUES (?, ?)', (subcategory_name, category_id))

            # Εισαγωγή ή ενημέρωση προϊόντων
            for index, row in df.iterrows():
                product_name = str(row['Product Name']).strip()
                product_price = float(row['Price'])
                
                # Διασφαλίζουμε σωστή μετατροπή της τιμής 'Active'
                active_value = str(row.get('Active', 'yes')).strip().lower()
                is_active = active_value in ('yes', '1')  # Δέχεται "yes" ή "1" για ενεργό

                # Προσθήκη του προϊόντος στο σύνολο excel_products
                excel_products.add(product_name)

                # Έλεγχος αν το προϊόν υπάρχει ήδη
                product = conn.execute('SELECT id, is_active FROM products WHERE name = ? AND category_id = ?', (product_name, category_id)).fetchone()
                if not product:
                    # Εισαγωγή προϊόντος αν δεν υπάρχει
                    conn.execute('INSERT INTO products (name, price, category_id, is_active) VALUES (?, ?, ?, ?)',
                                (product_name, product_price, category_id, is_active))
                else:
                    # Ενημέρωση τιμής προϊόντος και κατάστασης αν υπάρχει
                    conn.execute('UPDATE products SET price = ?, is_active = ? WHERE id = ?', (product_price, is_active, product['id']))
                    # Αν το προϊόν ήταν απενεργοποιημένο, το ενεργοποιούμε ξανά
                    if product['is_active'] == 0:
                        conn.execute('UPDATE products SET is_active = 1 WHERE id = ?', (product['id'],))

            # Κλείνουμε τη σύνδεση
            conn.commit()
            conn.close()

        # Έλεγχος για προϊόντα που υπάρχουν στη βάση δεδομένων αλλά όχι στο Excel (πρέπει να απενεργοποιηθούν)
        conn = get_db_connection()
        db_products = conn.execute('SELECT name, id FROM products WHERE is_active = 1').fetchall()
        db_product_names = set(product['name'] for product in db_products)

        # Προϊόντα που είναι στη βάση δεδομένων αλλά όχι στο Excel
        products_to_disable = db_product_names - excel_products

        # Απενεργοποίηση προϊόντων που δεν υπάρχουν πλέον στο Excel
        for product_name in products_to_disable:
            conn.execute('UPDATE products SET is_active = 0 WHERE name = ?', (product_name,))

        # Έλεγχος για κατηγορίες που υπάρχουν στη βάση δεδομένων αλλά όχι στο Excel (πρέπει να απενεργοποιηθούν)
        db_categories = conn.execute('SELECT name, id FROM categories WHERE is_active = 1').fetchall()
        db_category_names = set(category['name'] for category in db_categories)

        # Κατηγορίες που είναι στη βάση δεδομένων αλλά όχι στο Excel
        categories_to_disable = db_category_names - excel_categories

        # Απενεργοποίηση κατηγοριών που δεν υπάρχουν πλέον στο Excel
        for category_name in categories_to_disable:
            conn.execute('UPDATE categories SET is_active = 0 WHERE name = ?', (category_name,))

        conn.commit()
        conn.close()

    # Έλεγχος διαθεσιμότητας εκτυπωτή με βάση τη διεύθυνση IP
    def is_printer_available(ip_address):
        try:
            with socket.create_connection((ip_address, 9100), timeout=5):
                return True
        except socket.timeout:
            logging.warning(f"Printer {ip_address} timed out.")
        except OSError as e:
            logging.warning(f"Printer {ip_address} is not reachable. Error: {e}")
        return False

    def send_to_printer_async(ip_address, text):
        thread = threading.Thread(target=send_to_printer, args=(ip_address, text))
        thread.start()

    # Αποστολή δεδομένων στον εκτυπωτή
    def send_to_printer(ip_address, text):
        try:
            # Καθορισμός χρόνου αναμονής κατά τη σύνδεση με τον εκτυπωτή
            printer = Network(ip_address, timeout=2)  # 2 δευτερόλεπτα χρόνος αναμονής

            printer.text(text)
            printer.cut()
            printer.close()
        except Exception as e:
            # Καταγραφή του σφάλματος στο terminal αλλά χωρίς να σταματά η εκτέλεση
            print(f"Failed to print to {ip_address}: {e}")

    # Αποστολή παραγγελίας σε εκτυπωτή βάσει των κατηγοριών προϊόντων
    def send_order_to_printer(order_items, table_number):
        conn = get_db_connection()

        printer_orders = {}

        for item in order_items:
            category_id = item['category_id']
            # Εύρεση εκτυπωτών που συνδέονται με την κατηγορία προϊόντος
            printers = conn.execute('''
                SELECT p.id, p.ip_address 
                FROM printers p
                JOIN printer_categories pc ON p.id = pc.printer_id
                WHERE pc.category_id = ?
            ''', (category_id,)).fetchall()

            for printer in printers:
                printer_id = printer['id']
                if printer_id not in printer_orders:
                    printer_orders[printer_id] = {
                        'ip_address': printer['ip_address'],
                        'items': []
                    }
                # Προσθήκη του προϊόντος στη λίστα για τον αντίστοιχο εκτυπωτή
                printer_orders[printer_id]['items'].append(dict(item))  # Βεβαιωθείτε ότι η υποκατηγορία περιλαμβάνεται

        conn.close()

        for printer_id, printer_data in printer_orders.items():
            if is_printer_available(printer_data['ip_address']):
                # Δημιουργία του κειμένου παραγγελίας για εκτύπωση με την υποκατηγορία
                order_text = format_order_for_print(printer_data['items'], table_number)
                send_to_printer(printer_data['ip_address'], order_text)
            else:
                # Αν ο εκτυπωτής δεν είναι διαθέσιμος, αποθηκεύουμε την παραγγελία για αργότερα
                save_order_for_later(printer_id, printer_data['items'], table_number)

    # Αποθήκευση παραγγελίας για αργότερα όταν ο εκτυπωτής δεν είναι διαθέσιμος
    def save_order_for_later(printer_id, order_items, table_name, is_receipt=False):
        """
        Αποθηκεύει εκκρεμείς παραγγελίες στη βάση δεδομένων για μελλοντική εκτύπωση.
        """
        def save_to_db():
            retries = 5  # Μέγιστες προσπάθειες
            delay = 0.5  # Καθυστέρηση ανάμεσα στις προσπάθειες

            order_items_dict = [dict(item) for item in order_items]  # Μετατροπή σε JSON συμβατή μορφή

            while retries > 0:
                try:
                    conn = get_db_connection()
                    conn.execute('''
                        INSERT INTO pending_prints (printer_id, order_data, table_number, is_receipt)
                        VALUES (?, ?, ?, ?)
                    ''', (printer_id, json.dumps(order_items_dict), table_name, is_receipt))
                    conn.commit()
                    logging.info(f"Order saved for later: {order_items_dict}")
                    return True  # Επιτυχής αποθήκευση
                except sqlite3.OperationalError as e:
                    if 'database is locked' in str(e):
                        logging.warning(f"Database is locked. Retrying... Attempts left: {retries - 1}")
                        retries -= 1
                        time.sleep(delay)
                    else:
                        logging.error(f"Failed to save order for later: {e}")
                        break
                except Exception as ex:
                    logging.error(f"Unexpected error while saving order: {ex}")
                    break
                finally:
                    if 'conn' in locals() and conn:
                        conn.close()

            logging.error(f"Exceeded max retries. Order not saved: {json.dumps(order_items_dict, indent=2)}")
            return False  # Αποτυχία αποθήκευσης

        save_thread = threading.Thread(target=save_to_db)
        save_thread.start()
        
    # Συνάρτηση επαναπροσπάθειας εκτύπωσης παραγγελιών που είχαν αποθηκευτεί για αργότερα
    def retry_pending_prints():
        conn = get_db_connection()
        # Ανάκτηση όλων των εκκρεμών παραγγελιών για εκτύπωση
        pending_jobs = conn.execute('SELECT * FROM pending_prints').fetchall()

        for job in pending_jobs:
            printer_ip = get_printer_ip_by_id(job['printer_id'])

            if is_printer_available(printer_ip):
                order_items = json.loads(job['order_data'])
                if job['is_receipt']:
                    receipt_text = format_receipt_for_print(order_items, job['table_number'])
                    send_to_printer(printer_ip, receipt_text)
                else:
                    order_text = format_order_for_print(order_items, job['table_number'])
                    send_to_printer(printer_ip, order_text)

                # Διαγραφή της εγγραφής μετά την επιτυχή εκτύπωση
                conn.execute('DELETE FROM pending_prints WHERE id = ?', (job['id'],))
                logging.info(f"Successfully printed and deleted job {job['id']} for printer {printer_ip}")
            else:
                logging.warning(f"Printer {printer_ip} still unavailable. Job {job['id']} not printed.")

        conn.commit()
        conn.close()

    # Προγραμματισμός περιοδικού ελέγχου για εκκρεμείς εκτυπώσεις με χρήση της βιβλιοθήκης APScheduler
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=retry_pending_prints, trigger="interval", minutes=1)
    scheduler.start()

    logging.basicConfig(level=logging.INFO)

    # Συνάρτηση για την ανάκτηση της IP διεύθυνσης εκτυπωτή με βάση το ID του
    def get_printer_ip_by_id(printer_id):
        conn = get_db_connection()
        printer = conn.execute('SELECT ip_address FROM printers WHERE id = ?', (printer_id,)).fetchone()
        conn.close()
        return printer['ip_address'] if printer else None

    def handle_receipt_printing(invoice_printer_id, receipt_text, order, table_id, order_id, payment_method):
        conn = get_db_connection()
        
        # Βρίσκουμε τον εκτυπωτή για τις αποδείξεις από τη βάση δεδομένων
        result = conn.execute('SELECT ip_address FROM printers WHERE id = ?', (invoice_printer_id,)).fetchone()
        conn.close()

        if result is None:
            print('Δεν βρέθηκε εκτυπωτής με το συγκεκριμένο ID. Το τραπέζι έκλεισε χωρίς εκτύπωση.')
        else:
            printer_ip = result['ip_address']
            # Έλεγχος αν ο εκτυπωτής είναι διαθέσιμος
            if is_printer_available(printer_ip):
                # Αποστολή της απόδειξης στον εκτυπωτή
                send_to_printer(printer_ip, receipt_text)
            else:
                # Αν ο εκτυπωτής δεν είναι διαθέσιμος, αποθηκεύουμε την απόδειξη για αργότερα
                save_receipt_for_later(invoice_printer_id, order, table_id, order_id, payment_method)

    # Μορφοποίηση κειμένου παραγγελίας για εκτύπωση
    def format_order_for_print(order_items, table_number):
        line_length = 40  # Μήκος γραμμής για στοίχιση
        separator = "-" * line_length

        order_lines = [
            f"**** TableMaster ****\n".center(line_length),
            f"Τραπέζι: {table_number}".center(line_length),
            f"Ημερομηνία: {datetime.now().strftime('%d/%m/%Y %H:%M')}".center(line_length),
            separator
        ]

        # Ταξινόμηση προϊόντων με βάση την κατηγορία
        order_items.sort(key=lambda x: x['category_name'])

        current_category = None

        for idx, item in enumerate(order_items, start=1):
            # Εμφάνιση επικεφαλίδας κατηγορίας αν αλλάζει η κατηγορία
            if current_category != item['category_name']:
                if current_category is not None:
                    order_lines.append(separator)  # Προσθήκη διαχωριστικής γραμμής μεταξύ κατηγοριών
                current_category = item['category_name']
                order_lines.append(f"** {current_category} **".center(line_length))
                order_lines.append(separator)

            # Προετοιμασία κειμένου προϊόντος
            subcategory_text = f" ({item['subcategory_names']})" if item.get('subcategory_names') else ''  # Προσθήκη της υποκατηγορίας αν υπάρχει
            product_line = f"{idx}. {item['name']}{subcategory_text}"  # Εμφάνιση προϊόντος και υποκατηγορίας

            # Προσθήκη προϊόντος με στοίχιση
            order_lines.append(product_line)
            
            # Εισαγωγή ποσότητας με στοίχιση ακριβώς κάτω από το όνομα του προϊόντος
            quantity_indent = " " * (len(str(idx)) + 2)  # Υπολογισμός του κενού για την ποσότητα
            order_lines.append(f"{quantity_indent}Ποσότητα: {item['quantity']}")
            
            if item['comments']:
                order_lines.append(f"{quantity_indent}Σχόλια: {item['comments']}")

            # Προσθήκη κενού ανάμεσα στα προϊόντα
            order_lines.append("")

        order_lines.append(separator)

        return "\n".join(order_lines)
    def save_order_for_later(printer_id, order_items, table_name, is_receipt=False):
            """
            Αποθηκεύει εκκρεμείς παραγγελίες στη βάση δεδομένων για μελλοντική εκτύπωση.
            """
            def save_to_db():
                retries = 5  # Μέγιστες προσπάθειες
                delay = 0.5  # Καθυστέρηση ανάμεσα στις προσπάθειες

                order_items_dict = [dict(item) for item in order_items]  # Μετατροπή σε JSON συμβατή μορφή

                while retries > 0:
                    try:
                        conn = get_db_connection()
                        conn.execute('''
                            INSERT INTO pending_prints (printer_id, order_data, table_number, is_receipt)
                            VALUES (?, ?, ?, ?)
                        ''', (printer_id, json.dumps(order_items_dict), table_name, is_receipt))
                        conn.commit()
                        logging.info(f"Order saved for later: {order_items_dict}")
                        break  # Αν επιτύχει, διακόπτουμε το loop
                    except sqlite3.OperationalError as e:
                        if 'database is locked' in str(e):
                            logging.warning("Database is locked. Retrying...")
                            retries -= 1
                            time.sleep(delay)  # Αναμονή πριν την επανάληψη
                        else:
                            logging.error(f"Failed to save order for later: {e}")
                            break
                    except Exception as ex:
                        logging.error(f"Unexpected error while saving order: {ex}")
                        break
                    finally:
                        if 'conn' in locals() and conn:
                            conn.close()

                if retries == 0:
                    logging.error(f"Exceeded max retries. Order not saved: {order_items_dict}")

            # Εκτέλεση της αποθήκευσης σε ξεχωριστό thread
            save_thread = threading.Thread(target=save_to_db)
            save_thread.start()
            
    def save_receipt_for_later(printer_id, receipt_data, table_number, receipt_number, payment_method):
        # Μετατροπή του `sqlite3.Row` σε κανονικό λεξικό
        receipt_dict = [dict(row) for row in receipt_data]

        conn = get_db_connection()
        conn.execute('''
            INSERT INTO pending_receipts (printer_id, receipt_data, table_number, receipt_number, payment_method)
            VALUES (?, ?, ?, ?, ?)
        ''', (printer_id, json.dumps(receipt_dict), table_number, receipt_number, payment_method))
        conn.commit()
        conn.close()

    def retry_pending_receipts():
        conn = get_db_connection()
        try:
            # Ανάκτηση όλων των εκκρεμών αποδείξεων για εκτύπωση
            pending_receipts = conn.execute('SELECT * FROM pending_receipts').fetchall()

            for receipt in pending_receipts:
                printer_ip = get_printer_ip_by_id(receipt['printer_id'])

                if is_printer_available(printer_ip):
                    receipt_data = json.loads(receipt['receipt_data'])

                    # Ανάκτηση της order_date από τη βάση δεδομένων βάσει του receipt_number
                    order_date_row = conn.execute(
                        'SELECT order_date FROM orders WHERE id = ?', 
                        (receipt['receipt_number'],)
                    ).fetchone()

                    if order_date_row:
                        order_date = order_date_row['order_date']
                    else:
                        logging.error(f"Order date not found for receipt number {receipt['receipt_number']}.")
                        continue  # Παράλειψη αυτής της απόδειξης

                    # Κλήση της format_receipt_for_print με την order_date
                    receipt_text, _ = format_receipt_for_print(
                        receipt_data, 
                        receipt['table_number'], 
                        receipt['receipt_number'], 
                        receipt['payment_method'], 
                        order_date
                    )
                    send_to_printer(printer_ip, receipt_text)

                    # Διαγραφή της εγγραφής μετά την επιτυχή εκτύπωση
                    conn.execute('DELETE FROM pending_receipts WHERE id = ?', (receipt['id'],))
                    logging.info(f"Successfully printed and deleted receipt {receipt['id']} for printer {printer_ip}")
                else:
                    logging.warning(f"Printer {printer_ip} still unavailable. Receipt {receipt['id']} not printed.")

            conn.commit()
        except Exception as e:
            logging.error(f"Error while retrying pending receipts: {e}")
        finally:
            conn.close()

    # Προγραμματισμός της λειτουργίας να εκτελείται περιοδικά
    scheduler.add_job(func=retry_pending_receipts, trigger="interval", minutes=1)

    # Μορφοποίηση απόδειξης για εκτύπωση
    def format_receipt_for_print(order_items, table_number, receipt_number, payment_method, order_date):
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()

        # Ανάκτηση στοιχείων της εταιρείας από τη βάση δεδομένων
        cursor.execute('SELECT * FROM company_info LIMIT 1')
        company_info = cursor.fetchone()

        # Ανάκτηση του εκτυπωτή για τις αποδείξεις
        cursor.execute('SELECT value FROM settings WHERE name = "invoice_printer"')
        invoice_printer = cursor.fetchone()

        conn.close()

        if not company_info:
            # Προκαθορισμένα στοιχεία αν δεν υπάρχουν δεδομένα στην εταιρεία
            company_info = {
                "company_name": "ΕΠΩΝΥΜΙΑ ΕΠΙΧΕΙΡΗΣΗΣ",
                "company_address": "Διεύθυνση",
                "company_tax_id": "ΑΦΜ",
                "company_tax_office": "Δ.Ο.Υ.",
                "company_phone": "Τηλέφωνο"
            }
        else:
            company_info = {
                "company_name": company_info[1],
                "company_address": company_info[2],
                "company_tax_id": company_info[3],
                "company_tax_office": company_info[4],
                "company_phone": company_info[5]
            }

        if not invoice_printer:
            raise ValueError("Δεν έχει οριστεί εκτυπωτής για τις αποδείξεις. Παρακαλώ ενημερώστε τις ρυθμίσεις.")

        # Μετατροπή του order_date σε αντικείμενο datetime αν είναι συμβολοσειρά
        if isinstance(order_date, str):
            order_date = datetime.strptime(order_date, '%Y-%m-%d %H:%M:%S')  # Προσαρμόστε τη μορφή αν είναι διαφορετική

        receipt_lines = []
        line_width = 40
        separator = "-" * line_width

        # Μήνυμα για μη νόμιμη απόδειξη
        receipt_lines.append("ΑΥΤΟ ΔΕΝ ΕΙΝΑΙ ΑΠΟΔΕΙΞΗ ΛΙΑΝΙΚΗΣ ΠΩΛΗΣΗΣ".center(line_width))
        receipt_lines.append("ΜΟΝΟ ΓΙΑ ΕΣΩΤΕΡΙΚΗ ΧΡΗΣΗ".center(line_width))
        
        # Επικεφαλίδα απόδειξης
        receipt_lines.append(separator)
        receipt_lines.append(company_info['company_name'].center(line_width))
        receipt_lines.append(company_info['company_address'].center(line_width))
        receipt_lines.append(f"ΑΦΜ: {company_info['company_tax_id']}".center(line_width))
        receipt_lines.append(f"Δ.Ο.Υ.: {company_info['company_tax_office']}".center(line_width))
        receipt_lines.append(f"Τηλ: {company_info['company_phone']}".center(line_width))
        receipt_lines.append(separator)

        # Πληροφορίες απόδειξης
        receipt_lines.append(f"Ημερομηνία: {order_date.strftime('%d/%m/%Y %H:%M')}")
        receipt_lines.append(f"Απόδειξη Νο: {receipt_number}")
        receipt_lines.append(separator)

        # Λεπτομέρειες προϊόντων
        total_net = 0
        total_vat = 0

        for idx, item in enumerate(order_items, start=1):
            qty = item['quantity']
            price = item['price']
            vat_rate = item['vat_rate'] / 100
            net = price / (1 + vat_rate)
            vat = price - net

            # Μορφοποίηση προϊόντων
            item_name = f"{qty} {item['name']}".ljust(22)
            item_price = f"{price * qty:.2f}€".rjust(10)
            item_vat = f"{item['vat_rate']}%".rjust(8)

            receipt_lines.append(f"{item_name} {item_price} {item_vat}")

            total_net += net * qty
            total_vat += vat * qty

        total = total_net + total_vat
        receipt_lines.append(separator)
        receipt_lines.append(f"Καθαρή Αξία: {total_net:.2f}€".rjust(line_width))
        receipt_lines.append(f"Φ.Π.Α.: {total_vat:.2f}€".rjust(line_width))
        receipt_lines.append(separator)
        receipt_lines.append(f"Συνολική Αξία: {total:.2f}€".rjust(line_width))
        receipt_lines.append(separator)

        # Ευχαριστήριο μήνυμα
        receipt_lines.append("Ευχαριστούμε για την προτίμησή σας!".center(line_width))
        receipt_lines.append(separator)

        # Μήνυμα για μη νόμιμη απόδειξη
        
        receipt_lines.append("ΤΟ ΠΑΡΟΝ ΕΙΝΑΙ ΠΛΗΡΟΦΟΡΙΑΚΟ ΣΤΟΙΧΕΙΟ".center(line_width))
        receipt_lines.append("ΚΑΙ ΔΕΝ ΑΠΟΤΕΛΕΙ ΝΟΜΙΜΗ".center(line_width))
        receipt_lines.append("ΦΟΡΟΛΟΓΙΚΗ ΑΠΟΔΕΙΞΗ/ΤΙΜΟΛΟΓΙΟ".center(line_width))
        receipt_lines.append(separator)

        receipt_text = "\n".join(receipt_lines)

        return receipt_text, invoice_printer[0]
    
    @app.before_request
    def check_session_timeout():
        if 'user_id' in session:
            last_activity = session.get('last_activity')
            if last_activity:
                # Ανάκτηση του session_timeout από τη βάση δεδομένων
                conn = get_db_connection()
                session_timeout = conn.execute('SELECT value FROM settings WHERE name = "session_timeout"').fetchone()
                conn.close()
                
                timeout_minutes = int(session_timeout['value']) if session_timeout else 10  # Προεπιλογή 10 λεπτά
                timeout_seconds = timeout_minutes * 60  # Μετατροπή σε δευτερόλεπτα

                # Έλεγχος αν έχει περάσει ο χρόνος αδράνειας
                if (time.time() - last_activity) > timeout_seconds:
                    session.clear()
                    return redirect(url_for('login'))
            # Ενημέρωση της τελευταίας δραστηριότητας
            session['last_activity'] = time.time()

    @app.route('/manifest.json')
    def manifest():
        return send_from_directory('static', 'manifest.json')

    @app.route('/service-worker.js')
    def service_worker():
        return send_from_directory('static', 'service-worker.js')

    @app.route('/offline.html')
    def offline():
        return render_template('offline.html')

    # Διαδρομή για την αποστολή ενός αρχείου Excel
    @app.route('/upload_excel', methods=['POST'])
    def upload_excel():
        if 'excelFile' not in request.files:
            flash('No file part', 'danger')
            return redirect(request.url)

        file = request.files['excelFile']
        if file.filename == '':
            flash('No selected file', 'danger')
            return redirect(request.url)

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)

            # Επεξεργασία του Excel αρχείου
            process_excel_file(file_path)

            flash('Το αρχείο Excel ανέβηκε και επεξεργάστηκε επιτυχώς.', 'success')
            return redirect(url_for('settings', tab='product-management'))
        else:
            flash('Μη έγκυρος τύπος αρχείου. Επιτρέπονται μόνο αρχεία Excel.', 'danger')
            return redirect(url_for('settings', tab='product-management'))

    # Διαδρομή για την είσοδο (login) χρηστών
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            pin = request.form['pin']
            conn = get_db_connection()
            user = conn.execute('SELECT * FROM users WHERE pin = ?', (pin,)).fetchone()
            conn.close()
            if user:
                session['user_id'] = user['id']
                session['user_role'] = user['role']
                session['last_activity'] = time.time()  # Αρχικοποίηση της τελευταίας δραστηριότητας
                # Σήμανση για εμφάνιση του προειδοποιητικού μηνύματος
                session['show_warning'] = True
                return redirect(url_for('index'))
            else:
                flash('Λάθος PIN', 'danger')
        return render_template('login.html')

    @app.route('/dismiss_warning', methods=['POST'])
    def dismiss_warning():
        session['show_warning'] = False
        return jsonify({'success': True})
    
    # Διαδρομή για την αποσύνδεση (logout) χρηστών
    @app.route('/logout')
    def logout():
        session.clear()
        #flash('Αποσυνδεθήκατε επιτυχώς', 'success')
        return redirect(url_for('login'))

    # Αρχική σελίδα της εφαρμογής
    @app.route('/')
    def index():
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return render_template('index.html')

    # Διαδρομή για την ανάκτηση πληροφοριών χρήστη βάσει ID
    @app.route('/get_user/<int:user_id>', methods=['GET'])
    def get_user(user_id):
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        conn.close()

        if user:
            user_data = {
                'id': user['id'],
                'first_name': user['first_name'],
                'last_name': user['last_name'],
                'pin': user['pin'],
                'role': user['role']
            }
            return jsonify(user=user_data)
        else:
            return jsonify(error="User not found"), 404

    # Διαδρομή για την ανάκτηση όλων των χρηστών
    @app.route('/get_users', methods=['GET'])
    def get_users():
        conn = get_db_connection()
        users = conn.execute('SELECT * FROM users').fetchall()
        conn.close()
        
        user_list = [dict(user) for user in users]
        
        return jsonify(users=user_list)

    # Διαδρομή για την προσθήκη νέου χρήστη
    @app.route('/add_user', methods=['POST'])
    def add_user():
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        pin = request.form['pin']
        role = request.form['role']

        # Έλεγχος αν το pin περιέχει μόνο αριθμούς και έχει ακριβώς 4 ψηφία
        if not (pin.isdigit() and len(pin) == 4):
            flash('Το PIN πρέπει να περιέχει ακριβώς 4 αριθμούς.', 'danger')
            return redirect(url_for('settings', tab='user-management'))

        conn = get_db_connection()

        # Έλεγχος αν το PIN υπάρχει ήδη
        existing_user = conn.execute('SELECT id FROM users WHERE pin = ?', (pin,)).fetchone()
        if existing_user:
            flash('Το PIN αυτό χρησιμοποιείται ήδη από άλλο χρήστη. Παρακαλώ επιλέξτε ένα διαφορετικό PIN.', 'danger')
            conn.close()
            return redirect(url_for('settings', tab='user-management'))

        # Εισαγωγή νέου χρήστη στη βάση δεδομένων
        try:
            conn.execute('INSERT INTO users (first_name, last_name, pin, role) VALUES (?, ?, ?, ?)', 
                        (first_name, last_name, pin, role))
            conn.commit()
            flash('Ο χρήστης προστέθηκε επιτυχώς.', 'success')
        except sqlite3.IntegrityError as e:
            flash('Σφάλμα κατά την προσθήκη του χρήστη. Προσπαθήστε ξανά.', 'danger')
        finally:
            conn.close()

        return redirect(url_for('settings', tab='user-management'))

    # Διαδρομή για την επεξεργασία υπάρχοντος χρήστη
    @app.route('/edit_user/<int:user_id>', methods=['POST'])
    def edit_user(user_id):
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        pin = request.form['pin']
        role = request.form['role']
        
        # Έλεγχος αν το pin περιέχει μόνο αριθμούς και έχει ακριβώς 4 ψηφία
        if not (pin.isdigit() and len(pin) == 4):
            flash('Το PIN πρέπει να περιέχει ακριβώς 4 αριθμούς.', 'danger')
            return redirect(url_for('settings', tab='user-management'))

        conn = get_db_connection()

        # Έλεγχος αν το νέο PIN υπάρχει ήδη για κάποιον άλλο χρήστη
        existing_user = conn.execute('SELECT id FROM users WHERE pin = ? AND id != ?', (pin, user_id)).fetchone()

        if existing_user:
            conn.close()
            flash('Το PIN που εισάγατε χρησιμοποιείται ήδη από άλλο χρήστη. Παρακαλώ επιλέξτε ένα άλλο PIN.', 'danger')
            return redirect(url_for('settings', tab='user-management'))
        
        # Ενημέρωση του χρήστη στη βάση δεδομένων
        conn.execute('UPDATE users SET first_name = ?, last_name = ?, pin = ?, role = ? WHERE id = ?', 
                    (first_name, last_name, pin, role, user_id))
        conn.commit()
        conn.close()
        
        flash('Ο χρήστης ενημερώθηκε επιτυχώς.', 'success')
        return redirect(url_for('settings', tab='user-management'))

    # Διαδρομή για τη διαγραφή χρήστη
    @app.route('/delete_user/<int:user_id>', methods=['POST'])
    def delete_user(user_id):
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()

        # Ελέγχουμε αν ο χρήστης είναι ο κεντρικός διαχειριστής
        if user and user['role'] == 'admin' and user_id == 1:
            flash('Δεν μπορείτε να διαγράψετε τον κεντρικό διαχειριστή.', 'danger')
            return redirect(url_for('settings', tab='user-management'))

        if user and user['role'] == 'admin':
            flash('Ο διαχειριστής διαγράφηκε επιτυχώς.', 'success')
        else:
            flash('Ο χρήστης διαγράφηκε επιτυχώς.', 'success')

        conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
        conn.close()

        return redirect(url_for('settings', tab='user-management'))

    # Διαδρομή για την εμφάνιση της κατάστασης όλων των τραπεζιών
    @app.route('/tables')
    def tables():
        conn = get_db_connection()
        
        # Λήψη της σημερινής ημερομηνίας σε μορφή 'YYYY-MM-DD'
        today_date = datetime.now().strftime('%Y-%m-%d')
        
        # Ανάκτηση όλων των τραπεζιών από τη βάση δεδομένων
        all_tables = conn.execute('SELECT * FROM tables').fetchall()
        
        # Ανάκτηση των τραπεζιών που έχουν κρατήσεις για τη σημερινή ημερομηνία
        reserved_tables_today = conn.execute('''
            SELECT table_id 
            FROM reservations 
            WHERE date = ?
        ''', (today_date,)).fetchall()
        
        # Δημιουργία λίστας με τα IDs των τραπεζιών που είναι κρατημένα σήμερα
        reserved_table_ids = [table['table_id'] for table in reserved_tables_today]
        
        conn.close()
        
        # Επιστροφή της HTML σελίδας με τα τραπέζια και τα κρατημένα τραπέζια
        return render_template('tables.html', tables=all_tables, reserved_table_ids=reserved_table_ids)

    # Διαδρομή για την προσθήκη νέου τραπεζιού
    @app.route('/add_table', methods=['POST'])
    def add_table():
        table_number = request.form['table_number']
        capacity = request.form['capacity']
        space = request.form['space']  # Νέα προσθήκη

        conn = get_db_connection()
        conn.execute('INSERT INTO tables (table_number, capacity, space) VALUES (?, ?, ?)', (table_number, capacity, space))
        conn.commit()
        conn.close()

        flash('Το τραπέζι προστέθηκε επιτυχώς.')
        return redirect(url_for('tables'))

    # Διαδρομή για τη διαχείριση συγκεκριμένου τραπεζιού (εμφάνιση παραγγελιών και διαθέσιμων προϊόντων)
    @app.route('/manage_table/<int:table_id>', methods=['GET', 'POST'])
    def manage_table(table_id):
        conn = get_db_connection()
        
        # Ανάκτηση στοιχείων τραπεζιού
        table = conn.execute('SELECT * FROM tables WHERE id = ?', (table_id,)).fetchone()

        # Ανάκτηση όλων των παραγγελιών για το συγκεκριμένο τραπέζι που είναι σε εξέλιξη
        orders = conn.execute('''
            SELECT order_items.id, products.name AS product_name, order_items.quantity, products.price, 
                (order_items.quantity * products.price) AS total, order_items.comments
            FROM order_items
            JOIN products ON order_items.product_id = products.id
            JOIN orders ON order_items.order_id = orders.id
            WHERE orders.table_id = ? AND orders.status = 'pending'
        ''', (table_id,)).fetchall()

        # Υπολογισμός του συνολικού ποσού όλων των παραγγελιών του τραπεζιού
        total_amount = sum(order['total'] for order in orders)

        # Ανάκτηση μόνο ενεργών κατηγοριών με τα αντίστοιχα ενεργά προϊόντα τους
        categories = conn.execute('SELECT * FROM categories WHERE is_active = 1').fetchall()
        categories_with_products = []
        for category in categories:
            category_dict = dict(category)
            category_dict['products'] = conn.execute(
                'SELECT * FROM products WHERE category_id = ? AND is_active = 1', 
                (category['id'],)
            ).fetchall()
            categories_with_products.append(category_dict)

        # Ανάκτηση όλων των τραπεζιών για τη μεταφορά παραγγελιών
        all_tables = conn.execute('SELECT * FROM tables').fetchall()

        conn.close()
        
        return render_template(
            'manage_table.html', 
            table=table, 
            orders=orders, 
            total_amount=total_amount, 
            categories=categories_with_products, 
            all_tables=all_tables
        )

    @app.route('/delete_order_item/<int:item_id>', methods=['POST'])
    def delete_order_item(item_id):
        if 'user_id' not in session:
            flash('Πρέπει να συνδεθείτε για να διαγράψετε αντικείμενο.', 'danger')
            return redirect(url_for('login'))

        conn = get_db_connection()
        audit_conn = get_audit_db_connection()

        # Ανάκτηση πληροφοριών για το αντικείμενο παραγγελίας
        order_item = conn.execute('''
            SELECT oi.order_id, oi.product_id, p.name AS product_name 
            FROM order_items oi 
            JOIN products p ON oi.product_id = p.id 
            WHERE oi.id = ?
        ''', (item_id,)).fetchone()

        if order_item is None:
            conn.close()
            audit_conn.close()
            return jsonify({'success': False, 'message': 'Το προϊόν δεν βρέθηκε.'})

        order_id = order_item['order_id']
        product_name = order_item['product_name']

        # Εύρεση του table_number
        order = conn.execute('SELECT table_id FROM orders WHERE id = ?', (order_id,)).fetchone()
        table_id = order['table_id']
        table = conn.execute('SELECT table_number FROM tables WHERE id = ?', (table_id,)).fetchone()
        table_number = table['table_number']

        # Χρήστης που έκανε τη διαγραφή (από τη συνεδρία)
        user_id = session['user_id']
        user = conn.execute('SELECT first_name, last_name FROM users WHERE id = ?', (user_id,)).fetchone()
        user_name = f"{user['first_name']} {user['last_name']}"

        # Καταγραφή στο audit log
        deletion_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        audit_conn.execute('''
            INSERT INTO deletion_logs (order_item_id, product_name, table_number, user_id, user_name, deletion_time)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (item_id, product_name, table_number, user_id, user_name, deletion_time))
        audit_conn.commit()

        # Διαγραφή του προϊόντος
        conn.execute('DELETE FROM order_items WHERE id = ?', (item_id,))
        remaining_items = conn.execute('SELECT COUNT(*) FROM order_items WHERE order_id = ?', (order_id,)).fetchone()[0]

        if remaining_items == 0:
            conn.execute('DELETE FROM orders WHERE id = ?', (order_id,))
            conn.execute('UPDATE tables SET status = ? WHERE id = ?', ('free', table_id))

        conn.commit()
        conn.close()
        audit_conn.close()

        return redirect(url_for('manage_table', table_id=table_id))
    
    @app.route('/change_table_status/<int:table_id>', methods=['POST'])
    def change_table_status(table_id):
        status = request.form['status']
        
        # Ενημέρωση της κατάστασης του τραπεζιού στη βάση δεδομένων
        conn = get_db_connection()
        conn.execute('UPDATE tables SET status = ? WHERE id = ?', (status, table_id))
        conn.commit()
        conn.close()
        
        # Προσθήκη ενός flash μηνύματος επιτυχίας
        flash('Η κατάσταση του τραπεζιού ενημερώθηκε με επιτυχία.', 'success')

        # Επιστροφή ενός JSON μηνύματος επιτυχίας
        return jsonify({'success': True})

    # Διαδρομή για τη δημιουργία hash που αντιπροσωπεύει την τρέχουσα κατάσταση των τραπεζιών
    @app.route('/table_status_hash', methods=['GET'])
    def table_status_hash():
        conn = get_db_connection()
        
        # Ανάκτηση των ID και κατάστασης όλων των τραπεζιών
        tables = conn.execute('SELECT id, status FROM tables').fetchall()
        conn.close()

        # Δημιουργία ενός string που αντιπροσωπεύει την κατάσταση όλων των τραπεζιών και το hashing αυτού του string
        status_string = ''.join([f'{table["id"]}-{table["status"]}' for table in tables])
        status_hash = hashlib.md5(status_string.encode()).hexdigest()
        
        # Επιστροφή του hash ως JSON
        return jsonify({'hash': status_hash})

    @app.route('/close_table/<int:table_id>', methods=['POST'])
    def close_table(table_id):
        payment_method = request.form.get('payment_method')

        conn = get_db_connection()

        # Ανάκτηση παραγγελιών που σχετίζονται με το τραπέζι και είναι σε κατάσταση "pending"
        order = conn.execute('''
            SELECT o.id, o.order_date, oi.quantity, p.name, p.price, oi.comments, c.vat_rate
            FROM orders o
            JOIN order_items oi ON o.id = oi.order_id
            JOIN products p ON oi.product_id = p.id
            JOIN categories c ON p.category_id = c.id
            WHERE o.table_id = ? AND o.status = ?
        ''', (table_id, 'pending')).fetchall()

        if order:
            order_id = order[0]['id']  # Χρησιμοποιούμε το order ID ως αριθμό απόδειξης
            order_date = order[0]['order_date']  # Ημερομηνία παραγγελίας

            # Έλεγχος αν η επιλογή εκτύπωσης απόδειξης κατά το κλείσιμο τραπεζιού είναι ενεργή
            print_receipt_on_close = conn.execute('SELECT value FROM settings WHERE name = "print_receipt_on_close"').fetchone()
            if print_receipt_on_close and print_receipt_on_close['value'] == 'yes':
                # Δημιουργία απόδειξης με χρήση της ημερομηνίας παραγγελίας
                receipt_text, invoice_printer_id = format_receipt_for_print(order, table_id, order_id, payment_method, order_date)

                # Δημιουργία νήματος για την εκτύπωση ή αποθήκευση για αργότερα
                threading.Thread(target=handle_receipt_printing, args=(invoice_printer_id, receipt_text, order, table_id, order_id, payment_method)).start()

        # Ενημέρωση της κατάστασης των παραγγελιών και του τραπεζιού στη βάση δεδομένων
        conn.execute('UPDATE orders SET status = ?, table_id = NULL WHERE table_id = ? AND status = ?', ('paid', table_id, 'pending'))
        conn.execute('UPDATE tables SET status = ? WHERE id = ?', ('free', table_id))

        conn.commit()
        conn.close()

        # Εμφάνιση μηνύματος επιτυχίας και ανακατεύθυνση στη σελίδα με τα τραπέζια
        flash('Το τραπέζι έκλεισε και οι παραγγελίες μεταφέρθηκαν στο αρχείο πληρωμένων παραγγελιών.', 'success')
        return redirect(url_for('tables'))
        
    # Διαδρομή για την επεξεργασία των στοιχείων ενός τραπεζιού
    @app.route('/edit_table/<int:table_id>', methods=['GET', 'POST'])
    def edit_table(table_id):
        conn = get_db_connection()
        
        # Ανάκτηση στοιχείων τραπεζιού από τη βάση δεδομένων
        table = conn.execute('SELECT * FROM tables WHERE id = ?', (table_id,)).fetchone()

        if request.method == 'POST':
            table_number = request.form['table_number']
            capacity = request.form['capacity']
            space = request.form['space']  # Προσθήκη του πεδίου "Χώρος"
            
            # Ενημέρωση των στοιχείων του τραπεζιού στη βάση δεδομένων
            conn.execute('UPDATE tables SET table_number = ?, capacity = ?, space = ? WHERE id = ?',
                        (table_number, capacity, space, table_id))
            conn.commit()
            conn.close()
            
            # Εμφάνιση μηνύματος επιτυχίας και ανακατεύθυνση στη σελίδα διαχείρισης του τραπεζιού
            flash('Το τραπέζι ενημερώθηκε επιτυχώς.', 'success')
            return redirect(url_for('manage_table', table_id=table_id))

        conn.close()
        return render_template('edit_table.html', table=table)

    # Διαδρομή για τη διαγραφή τραπεζιού
    @app.route('/delete_table/<int:table_id>', methods=['POST'])
    def delete_table(table_id):
        conn = get_db_connection()
        
        # Διαγραφή του τραπεζιού από τη βάση δεδομένων
        conn.execute('DELETE FROM tables WHERE id = ?', (table_id,))
        conn.commit()
        conn.close()
        
        # Εμφάνιση μηνύματος επιτυχίας και ανακατεύθυνση στη σελίδα με τα τραπέζια
        flash('Το τραπέζι διαγράφηκε επιτυχώς.', 'success')
        return redirect(url_for('tables'))

    # Διαδρομή για την εμφάνιση των παραγγελιών με δυνατότητα φιλτραρίσματος
    @app.route('/orders', methods=['GET'])
    def orders():
        user_role = session.get('user_role')
        user_id = session.get('user_id')

        status = request.args.get('status', '')
        table_id = request.args.get('table_id', '')
        selected_user_id = request.args.get('user_id', user_id if user_role != 'admin' else '')
        date_from = request.args.get('date_from', datetime.now().strftime('%Y-%m-%d'))
        date_to = request.args.get('date_to', datetime.now().strftime('%Y-%m-%d'))

        # Βασικά queries
        base_query = '''
            FROM orders o
            LEFT JOIN order_items oi ON o.id = oi.order_id
            LEFT JOIN products p ON oi.product_id = p.id
            LEFT JOIN users u ON o.user_id = u.id
            WHERE 1=1
        '''
        filter_query = ''
        params = []

        # Προσθήκη φίλτρων
        if status:
            filter_query += ' AND o.status = ?'
            params.append(status)
        if table_id:
            filter_query += ' AND o.table_name = ?'
            params.append(table_id)
        if date_from:
            filter_query += ' AND date(o.order_date) >= ?'
            params.append(date_from)
        if date_to:
            filter_query += ' AND date(o.order_date) <= ?'
            params.append(date_to)

        # Περιορισμός για χρήστες που δεν είναι admin
        if user_role != 'admin':
            filter_query += ' AND o.user_id = ?'
            params.append(user_id)
        elif selected_user_id:
            filter_query += ' AND o.user_id = ?'
            params.append(selected_user_id)

        # Συνολικό query για τις παραγγελίες
        order_query = f'''
            SELECT o.id AS order_id, o.table_name, o.order_date, o.status,
                GROUP_CONCAT(p.name || " (" || oi.quantity || "x" || oi.price || "€)", ", ") AS items,
                SUM(oi.price * oi.quantity) AS total,
                u.first_name || " " || u.last_name AS user_name
            {base_query} {filter_query}
            GROUP BY o.id ORDER BY o.order_date DESC
        '''

        # Query για το συνολικό ποσό
        total_query = f'''
            SELECT SUM(oi.price * oi.quantity) AS total_revenue
            {base_query} {filter_query}
        '''

        conn = get_db_connection()
        try:
            orders = conn.execute(order_query, params).fetchall()
            users = conn.execute('SELECT id, first_name, last_name FROM users').fetchall()
            total_revenue = conn.execute(total_query, params).fetchone()[0] or 0
        finally:
            conn.close()

        return render_template('orders.html', orders=orders, users=users, selected_status=status, 
                            selected_table_id=table_id, selected_user_id=selected_user_id, date_from=date_from, 
                            date_to=date_to, total_revenue=total_revenue)

    # Διαδρομή για την προσθήκη νέας παραγγελίας σε τραπέζι
    @app.route('/add_order/<int:table_id>', methods=['POST'])
    def add_order(table_id):
        # Ανάκτηση δεδομένων προϊόντων από τη φόρμα
        products = request.form.getlist('products[]')
        complete_order = request.form.get('complete_order') == 'true'
        user_id = session.get('user_id')  # Ανάκτηση του ID του συνδεδεμένου χρήστη

        conn = get_db_connection()

        # Εύρεση του τραπεζιού από τη βάση δεδομένων
        table = conn.execute('SELECT table_number FROM tables WHERE id = ?', (table_id,)).fetchone()
        if table is None:
            return jsonify({'success': False, 'message': 'Το τραπέζι δεν βρέθηκε.'})

        table_name = table['table_number']

        # Εύρεση υπάρχουσας παραγγελίας για το τραπέζι σε κατάσταση 'pending'
        order = conn.execute('SELECT id FROM orders WHERE table_id = ? AND status = ?', (table_id, 'pending')).fetchone()
        if order is None:
            # Αν δεν υπάρχει παραγγελία, δημιουργούμε μία νέα
            conn.execute('INSERT INTO orders (table_id, table_name, order_date, user_id) VALUES (?, ?, ?, ?)', 
                        (table_id, table_name, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_id))
            order_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
        else:
            order_id = order['id']

        # Προσθήκη των προϊόντων στην παραγγελία ως ξεχωριστές εγγραφές
        for product_data in products:
            product_id, quantity, comments, subcategories = product_data.split('|')
            product_id = int(product_id)
            quantity = int(quantity)
            comments = comments if comments else None
            subcategory_names = ', '.join(subcategories.split(',')) if subcategories else None

            product = conn.execute('SELECT price FROM products WHERE id = ?', (product_id,)).fetchone()
            if product is None:
                return jsonify({'success': False, 'message': f'Το προϊόν με ID {product_id} δεν βρέθηκε.'})

            price = product['price']

            # Εισαγωγή κάθε μονάδας ως ξεχωριστή εγγραφή
            for _ in range(quantity):
                conn.execute('INSERT INTO order_items (order_id, product_id, price, quantity, comments, subcategory_id) VALUES (?, ?, ?, ?, ?, ?)', 
                            (order_id, product_id, price, 1, comments, subcategory_names))

        # Ενημέρωση της κατάστασης του τραπεζιού σε 'occupied' εάν δεν είναι ήδη
        conn.execute('UPDATE tables SET status = ? WHERE id = ? AND status != ?', ('occupied', table_id, 'occupied'))

        # Ανάκτηση όλων των μη εκτυπωμένων αντικειμένων για ενημέρωση του printed
        order_item_ids = conn.execute('SELECT id FROM order_items WHERE order_id = ? AND printed = 0', (order_id,)).fetchall()
        order_item_ids = [item['id'] for item in order_item_ids]

        # Εκτύπωση του χαρτακιού παραγγελίας με ομαδοποίηση ποσοτήτων
        order_items_for_printing = conn.execute('''
            SELECT 
                p.name, 
                COUNT(*) as quantity, 
                oi.comments, 
                p.category_id, 
                c.name as category_name, 
                oi.subcategory_id as subcategory_names
            FROM order_items oi
            JOIN products p ON oi.product_id = p.id
            JOIN categories c ON p.category_id = c.id
            WHERE oi.order_id = ? AND oi.printed = 0
            GROUP BY p.id, oi.comments, oi.subcategory_id, p.category_id, c.name
        ''', (order_id,)).fetchall()

        if order_items_for_printing:
            # Εκτελεί την αποστολή των παραγγελιών στους εκτυπωτές σε ξεχωριστό νήμα
            threading.Thread(target=handle_order_printing, args=(order_items_for_printing, table_name, order_item_ids)).start()

        conn.commit()
        conn.close()

        # Επιστροφή επιτυχίας και ID της παραγγελίας ως JSON
        return jsonify({'success': True, 'order_id': order_id})

    @app.route('/get_subcategories/<int:product_id>', methods=['GET'])
    def get_subcategories(product_id):
        conn = get_db_connection()
        
        # Πρώτα πρέπει να βρούμε το category_id του product που δόθηκε
        category = conn.execute('SELECT category_id FROM products WHERE id = ?', (product_id,)).fetchone()
        if category is None:
            return jsonify({'subcategories': []})
        
        # Τώρα βρίσκουμε όλες τις υποκατηγορίες που ανήκουν σε αυτή την κατηγορία
        subcategories = conn.execute('SELECT id, name FROM subcategories WHERE category_id = ?', (category['category_id'],)).fetchall()
        
        conn.close()
        
        return jsonify({'subcategories': [{'id': sub['id'], 'name': sub['name']} for sub in subcategories]})

    def handle_order_printing(order_items, table_name, order_item_ids):
        conn = get_db_connection()

        printer_orders = {}

        for item in order_items:
            category_id = item['category_id']
            # Εύρεση εκτυπωτών που συνδέονται με την κατηγορία προϊόντος
            printers = conn.execute('''
                SELECT p.id, p.ip_address 
                FROM printers p
                JOIN printer_categories pc ON p.id = pc.printer_id
                WHERE pc.category_id = ?
            ''', (category_id,)).fetchall()

            for printer in printers:
                printer_id = printer['id']
                if printer_id not in printer_orders:
                    printer_orders[printer_id] = {
                        'ip_address': printer['ip_address'],
                        'items': []
                    }
                # Προσθήκη του προϊόντος στη λίστα για τον αντίστοιχο εκτυπωτή
                printer_orders[printer_id]['items'].append(dict(item))

        for printer_id, printer_data in printer_orders.items():
            if is_printer_available(printer_data['ip_address']):
                order_text = format_order_for_print(printer_data['items'], table_name)
                send_to_printer(printer_data['ip_address'], order_text)
            else:
                save_order_for_later(printer_id, printer_data['items'], table_name)

        # Σημείωση ότι τα αντικείμενα έχουν εκτυπωθεί
        if order_item_ids:
            conn.execute('''
                UPDATE order_items
                SET printed = 1
                WHERE id IN ({})
            '''.format(','.join('?' * len(order_item_ids))), order_item_ids)

        conn.commit()
        conn.close()

    @app.route('/export_orders', methods=['GET'])
    def export_orders():
        status = request.args.get('status', '')
        table_id = request.args.get('table_id', '')
        user_id = request.args.get('user_id', '')
        date_from = request.args.get('date_from', datetime.now().strftime('%Y-%m-%d'))
        date_to = request.args.get('date_to', datetime.now().strftime('%Y-%m-%d'))

        query = '''
            SELECT o.id AS order_id, o.table_name, o.order_date, o.status,
                GROUP_CONCAT(p.name || " (" || oi.quantity || "x" || oi.price || "€)", ", ") AS items,
                SUM(oi.price * oi.quantity) AS total,
                u.first_name || " " || u.last_name AS user_name
            FROM orders o
            LEFT JOIN order_items oi ON o.id = oi.order_id
            LEFT JOIN products p ON oi.product_id = p.id
            LEFT JOIN users u ON o.user_id = u.id
            WHERE 1=1
        '''

        params = []

        if status:
            query += ' AND o.status = ?'
            params.append(status)
        if table_id:
            query += ' AND o.table_name = ?'
            params.append(table_id)
        if user_id:
            query += ' AND o.user_id = ?'
            params.append(user_id)
        if date_from:
            query += ' AND date(o.order_date) >= ?'
            params.append(date_from)
        if date_to:
            query += ' AND date(o.order_date) <= ?'
            params.append(date_to)

        query += ' GROUP BY o.id ORDER BY o.order_date DESC'

        conn = get_db_connection()
        try:
            orders = conn.execute(query, params).fetchall()
        finally:
            conn.close()

        # Μετατροπή των αποτελεσμάτων σε DataFrame pandas
        df = pd.DataFrame(orders, columns=["order_id", "table_name", "order_date", "status", "items", "total", "user_name"])

        # Προσθήκη τίτλων στηλών
        df.columns = ["Αριθμός Παραγγελίας", "Αριθμός Τραπεζιού", "Ημερομηνία Παραγγελίας", "Κατάσταση", "Προϊόντα", "Σύνολο", "Χρήστης"]

        # Δημιουργία του αρχείου Excel στη μνήμη με μορφοποίηση
        output = io.BytesIO()
        writer = pd.ExcelWriter(output, engine='xlsxwriter')
        df.to_excel(writer, index=False, sheet_name='Orders')

        workbook = writer.book
        worksheet = writer.sheets['Orders']

        # Ρύθμιση πλάτους στηλών
        worksheet.set_column('A:A', 20)  # Αριθμός Παραγγελίας
        worksheet.set_column('B:B', 20)  # Αριθμός Τραπεζιού
        worksheet.set_column('C:C', 20)  # Ημερομηνία Παραγγελίας
        worksheet.set_column('D:D', 15)  # Κατάσταση
        worksheet.set_column('E:E', 40)  # Προϊόντα
        worksheet.set_column('F:F', 10)  # Σύνολο
        worksheet.set_column('G:G', 20)  # Χρήστης

        # Δημιουργία μορφοποίησης για την επικεφαλίδα
        header_format = workbook.add_format({
            'bold': True,
            'text_wrap': True,
            'valign': 'middle',
            'align': 'center',
            'bg_color': '#D7E4BC',
            'border': 1
        })

        # Εφαρμογή μορφοποίησης επικεφαλίδας
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_format)

        writer.close()
        output.seek(0)

        # Επιστροφή του αρχείου Excel για λήψη
        return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                        download_name='orders.xlsx', as_attachment=True)

    @app.route('/transfer_orders', methods=['POST'])
    def transfer_orders():
        source_table_id = request.form.get('source_table_id')
        target_table_id = request.form.get('target_table_id')

        if not source_table_id or not target_table_id:
            return "Missing table IDs", 400

        conn = get_db_connection()

        # Εύρεση υπάρχουσας παραγγελίας στο target_table
        target_order = conn.execute(
            'SELECT id FROM orders WHERE table_id = ? AND status = "pending"',
            (target_table_id,)
        ).fetchone()

        # Εύρεση όλων των παραγγελιών στο source_table
        source_orders = conn.execute(
            'SELECT id FROM orders WHERE table_id = ? AND status = "pending"',
            (source_table_id,)
        ).fetchall()

        if target_order:
            target_order_id = target_order['id']
            # Μεταφορά όλων των προϊόντων από τις παραγγελίες του source_table στο target_table
            for order in source_orders:
                conn.execute(
                    'UPDATE order_items SET order_id = ? WHERE order_id = ?',
                    (target_order_id, order['id'])
                )
                # Διαγραφή της κενής παραγγελίας από το source_table
                conn.execute('DELETE FROM orders WHERE id = ?', (order['id'],))
        else:
            # Αν δεν υπάρχει παραγγελία στο target_table, μεταφέρουμε τις παραγγελίες
            conn.execute(
                'UPDATE orders SET table_id = ? WHERE table_id = ?',
                (target_table_id, source_table_id)
            )

        # Ενημέρωση της κατάστασης των τραπεζιών
        conn.execute('UPDATE tables SET status = ? WHERE id = ?', ('occupied', target_table_id))
        
        # Ελέγχουμε αν το source_table έχει άλλες παραγγελίες, αν όχι, το ορίζουμε ως "free"
        if not conn.execute('SELECT 1 FROM orders WHERE table_id = ?', (source_table_id,)).fetchone():
            conn.execute('UPDATE tables SET status = ? WHERE id = ?', ('free', source_table_id))

        conn.commit()
        conn.close()

        flash('Οι παραγγελίες συγχωνεύθηκαν επιτυχώς.', 'success')
        return redirect(url_for('tables'))

        # Διαδρομή για την εμφάνιση των παραγγελιών που είναι σε εκκρεμότητα για πληρωμή
        
    @app.route('/bills')
    def bills():
        conn = get_db_connection()
        
        # Ανάκτηση όλων των παραγγελιών που είναι σε κατάσταση 'pending'
        pending_orders = conn.execute('''
            SELECT o.id AS order_id, t.table_number, o.order_date, o.status,
                GROUP_CONCAT(p.name || " (" || oi.quantity || "x" || oi.price || "€)", ", ") AS items
            FROM orders o
            LEFT JOIN tables t ON o.table_id = t.id
            JOIN order_items oi ON o.id = oi.order_id
            JOIN products p ON oi.product_id = p.id
            WHERE o.status = 'pending'
            GROUP BY o.id
            ORDER BY o.order_date DESC
        ''').fetchall()
        
        conn.close()
        
        # Επιστροφή της σελίδας με τις παραγγελίες σε εκκρεμότητα
        return render_template('bills.html', pending_orders=pending_orders)

    # Διαδρομή για τον διαχωρισμό και την πληρωμή λογαριασμών
    @app.route('/split_bill/<int:order_id>', methods=['GET', 'POST'])
    def split_bill(order_id):
        conn = get_db_connection()

        if request.method == 'POST':
            selected_items = request.form.getlist('selected_items')  # Λίστα με τα επιλεγμένα προϊόντα προς πληρωμή
            total_amount = 0
            error_detected = False  # Flag για ανίχνευση λάθους

            print(f"Selected items: {selected_items}")  # Debugging: Τι επέλεξε ο χρήστης

            for item_id in selected_items:
                print(f"Processing item_id: {item_id}")  # Debugging: Ποιο προϊόν επεξεργάζεσαι

                # Ανάκτηση του προϊόντος από τη βάση
                order_item = conn.execute('SELECT price, quantity, paid_quantity FROM order_items WHERE id = ?', (item_id,)).fetchone()

                if not order_item:
                    print(f"Product ID {item_id} not found in database.")  # Debugging: Το προϊόν δεν βρέθηκε
                    flash(f'Το προϊόν με ID {item_id} δεν βρέθηκε.', 'danger')
                    error_detected = True
                    continue

                price = order_item['price']
                remaining_quantity = order_item['quantity'] - order_item['paid_quantity']
                print(f"Remaining quantity for item {item_id}: {remaining_quantity}")  # Debugging: Πόσο απομένει

                if remaining_quantity <= 0:
                    flash(f'Το προϊόν με ID {item_id} είναι ήδη πληρωμένο.', 'danger')
                    error_detected = True
                    continue

                # Ενημέρωση του συνολικού ποσού
                total_amount += price  # Quantity είναι πάντα 1, οπότε δεν χρειάζεται πολλαπλασιασμός

                # Ενημέρωση του paid_quantity
                conn.execute('UPDATE order_items SET paid_quantity = paid_quantity + 1 WHERE id = ?', (item_id,))
                print(f"Updated paid_quantity for item {item_id} to 1")  # Debugging: Ενημέρωση πληρωμής

            # Αν ανιχνεύθηκε λάθος, σταματάμε τη διαδικασία
            if error_detected:
                conn.close()
                return redirect(request.url)

            # Έλεγχος αν όλα τα προϊόντα έχουν εξοφληθεί
            all_paid = conn.execute('''
                SELECT COUNT(*) 
                FROM order_items 
                WHERE order_id = ? AND quantity > paid_quantity
            ''', (order_id,)).fetchone()[0] == 0

            if all_paid:
                conn.execute('UPDATE orders SET status = ? WHERE id = ?', ('paid', order_id))
                print(f"Order {order_id} marked as paid")  # Debugging: Ενημέρωση παραγγελίας ως πληρωμένη

            # Δημιουργία εγγραφής στον πίνακα bills
            conn.execute('INSERT INTO bills (order_id, total_amount, status) VALUES (?, ?, ?)', 
                        (order_id, total_amount, 'unpaid'))

            conn.commit()
            flash('Η πληρωμή καταχωρήθηκε επιτυχώς.', 'success')

        # Ανάκτηση δεδομένων παραγγελίας
        order = conn.execute('SELECT * FROM orders WHERE id = ?', (order_id,)).fetchone()

        # Ανάκτηση μόνο των μη πληρωμένων αντικειμένων για εμφάνιση
        items = conn.execute('''
            SELECT 
                oi.id, 
                p.name, 
                oi.quantity AS total_quantity, 
                COALESCE(oi.paid_quantity, 0) AS paid_quantity, 
                oi.price, 
                oi.comments, 
                sc.name AS subcategory_name
            FROM order_items oi
            JOIN products p ON oi.product_id = p.id
            LEFT JOIN subcategories sc ON oi.subcategory_id = sc.id
            WHERE oi.order_id = ? AND oi.quantity > COALESCE(oi.paid_quantity, 0)
        ''', (order_id,)).fetchall()

        conn.close()

        # Επιστροφή στη φόρμα με τα δεδομένα
        return render_template('split_bill.html', order=order, items=items)
    
    # Διαδρομή για την προσθήκη νέας κατηγορίας προϊόντων
    @app.route('/add_category', methods=['POST'])
    def add_category():
        category_name = request.form['category_name']
        vat_rate = request.form['vat_rate']

        try:
            vat_rate = float(vat_rate)
        except ValueError:
            flash('Ο συντελεστής ΦΠΑ πρέπει να είναι αριθμός.', 'danger')
            return redirect(url_for('settings', tab='product-management'))

        conn = get_db_connection()

        # Έλεγχος αν η κατηγορία υπάρχει ήδη, είτε ενεργή είτε όχι
        category = conn.execute('SELECT id, is_active FROM categories WHERE name = ?', (category_name,)).fetchone()
        if category:
            if category['is_active'] == 0:
                # Επανενεργοποίηση της κατηγορίας
                conn.execute('UPDATE categories SET is_active = 1, vat_rate = ? WHERE id = ?', (vat_rate, category['id']))
                flash('Η κατηγορία επανενεργοποιήθηκε επιτυχώς.', 'success')
            else:
                flash('Η κατηγορία υπάρχει ήδη.', 'warning')
        else:
            # Προσθήκη νέας κατηγορίας
            conn.execute('INSERT INTO categories (name, vat_rate, is_active) VALUES (?, ?, 1)', (category_name, vat_rate))
            category_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]

            # Προσθήκη υποκατηγοριών αν υπάρχουν
            subcategories = request.form.getlist('subcategories[]')
            if subcategories:
                for subcategory_name in subcategories:
                    if subcategory_name:
                        conn.execute('INSERT INTO subcategories (name, category_id) VALUES (?, ?)', (subcategory_name, category_id))

        conn.commit()
        conn.close()

        flash('Η κατηγορία και οι υποκατηγορίες προστέθηκαν ή ενημερώθηκαν επιτυχώς.', 'success')
        return redirect(url_for('settings', tab='product-management'))

    @app.route('/add_subcategory', methods=['POST'])
    def add_subcategory():
        subcategory_name = request.form['subcategory_name']
        category_id = request.form['category_id']  # Ανακτούμε το ID της κατηγορίας από τη φόρμα

        if not subcategory_name:
            flash('Το όνομα της υποκατηγορίας δεν μπορεί να είναι κενό.', 'danger')
            return redirect(url_for('settings', tab='product-management'))

        conn = get_db_connection()
        # Εισαγωγή νέας υποκατηγορίας στη βάση δεδομένων
        conn.execute('INSERT INTO subcategories (name, category_id) VALUES (?, ?)', (subcategory_name, category_id))
        conn.commit()
        conn.close()

        flash('Η υποκατηγορία προστέθηκε επιτυχώς.', 'success')
        return redirect(url_for('settings', tab='product-management'))
            
    # Διαδρομή για την επεξεργασία υπάρχουσας κατηγορίας προϊόντων
    @app.route('/edit_category/<int:category_id>', methods=['POST'])
    def edit_category(category_id):
        category_name = request.form['category_name']
        vat_rate = request.form['vat_rate']
        
        # Νέες υποκατηγορίες που θα προστεθούν
        new_subcategories = request.form.getlist('new_subcategories[]')
        # Υπάρχουσες υποκατηγορίες που πρέπει να ενημερωθούν
        existing_subcategories = {key: value for key, value in request.form.items() if key.startswith('subcategories[') and key.endswith(']')}
        # Υποκατηγορίες που θα διαγραφούν
        remove_subcategories = request.form.getlist('remove_subcategories[]')
        
        conn = get_db_connection()

        # Ενημέρωση του ονόματος της κατηγορίας και του συντελεστή ΦΠΑ στη βάση δεδομένων
        conn.execute('UPDATE categories SET name = ?, vat_rate = ? WHERE id = ?', (category_name, vat_rate, category_id))

        # Διαγραφή επιλεγμένων υποκατηγοριών
        for subcategory_id in remove_subcategories:
            conn.execute('DELETE FROM subcategories WHERE id = ?', (subcategory_id,))

        # Ενημέρωση υπαρχουσών υποκατηγοριών
        for subcategory_id, subcategory_name in existing_subcategories.items():
            subcategory_id_clean = subcategory_id.replace('subcategories[', '').replace(']', '')
            if subcategory_name.strip():
                conn.execute('UPDATE subcategories SET name = ? WHERE id = ?', (subcategory_name.strip(), subcategory_id_clean))

        # Προσθήκη νέων υποκατηγοριών αν υπάρχουν
        if new_subcategories:
            for subcategory_name in new_subcategories:
                if subcategory_name.strip():  # Αν η υποκατηγορία δεν είναι κενή
                    conn.execute('INSERT INTO subcategories (name, category_id) VALUES (?, ?)', (subcategory_name.strip(), category_id))

        conn.commit()
        conn.close()
        
        flash('Η κατηγορία και οι υποκατηγορίες ενημερώθηκαν επιτυχώς.', 'success')
        return redirect(url_for('settings') + '?tab=product-management')

    # Διαδρομή για τη διαγραφή κατηγορίας προϊόντων
    @app.route('/delete_category/<int:category_id>', methods=['POST'])
    def delete_category(category_id):
        conn = get_db_connection()

        # Λογική διαγραφή της κατηγορίας
        conn.execute('UPDATE categories SET is_active = 0 WHERE id = ?', (category_id,))

        # Λογική διαγραφή όλων των προϊόντων της κατηγορίας
        conn.execute('UPDATE products SET is_active = 0 WHERE category_id = ?', (category_id,))

        conn.commit()
        conn.close()

        flash('Η κατηγορία και όλα τα προϊόντα της απενεργοποιήθηκαν επιτυχώς.', 'success')
        return redirect(url_for('settings') + '?tab=product-management')

    # Διαδρομή για την εμφάνιση των προϊόντων ταξινομημένα ανά κατηγορία
    @app.route('/products')
    def products():
        conn = get_db_connection()
        categories = conn.execute('SELECT * FROM categories WHERE is_active = 1').fetchall()
        products = conn.execute('SELECT * FROM products WHERE is_active = 1').fetchall()
        
        # Ομαδοποίηση των προϊόντων ανά κατηγορία
        categorized_products = {category['id']: [] for category in categories}
        
        for product in products:
            category_id = product['category_id']
            
            # Προσθήκη προϊόντος στην κατάλληλη κατηγορία
            if category_id in categorized_products:
                categorized_products[category_id].append(product)
            else:
                print(f"Warning: Category ID {category_id} not found in categories")

        categories_with_products = []
        for category in categories:
            category_dict = dict(category)
            category_dict['products'] = categorized_products[category['id']]
            categories_with_products.append(category_dict)
        
        conn.close()
        # Επιστροφή της HTML σελίδας με τις κατηγορίες και τα προϊόντα τους
        return render_template('products.html', categories=categories_with_products)

    # Διαδρομή για την προσθήκη νέου προϊόντος
    @app.route('/add_product', methods=['POST'])
    def add_product():
        product_name = request.form['product_name']
        product_price = request.form['product_price']
        category_id = request.form['category_id']
        
        conn = get_db_connection()

        # Έλεγχος αν το προϊόν υπάρχει ήδη
        product = conn.execute('SELECT id, is_active FROM products WHERE name = ? AND category_id = ?', (product_name, category_id)).fetchone()
        if product:
            if product['is_active'] == 0:
                # Επανενεργοποίηση του προϊόντος
                conn.execute('UPDATE products SET is_active = 1, price = ? WHERE id = ?', (product_price, product['id']))
                flash('Το προϊόν επανενεργοποιήθηκε επιτυχώς.', 'success')
            else:
                flash('Το προϊόν υπάρχει ήδη.', 'warning')
        else:
            # Εισαγωγή νέου προϊόντος
            conn.execute('INSERT INTO products (name, price, category_id, is_active) VALUES (?, ?, ?, 1)', 
                        (product_name, product_price, category_id))
        
        conn.commit()
        conn.close()

        flash('Το προϊόν προστέθηκε ή ενημερώθηκε επιτυχώς.', 'success')
        return redirect(url_for('settings', tab='product-management'))

    # Διαδρομή για την επεξεργασία υπάρχοντος προϊόντος
    @app.route('/edit_product/<int:product_id>', methods=['POST'])
    def edit_product(product_id):
        product_name = request.form['product_name']
        product_price = request.form['product_price']
        
        conn = get_db_connection()
        # Ενημέρωση του ονόματος και της τιμής του προϊόντος στη βάση δεδομένων
        conn.execute('UPDATE products SET name = ?, price = ? WHERE id = ?', 
                    (product_name, product_price, product_id))
        conn.commit()
        conn.close()
        
        flash('Το προϊόν ενημερώθηκε επιτυχώς.', 'success')
        return redirect(url_for('settings', tab='product-management'))

    # Διαδρομή για τη διαγραφή προϊόντος
    @app.route('/delete_product/<int:product_id>', methods=['POST'])
    def delete_product(product_id):
        conn = get_db_connection()

        # Λογική διαγραφή του προϊόντος
        conn.execute('UPDATE products SET is_active = 0 WHERE id = ?', (product_id,))
        conn.commit()
        conn.close()

        flash('Το προϊόν απενεργοποιήθηκε επιτυχώς.', 'success')
        return redirect(url_for('settings') + '?tab=product-management')

    # Διαδρομή για την προσθήκη νέου εκτυπωτή
    @app.route('/add_printer', methods=['POST'])
    def add_printer():
        name = request.form['name']
        ip_address = request.form['ip_address']
        
        try:
            # Έλεγχος εγκυρότητας της διεύθυνσης IP
            ipaddress.ip_address(ip_address)
        except ValueError:
            flash('Μη έγκυρη διεύθυνση IP. Παρακαλώ εισάγετε μια έγκυρη IP διεύθυνση.', 'danger')
            return redirect(url_for('settings', tab='printer-management'))
        
        conn = get_db_connection()
        # Εισαγωγή νέου εκτυπωτή στη βάση δεδομένων
        conn.execute('INSERT INTO printers (name, ip_address) VALUES (?, ?)', 
                    (name, ip_address))
        conn.commit()
        conn.close()
        
        flash('Ο εκτυπωτής προστέθηκε επιτυχώς.', 'success')
        return redirect(url_for('settings', tab='printer-management'))

    # Διαδρομή για την επεξεργασία υπάρχοντος εκτυπωτή
    @app.route('/edit_printer/<int:printer_id>', methods=['POST'])
    def edit_printer(printer_id):
        name = request.form['name']
        ip_address = request.form['ip_address']
        selected_categories = request.form.getlist('categories')  # Λήψη των επιλεγμένων κατηγοριών ως λίστα

        # Έλεγχος εγκυρότητας της διεύθυνσης IP
        try:
            ipaddress.ip_address(ip_address)
        except ValueError:
            flash('Μη έγκυρη διεύθυνση IP. Παρακαλώ εισάγετε μια έγκυρη IP διεύθυνση.', 'danger')
            return redirect(url_for('settings', tab='printer-management'))

        conn = get_db_connection()
        
        # Ενημέρωση του εκτυπωτή στη βάση δεδομένων
        conn.execute('UPDATE printers SET name = ?, ip_address = ? WHERE id = ?', (name, ip_address, printer_id))

        # Ενημέρωση των κατηγοριών που αντιστοιχούν στον εκτυπωτή
        conn.execute('DELETE FROM printer_categories WHERE printer_id = ?', (printer_id,))
        for category_id in selected_categories:
            conn.execute('INSERT INTO printer_categories (printer_id, category_id) VALUES (?, ?)', (printer_id, category_id))

        conn.commit()
        conn.close()
        
        flash('Ο εκτυπωτής ενημερώθηκε επιτυχώς.', 'success')
        return redirect(url_for('settings', tab='printer-management'))

    # Διαδρομή για την ενημέρωση των ρυθμίσεων εκτυπωτή
    @app.route('/update_printer_settings', methods=['POST'])
    def update_printer_settings():
        conn = get_db_connection()
        
        # Διαγραφή υπαρχουσών ρυθμίσεων εκτυπωτών
        conn.execute('DELETE FROM printer_categories')

        # Εισαγωγή νέων ρυθμίσεων εκτυπωτών με βάση τις επιλογές του χρήστη
        for printer in conn.execute('SELECT * FROM printers').fetchall():
            selected_categories = request.form.getlist(f'categories_{printer["id"]}')
            for category_id in selected_categories:
                conn.execute('INSERT INTO printer_categories (printer_id, category_id) VALUES (?, ?)', 
                            (printer['id'], category_id))
        
        conn.commit()
        conn.close()
        
        flash('Οι ρυθμίσεις εκτυπωτών ενημερώθηκαν επιτυχώς.', 'success')
        return redirect(url_for('settings', tab='printer-management'))

    # Διαδρομή για τη διαγραφή εκτυπωτή
    @app.route('/delete_printer/<int:printer_id>', methods=['POST'])
    def delete_printer(printer_id):
        conn = get_db_connection()
        # Διαγραφή του εκτυπωτή από τη βάση δεδομένων
        conn.execute('DELETE FROM printers WHERE id = ?', (printer_id,))
        conn.commit()
        conn.close()
        
        flash('Ο εκτυπωτής διαγράφηκε επιτυχώς.', 'success')
        return redirect(url_for('settings', tab='printer-management'))

    # Διαδρομή για εκτύπωση παραγγελίας βάσει του ID της
    @app.route('/print_order/<int:order_id>', methods=['POST'])
    def print_order(order_id):
        conn = get_db_connection()

        # Ανάκτηση προϊόντων της παραγγελίας που δεν έχουν εκτυπωθεί ακόμα, συμπεριλαμβανομένων των υποκατηγοριών
        order_items = conn.execute('''
        SELECT oi.id, oi.quantity, p.name, p.price, oi.comments, p.category_id, c.name as category_name, sc.name as subcategory_name
        FROM order_items oi
        JOIN products p ON oi.product_id = p.id
        JOIN categories c ON p.category_id = c.id
        LEFT JOIN subcategories sc ON p.subcategory_id = sc.id  -- Προσθήκη του LEFT JOIN για τις υποκατηγορίες
        WHERE oi.order_id = ? AND oi.printed = 0
    ''', (order_id,)).fetchall()


        if not order_items:
            conn.close()
            return jsonify({'success': False, 'message': 'No new items to print'}), 404

        # Ανάκτηση του αριθμού τραπεζιού που σχετίζεται με την παραγγελία
        table_info = conn.execute('''
            SELECT t.table_number 
            FROM orders o
            JOIN tables t ON o.table_id = t.id
            WHERE o.id = ?
        ''', (order_id,)).fetchone()

        # Σημείωση ότι τα αντικείμενα της παραγγελίας εκτυπώθηκαν
        order_item_ids = [item['id'] for item in order_items]
        conn.execute('''
            UPDATE order_items
            SET printed = 1
            WHERE id IN ({})
        '''.format(','.join('?' * len(order_item_ids))), order_item_ids)

        conn.commit()
        conn.close()

        # Δημιουργία περιεχομένου για εκτύπωση με την υποκατηγορία
        formatted_order_items = []
        for item in order_items:
            # Προσθέτουμε την υποκατηγορία εάν υπάρχει
            subcategory_text = f" ({item['subcategory_name']})" if item['subcategory_name'] else ''
            formatted_item = f"{item['name']}{subcategory_text} - Ποσότητα: {item['quantity']} - Σχόλια: {item['comments'] or ''}"
            formatted_order_items.append(formatted_item)

        # Αποστολή της παραγγελίας στον εκτυπωτή
        send_order_to_printer(formatted_order_items, table_info['table_number'])

        return jsonify({'success': True})

    # Ενημέρωση εκτυπωτή για τις αποδείξεις
    @app.route('/update_invoice_printer', methods=['POST'])
    def update_invoice_printer():
        if 'user_role' not in session or session['user_role'] != 'admin':
            #flash('Δεν έχετε δικαίωμα πρόσβασης σε αυτή τη σελίδα', 'danger')
            return redirect(url_for('index'))

        invoice_printer_id = request.form.get('invoice_printer')

        if not invoice_printer_id:
            flash('Παρακαλώ επιλέξτε έναν έγκυρο εκτυπωτή.', 'danger')
            return redirect(url_for('settings', tab='invoice-management'))

        conn = get_db_connection()
        
        try:
            # Έλεγχος αν υπάρχει ήδη καταχωρημένος εκτυπωτής αποδείξεων
            existing_setting = conn.execute('SELECT * FROM settings WHERE name = "invoice_printer"').fetchone()

            if existing_setting:
                # Ενημέρωση του εκτυπωτή για τις αποδείξεις
                conn.execute('UPDATE settings SET value = ? WHERE name = "invoice_printer"', (invoice_printer_id,))
            else:
                # Εισαγωγή νέου εκτυπωτή για τις αποδείξεις
                conn.execute('INSERT INTO settings (name, value) VALUES ("invoice_printer", ?)', (invoice_printer_id,))
            
            conn.commit()
            flash('Ο εκτυπωτής για τα παραστατικά ενημερώθηκε επιτυχώς!', 'success')
        except Exception as e:
            conn.rollback()
            flash('Παρουσιάστηκε σφάλμα κατά την ενημέρωση του εκτυπωτή.', 'danger')
        finally:
            conn.close()

        return redirect(url_for('settings', tab='invoice-management'))

    # Ακύρωση εκτύπωσης από τη λίστα εκκρεμών παραγγελιών
    @app.route('/cancel_print/<int:print_id>', methods=['POST'])
    def cancel_print(print_id):
        conn = get_db_connection()
        try:
            # Έλεγχος αν η εγγραφή υπάρχει στον πίνακα pending_prints
            print_record = conn.execute('SELECT id FROM pending_prints WHERE id = ?', (print_id,)).fetchone()

            if print_record:
                conn.execute('DELETE FROM pending_prints WHERE id = ?', (print_id,))
            else:
                # Αν δεν βρεθεί στον πίνακα pending_prints, ελέγχει τον πίνακα pending_receipts
                receipt_record = conn.execute('SELECT id FROM pending_receipts WHERE id = ?', (print_id,)).fetchone()

                if receipt_record:
                    conn.execute('DELETE FROM pending_receipts WHERE id = ?', (print_id,))
                else:
                    flash('Η εγγραφή δεν βρέθηκε.', 'danger')
                    return redirect(url_for('settings', tab='pending-prints'))

            conn.commit()
            flash('Η εκτύπωση ακυρώθηκε με επιτυχία.', 'success')
        except Exception as e:
            conn.rollback()
            flash('Σφάλμα κατά την ακύρωση της εκτύπωσης.', 'danger')
        finally:
            conn.close()

        return redirect(url_for('settings', tab='pending-prints'))

    @app.route('/reprint_receipt/<int:order_id>', methods=['POST'])
    def reprint_receipt(order_id):
        if 'user_role' not in session or session['user_role'] != 'admin':
            flash('Δεν έχετε δικαίωμα πρόσβασης για επανεκτύπωση αποδείξεων.', 'danger')
            return redirect(url_for('orders'))

        conn = get_db_connection()

        # Ανάκτηση στοιχείων της παραγγελίας
        order_items = conn.execute('''
            SELECT p.name, oi.quantity, p.price, c.vat_rate
            FROM order_items oi
            JOIN products p ON oi.product_id = p.id
            JOIN categories c ON p.category_id = c.id
            WHERE oi.order_id = ?
        ''', (order_id,)).fetchall()

        # Ανάκτηση ημερομηνίας παραγγελίας
        order_date_row = conn.execute('SELECT order_date FROM orders WHERE id = ?', (order_id,)).fetchone()
        order_date = order_date_row['order_date'] if order_date_row else None

        # Έλεγχος αν λείπει η order_date
        if order_date is None:
            flash('Η παραγγελία δεν έχει καταχωρημένη ημερομηνία.', 'danger')
            conn.close()
            return redirect(url_for('orders'))

        # Μετατροπή της order_date αν είναι συμβολοσειρά
        if isinstance(order_date, str):
            order_date = datetime.strptime(order_date, '%Y-%m-%d %H:%M:%S')

        table_number = conn.execute('SELECT table_id FROM orders WHERE id = ?', (order_id,)).fetchone()['table_id']

        if order_items:
            # Δημιουργία απόδειξης
            receipt_text, invoice_printer_id = format_receipt_for_print(order_items, table_number, order_id, 'reprint', order_date)

            # Δημιουργία νήματος για εκτύπωση ή αποθήκευση για αργότερα
            threading.Thread(target=handle_receipt_printing, args=(invoice_printer_id, receipt_text, order_items, table_number, order_id, 'reprint')).start()

            flash('Η απόδειξη επανεκτυπώθηκε με επιτυχία.', 'success')
        else:
            flash('Η παραγγελία δεν βρέθηκε ή δεν έχει προϊόντα.', 'danger')

        conn.close()
        return redirect(url_for('orders'))


    @app.route('/update_invoice_settings', methods=['POST'])
    def update_invoice_settings():
        try:
            invoice_printer_id = request.form.get('invoice_printer')
            print_receipt_on_close = request.form.get('print_receipt_on_close')

            conn = get_db_connection()
            # Ενημέρωση ρυθμίσεων στη βάση δεδομένων
            conn.execute('INSERT OR REPLACE INTO settings (name, value) VALUES (?, ?)', ("invoice_printer", invoice_printer_id))
            conn.execute('INSERT OR REPLACE INTO settings (name, value) VALUES (?, ?)', ("print_receipt_on_close", print_receipt_on_close))
            conn.commit()
            flash('Οι ρυθμίσεις ενημερώθηκαν επιτυχώς!', 'success')
        except Exception as e:
            conn.rollback()
            flash('Παρουσιάστηκε σφάλμα κατά την ενημέρωση των ρυθμίσεων.', 'danger')
        finally:
            conn.close()
        return redirect(url_for('settings', tab='invoice-management'))
    
    @app.route('/save_settings', methods=['POST'])
    def save_settings():
        if 'user_role' not in session or session['user_role'] != 'admin':
            #flash('Δεν έχετε δικαίωμα πρόσβασης σε αυτή τη σελίδα', 'danger')
            return redirect(url_for('index'))

        language = request.form.get('language')
        currency = request.form.get('currency')
        theme = request.form.get('theme')
        session_timeout = request.form.get('session_timeout')

        try:
            session_timeout = int(session_timeout)
            if session_timeout < 1:
                flash('Ο χρόνος αδράνειας πρέπει να είναι τουλάχιστον 1 λεπτό.', 'danger')
                return redirect(url_for('settings', tab='general'))
        except ValueError:
            flash('Ο χρόνος αδράνειας πρέπει να είναι έγκυρος αριθμός.', 'danger')
            return redirect(url_for('settings', tab='general'))

        conn = get_db_connection()
        try:
            # Ενημέρωση ή εισαγωγή των ρυθμίσεων
            conn.execute('INSERT OR REPLACE INTO settings (name, value) VALUES (?, ?)', ('language', language))
            conn.execute('INSERT OR REPLACE INTO settings (name, value) VALUES (?, ?)', ('currency', currency))
            conn.execute('INSERT OR REPLACE INTO settings (name, value) VALUES (?, ?)', ('theme', theme))
            conn.execute('INSERT OR REPLACE INTO settings (name, value) VALUES (?, ?)', ('session_timeout', session_timeout))
            conn.commit()
            flash('Οι γενικές ρυθμίσεις αποθηκεύτηκαν επιτυχώς!', 'success')
        except Exception as e:
            conn.rollback()
            flash('Παρουσιάστηκε σφάλμα κατά την αποθήκευση των ρυθμίσεων.', 'danger')
        finally:
            conn.close()

        return redirect(url_for('settings', tab='general'))
    
    @app.route('/export_database', methods=['POST'])
    def export_database():
        if 'user_role' not in session or session['user_role'] != 'admin':
            flash('Δεν έχετε δικαίωμα πρόσβασης σε αυτή τη λειτουργία.', 'danger')
            return redirect(url_for('index'))

        try:
            # Δημιουργία προσωρινού φακέλου για το backup
            backup_dir = 'backup_temp'
            os.makedirs(backup_dir, exist_ok=True)

            # Αντιγραφή των βάσεων δεδομένων στον προσωρινό φάκελο
            shutil.copy('database.db', os.path.join(backup_dir, 'database.db'))
            shutil.copy('audit_logs.db', os.path.join(backup_dir, 'audit_logs.db'))

            # Δημιουργία αρχείου ZIP στη μνήμη
            output = io.BytesIO()
            with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(os.path.join(backup_dir, 'database.db'), 'database.db')
                zipf.write(os.path.join(backup_dir, 'audit_logs.db'), 'audit_logs.db')

            # Καθαρισμός προσωρινού φακέλου
            shutil.rmtree(backup_dir)

            # Επαναφορά του δείκτη του BytesIO στην αρχή
            output.seek(0)

            # Όνομα αρχείου για λήψη
            backup_filename = f"tablemaster_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"

            # Επιστροφή του αρχείου ZIP για λήψη
            return send_file(
                output,
                mimetype='application/zip',
                download_name=backup_filename,
                as_attachment=True
            )

        except Exception as e:
            logging.error(f"Failed to export database: {e}")
            flash('Σφάλμα κατά τη δημιουργία του αντιγράφου ασφαλείας.', 'danger')
            return redirect(url_for('settings', tab='backup-restore'))

    @app.route('/import_database', methods=['POST'])
    def import_database():
        if 'user_role' not in session or session['user_role'] != 'admin':
            flash('Δεν έχετε δικαίωμα πρόσβασης σε αυτή τη λειτουργία.', 'danger')
            return redirect(url_for('index'))

        if 'backup_file' not in request.files:
            flash('Δεν επιλέχθηκε αρχείο.', 'danger')
            return redirect(url_for('settings', tab='backup-restore'))

        file = request.files['backup_file']
        if file.filename == '' or not file.filename.endswith('.zip'):
            flash('Παρακαλώ επιλέξτε ένα έγκυρο αρχείο ZIP.', 'danger')
            return redirect(url_for('settings', tab='backup-restore'))

        try:
            # Save the uploaded ZIP file temporarily
            temp_zip = 'temp_backup.zip'
            file.save(temp_zip)

            # Extract the ZIP file
            with zipfile.ZipFile(temp_zip, 'r') as zipf:
                zipf.extractall('backup_restore_temp')

            # Verify and replace the databases
            if os.path.exists('backup_restore_temp/database.db') and os.path.exists('backup_restore_temp/audit_logs.db'):
                # Backup current databases before overwriting
                shutil.move('database.db', 'database.db.bak')
                shutil.move('audit_logs.db', 'audit_logs.db.bak')
                
                shutil.move('backup_restore_temp/database.db', 'database.db')
                shutil.move('backup_restore_temp/audit_logs.db', 'audit_logs.db')
            else:
                raise ValueError("Το αρχείο ZIP δεν περιέχει τα απαραίτητα database.db και audit_logs.db.")

            # Clean up
            shutil.rmtree('backup_restore_temp')
            os.remove(temp_zip)

            flash('Η βάση δεδομένων επαναφέρθηκε επιτυχώς!', 'success')
        except Exception as e:
            logging.error(f"Failed to import database: {e}")
            # Restore original databases if something goes wrong
            if os.path.exists('database.db.bak'):
                shutil.move('database.db.bak', 'database.db')
            if os.path.exists('audit_logs.db.bak'):
                shutil.move('audit_logs.db.bak', 'audit_logs.db')
            flash('Σφάλμα κατά την επαναφορά του αντιγράφου ασφαλείας.', 'danger')

        return redirect(url_for('settings', tab='backup-restore'))

    # Σελίδα ρυθμίσεων για διαχειριστές
    @app.route('/settings', methods=['GET'])
    def settings():
        if 'user_role' not in session or session['user_role'] != 'admin':
            #flash('Δεν έχετε δικαίωμα πρόσβασης σε αυτή τη σελίδα', 'danger')
            return redirect(url_for('index'))

        conn = get_db_connection()
        audit_conn = get_audit_db_connection()
        
        try:
            # Ανάκτηση κατηγοριών, προϊόντων και υποκατηγοριών
            categories = conn.execute('SELECT * FROM categories WHERE is_active = 1').fetchall()
            products = conn.execute('SELECT * FROM products WHERE is_active = 1').fetchall()
            printers = conn.execute('SELECT * FROM printers').fetchall()
            users = conn.execute('SELECT * FROM users').fetchall()
            company_info = conn.execute('SELECT * FROM company_info').fetchone()

            # Ανάκτηση υποκατηγοριών για κάθε κατηγορία
            subcategories_by_category = {}
            for category in categories:
                subcategories = conn.execute('SELECT * FROM subcategories WHERE category_id = ?', (category['id'],)).fetchall()
                subcategories_by_category[category['id']] = subcategories

            # Ανάκτηση του εκτυπωτή για τις αποδείξεις
            invoice_printer_id = conn.execute('SELECT value FROM settings WHERE name = "invoice_printer"').fetchone()

            # Ανάκτηση της επιλογής εκτύπωσης απόδειξης για κάθε παραγγελία
            print_receipt_on_order = conn.execute('SELECT value FROM settings WHERE name = "print_receipt_on_order"').fetchone()

            # Ανάκτηση της επιλογής εκτύπωσης απόδειξης κατά το κλείσιμο του τραπεζιού
            print_receipt_on_close = conn.execute('SELECT value FROM settings WHERE name = "print_receipt_on_close"').fetchone()

            # Ανάκτηση του session timeout
            session_timeout = conn.execute('SELECT value FROM settings WHERE name = "session_timeout"').fetchone()
            session_timeout_value = session_timeout['value'] if session_timeout else 10  # Προεπιλογή 10 λεπτά

            # Ανάκτηση των κατηγοριών που συνδέονται με κάθε εκτυπωτή
            printer_categories = {
                printer['id']: [cat['category_id'] for cat in conn.execute(
                    'SELECT category_id FROM printer_categories WHERE printer_id = ?',
                    (printer['id'],)
                ).fetchall()]
                for printer in printers
            }

            # Δομή προϊόντων κατηγοριοποιημένων
            categorized_products = {category['id']: [] for category in categories}
            for product in products:
                category_id = product['category_id']
                if category_id in categorized_products:
                    categorized_products[category_id].append(product)
                else:
                    print(f"Warning: Το προϊόν με ID {product['id']} ανήκει σε διαγραμμένη κατηγορία.")

            categories_with_products_and_subcategories = [
                {
                    **category,
                    'products': categorized_products[category['id']],
                    'subcategories': subcategories_by_category.get(category['id'], [])
                }
                for category in categories
            ]

            # Ανάκτηση εκκρεμών εκτυπώσεων και αποδείξεων
            pending_prints = conn.execute('''
                SELECT p.id, p.table_number, p.is_receipt, p.timestamp, pr.name as printer_name
                FROM pending_prints p
                JOIN printers pr ON p.printer_id = pr.id
                UNION ALL
                SELECT r.id, r.table_number, 1 as is_receipt, r.timestamp, pr.name as printer_name
                FROM pending_receipts r
                JOIN printers pr ON r.printer_id = pr.id
            ''').fetchall()

            # Ανάκτηση του license key
            license_key = get_license_key()

            # Ανάκτηση audit logs με φίλτρα
            date_from = request.args.get('date_from', '')
            date_to = request.args.get('date_to', '')
            user_id = request.args.get('user_id', '')

            audit_query = 'SELECT * FROM deletion_logs WHERE 1=1'
            audit_params = []

            if date_from:
                audit_query += ' AND DATE(deletion_time) >= ?'
                audit_params.append(date_from)
            if date_to:
                audit_query += ' AND DATE(deletion_time) <= ?'
                audit_params.append(date_to)
            if user_id:
                audit_query += ' AND user_id = ?'
                audit_params.append(user_id)

            audit_query += ' ORDER BY deletion_time DESC'
            audit_logs = audit_conn.execute(audit_query, audit_params).fetchall()

        except Exception as e:
            logging.error(f"Σφάλμα κατά τη φόρτωση των ρυθμίσεων: {e}")
            flash('Προέκυψε σφάλμα κατά τη φόρτωση των ρυθμίσεων.', 'danger')
            return redirect(url_for('index'))

        finally:
            conn.close()
            audit_conn.close()

        return render_template(
            'settings.html',
            categories=categories_with_products_and_subcategories,
            printers=printers,
            users=users,
            company_info=company_info,
            printer_categories=printer_categories,
            invoice_printer_id=invoice_printer_id['value'] if invoice_printer_id else None,
            print_receipt_on_order=print_receipt_on_order['value'] if print_receipt_on_order else 'no',
            print_receipt_on_close=print_receipt_on_close['value'] if print_receipt_on_close else 'no',
            pending_prints=pending_prints,
            license_key=license_key,
            audit_logs=audit_logs,
            session_timeout=session_timeout_value  # Πέρασμα της τιμής στο template
        )

    # Ενημέρωση των στοιχείων της εταιρείας
    @app.route('/update_company_info', methods=['POST'])
    def update_company_info():
        if 'user_role' not in session or session['user_role'] != 'admin':
            #flash('Δεν έχετε δικαίωμα πρόσβασης σε αυτή τη σελίδα', 'danger')
            return redirect(url_for('index'))

        company_name = request.form.get('company_name')
        company_address = request.form.get('company_address')
        company_tax_id = request.form.get('company_tax_id')
        company_phone = request.form.get('company_phone')
        company_tax_office = request.form.get('company_tax_office')

        # Έλεγχος μορφής ΑΦΜ (πρέπει να έχει ακριβώς 9 ψηφία)
        if not re.match(r'^\d{9}$', company_tax_id):
            flash('Το ΑΦΜ πρέπει να περιέχει ακριβώς 9 ψηφία.', 'danger')
            return redirect(url_for('settings', tab='company-info'))

        # Έλεγχος μορφής τηλεφώνου (πρέπει να έχει 10 ψηφία και να ξεκινάει από 2 ή 6)
        if not re.match(r'^[26]\d{9}$', company_phone):
            flash('Το τηλέφωνο πρέπει να είναι έγκυρο ελληνικό τηλέφωνο με 10 ψηφία.', 'danger')
            return redirect(url_for('settings', tab='company-info'))

        conn = get_db_connection()

        # Έλεγχος εάν υπάρχουν ήδη καταχωρημένα στοιχεία εταιρείας
        existing_info = conn.execute('SELECT * FROM company_info LIMIT 1').fetchone()

        if existing_info:
            # Ενημέρωση των στοιχείων
            conn.execute('''
                UPDATE company_info
                SET company_name = ?, company_address = ?, company_tax_id = ?, company_phone = ?, company_tax_office = ?
                WHERE id = ?
            ''', (company_name, company_address, company_tax_id, company_phone, company_tax_office, existing_info['id']))
        else:
            # Εισαγωγή νέων στοιχείων
            conn.execute('''
                INSERT INTO company_info (company_name, company_address, company_tax_id, company_phone, company_tax_office)
                VALUES (?, ?, ?, ?, ?)
            ''', (company_name, company_address, company_tax_id, company_phone, company_tax_office))

        conn.commit()
        conn.close()

        flash('Τα στοιχεία της εταιρείας ενημερώθηκαν επιτυχώς!', 'success')
        return redirect(url_for('settings', tab='company-info'))



# Εκκίνηση της εφαρμογής Flask
if __name__ == '__main__':
    if check_license():
        init_db()
        init_audit_db()
        create_admin_if_not_exists()
        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
