document.addEventListener('DOMContentLoaded', function () {
    // Αρχικό hash
    let previousHash = '';

    // Λειτουργία για έλεγχο του hash από τον server
    function checkTableStatus() {
        fetch('/table_status_hash')
            .then(response => response.json())
            .then(data => {
                const currentHash = data.hash;
                // Αν το hash έχει αλλάξει, ανανέωσε τη σελίδα
                if (previousHash && previousHash !== currentHash) {
                    location.reload(); // Ανανέωση της σελίδας
                }
                // Αποθηκεύουμε το τρέχον hash για μελλοντική σύγκριση
                previousHash = currentHash;
            })
            .catch(error => console.error('Error fetching table status hash:', error));
    }

    // Έλεγχος του hash κάθε 10 δευτερόλεπτα
    setInterval(checkTableStatus, 1000);
});
