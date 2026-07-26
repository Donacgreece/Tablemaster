"""Printer administration, receipt settings, and backup actions."""

import io
import ipaddress
import logging
import os
import shutil
import threading
import zipfile
from datetime import datetime

from flask import flash, jsonify, redirect, request, send_file, session, url_for

from tablemaster.database import get_db_connection


def register_admin_action_routes(app, format_receipt_for_print, handle_receipt_printing):
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
