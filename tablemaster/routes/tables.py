"""Table floor, table lifecycle, and table-item routes."""

import hashlib
import threading
from datetime import datetime

from flask import flash, jsonify, redirect, render_template, request, session, url_for

from tablemaster.database import get_audit_db_connection, get_db_connection


def register_table_routes(app, format_receipt_for_print, handle_receipt_printing):
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
