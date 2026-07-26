"""Order history, order entry, export, printing, and transfer routes."""

import io
import threading
from datetime import datetime

import pandas as pd
from flask import flash, jsonify, redirect, render_template, request, send_file, session, url_for

from tablemaster.database import get_db_connection


def register_order_routes(app, format_order_for_print, is_printer_available, save_order_for_later, send_to_printer):
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
