"""Core, authentication, upload, and user-management routes."""

import os
import time

from flask import flash, jsonify, redirect, render_template, request, send_from_directory, session, url_for
from werkzeug.utils import secure_filename

from tablemaster.database import get_db_connection
from tablemaster.services.spreadsheets import allowed_file, process_excel_file


def register_core_routes(app):
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
