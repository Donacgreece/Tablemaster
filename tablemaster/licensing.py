"""License validation for TableMaster installations."""

import os
import re
import subprocess

from cryptography.fernet import Fernet

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
