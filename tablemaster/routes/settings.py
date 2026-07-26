"""Settings dashboard and company-profile routes."""

import logging
import re

from flask import flash, redirect, render_template, request, session, url_for

from tablemaster.database import get_audit_db_connection, get_db_connection
from tablemaster.licensing import get_license_key


def register_settings_routes(app):
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
