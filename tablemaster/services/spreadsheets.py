"""Excel catalogue import helpers."""

import pandas as pd

from tablemaster.database import get_db_connection

ALLOWED_EXTENSIONS = {"xls", "xlsx"}

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
