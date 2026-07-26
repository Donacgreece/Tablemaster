"""Billing and split-payment routes."""

import threading
from datetime import datetime

from flask import redirect, render_template, request, session, url_for

from tablemaster.database import get_db_connection


def register_billing_routes(app, format_receipt_for_print, handle_receipt_printing):
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
