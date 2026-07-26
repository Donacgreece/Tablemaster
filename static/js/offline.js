// offline.js
function showOfflineMessage() {
    document.getElementById('offlineOverlay').style.display = 'block';
    document.body.style.pointerEvents = 'none'; // Απενεργοποίηση όλων των αλληλεπιδράσεων
}

function hideOfflineMessage() {
    document.getElementById('offlineOverlay').style.display = 'none';
    document.body.style.pointerEvents = 'auto'; // Επανενεργοποίηση των αλληλεπιδράσεων
}

function checkConnection() {
    if (!navigator.onLine) {
        showOfflineMessage();
    } else {
        hideOfflineMessage();
    }
}

// Άμεσος έλεγχος σύνδεσης κατά την εκκίνηση της σελίδας
window.addEventListener('load', function() {
    checkConnection();
});

// Ανίχνευση άμεσων αλλαγών στη σύνδεση
window.addEventListener('online', hideOfflineMessage);
window.addEventListener('offline', showOfflineMessage);

// Επαναλαμβανόμενος έλεγχος σύνδεσης κάθε 1 δευτερόλεπτο για να εξασφαλιστεί ότι δεν υπάρχουν παραθυράκια χρόνου
setInterval(checkConnection, 1000);


