import subprocess
import re
import os
from cryptography.fernet import Fernet

def get_mac_address():
    """
    Ζητά τη MAC διεύθυνση από τον χρήστη ή επιστρέφει τη MAC διεύθυνση της συσκευής.
    """
    # Ζητά από τον χρήστη να εισάγει τη MAC διεύθυνση
    mac_address = input("Εισάγετε τη MAC διεύθυνση (ή πατήστε Enter για αυτόματη ανίχνευση): ").strip()
    
    # Αν ο χρήστης εισάγει μια MAC διεύθυνση, την επιστρέφουμε
    if mac_address:
        # Ελέγχει αν η MAC διεύθυνση είναι έγκυρη
        if re.match(r"([A-Fa-f0-9]{2}[:-]){5}([A-Fa-f0-9]{2})", mac_address):
            return mac_address.upper()  # Μετατροπή σε κεφαλαία
        else:
            print("Μη έγκυρη μορφή MAC διεύθυνσης. Παρακαλώ δοκιμάστε ξανά.")
            return get_mac_address()  # Καλεί ξανά τη συνάρτηση για νέα εισαγωγή

    # Αν δεν δοθεί MAC διεύθυνση, προσπαθούμε να την ανιχνεύσουμε αυτόματα
    try:
        if os.name == "nt":  # Windows
            output = subprocess.check_output("ipconfig /all", shell=True).decode('utf-8', errors='ignore')
            mac_address = re.search(r"([A-F0-9]{2}[:-]){5}([A-F0-9]{2})", output, re.I)
        else:  # Unix/Linux/Mac
            output = subprocess.check_output("ifconfig", shell=True).decode()
            mac_address = re.search(r"([a-f0-9]{2}(:[a-f0-9]{2}){5})", output)

        if mac_address:
            return mac_address.group(0).upper()  # Μετατροπή σε κεφαλαία
        else:
            print("Δεν βρέθηκε MAC διεύθυνση.")
            return None

    except Exception as e:
        print(f"Σφάλμα κατά την ανάκτηση της MAC διεύθυνσης: {e}")
        return None

def generate_license_key(mac_address):
    """
    Δημιουργεί ένα License Key με βάση τη MAC διεύθυνση.
    """
    return f"LICENSE-{mac_address.replace(':', '').replace('-', '')}"

def encrypt_license_key(license_key, key):
    """
    Κρυπτογραφεί το License Key χρησιμοποιώντας το κλειδί κρυπτογράφησης.
    """
    fernet = Fernet(key)
    encrypted_key = fernet.encrypt(license_key.encode())
    return encrypted_key

def save_to_file(data, filename):
    """
    Αποθηκεύει δεδομένα σε αρχείο.
    """
    with open(filename, 'wb') as file:
        file.write(data)

def main():
    # Δημιουργία κλειδιού κρυπτογράφησης
    key = Fernet.generate_key()

    # Αποθήκευση του κλειδιού σε αρχείο για μελλοντική χρήση
    save_to_file(key, "encryption.key")
    print(f"Το κλειδί κρυπτογράφησης αποθηκεύτηκε με επιτυχία στο encryption.key.")

    # Αποκτά τη MAC διεύθυνση
    mac_address = get_mac_address()
    if mac_address:
        print(f"MAC Address: {mac_address}")

        # Δημιουργεί το License Key
        license_key = generate_license_key(mac_address)
        print(f"Generated License Key: {license_key}")

        # Κρυπτογραφεί το License Key
        encrypted_key = encrypt_license_key(license_key, key)
        print(f"Encrypted License Key: {encrypted_key}")

        # Αποθηκεύει το κρυπτογραφημένο License Key σε αρχείο
        save_to_file(encrypted_key, "license.key")
        print("Το κρυπτογραφημένο License Key αποθηκεύτηκε με επιτυχία στο license.key.")
    else:
        print("Δεν ήταν δυνατή η ανάκτηση της MAC διεύθυνσης.")

if __name__ == "__main__":
    main()
