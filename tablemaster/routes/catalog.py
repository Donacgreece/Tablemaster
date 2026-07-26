"""Product catalogue, category, and subcategory routes."""

from flask import flash, redirect, render_template, request, url_for

from tablemaster.database import get_db_connection


def register_catalog_routes(app):
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
