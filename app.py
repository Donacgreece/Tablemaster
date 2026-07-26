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
from tablemaster.licensing import check_license, get_license_key

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

    from tablemaster.database import (
        create_admin_if_not_exists,
        get_audit_db_connection,
        get_db_connection,
        init_audit_db,
        init_db,
    )

    from tablemaster.services.spreadsheets import allowed_file, process_excel_file

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

    from tablemaster.routes.core import register_core_routes

    register_core_routes(app)
    from tablemaster.routes.tables import register_table_routes

    register_table_routes(app, format_receipt_for_print, handle_receipt_printing)
    from tablemaster.routes.orders import register_order_routes

    register_order_routes(
        app,
        format_order_for_print,
        is_printer_available,
        save_order_for_later,
        send_to_printer,
    )
    from tablemaster.routes.billing import register_billing_routes

    register_billing_routes(app, format_receipt_for_print, handle_receipt_printing)
    from tablemaster.routes.catalog import register_catalog_routes

    register_catalog_routes(app)
    from tablemaster.routes.admin_actions import register_admin_action_routes

    register_admin_action_routes(app, format_receipt_for_print, handle_receipt_printing)
    from tablemaster.routes.settings import register_settings_routes

    register_settings_routes(app)

# Εκκίνηση της εφαρμογής Flask
if __name__ == '__main__':
    if check_license():
        init_db()
        init_audit_db()
        create_admin_if_not_exists()
        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
