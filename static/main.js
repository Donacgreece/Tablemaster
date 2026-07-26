import { saveOrderOffline, getOfflineOrders, deleteOrder } from './db.js';

// Συνάρτηση για προσθήκη παραγγελίας (online ή offline)
async function addOrder(order) {
  if (navigator.onLine) {
    // Εάν είμαστε online, στείλε την παραγγελία στον server
    await fetch('/add_order', {
      method: 'POST',
      body: JSON.stringify(order),
      headers: {
        'Content-Type': 'application/json',
      },
    });
  } else {
    // Εάν είμαστε offline, αποθήκευσε την παραγγελία στο IndexedDB
    await saveOrderOffline(order);
    alert('Η παραγγελία αποθηκεύτηκε τοπικά και θα συγχρονιστεί όταν επανέλθει η σύνδεση.');
  }
}

// Συγχρονισμός δεδομένων όταν επανέλθει η σύνδεση
window.addEventListener('online', async () => {
  const orders = await getOfflineOrders();

  for (const order of orders) {
    try {
      await fetch('/add_order', {
        method: 'POST',
        body: JSON.stringify(order),
        headers: {
          'Content-Type': 'application/json',
        },
      });

      // Διαγραφή της παραγγελίας από το IndexedDB εάν ο συγχρονισμός ήταν επιτυχής
      await deleteOrder(order.id);
    } catch (err) {
      console.error('Σφάλμα κατά τον συγχρονισμό της παραγγελίας:', err);
    }
  }

  alert('Όλες οι τοπικές παραγγελίες συγχρονίστηκαν με επιτυχία.');
});
