import { openDB } from 'idb';

const dbPromise = openDB('tablemaster-db', 1, {
  upgrade(db) {
    // Δημιουργία πίνακα για offline αποθήκευση παραγγελιών
    db.createObjectStore('orders', { keyPath: 'id', autoIncrement: true });
  },
});

// Συνάρτηση για αποθήκευση παραγγελίας στο IndexedDB
export async function saveOrderOffline(order) {
  const db = await dbPromise;
  await db.put('orders', order);
}

// Συνάρτηση για ανάκτηση όλων των παραγγελιών από το IndexedDB
export async function getOfflineOrders() {
  const db = await dbPromise;
  return db.getAll('orders');
}

// Συνάρτηση για διαγραφή παραγγελίας από το IndexedDB μετά το συγχρονισμό
export async function deleteOrder(orderId) {
  const db = await dbPromise;
  return db.delete('orders', orderId);
}
