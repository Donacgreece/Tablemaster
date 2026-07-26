const CACHE_NAME = 'v1';
const OFFLINE_URL = '/offline.html';

// Αρχεία που θα αποθηκευτούν στην cache κατά την εγκατάσταση
const CACHE_FILES = [
    '/',
    '/static/css/base.css',
    '/static/css/tables.css',
    '/static/css/manage_table.css',
    '/static/js/tables.js',
    '/static/js/manage_table.js',
    '/static/js/close_table.js',
    '/static/icons/icon-192x192.png',
    '/static/icons/icon-512x512.png',
    OFFLINE_URL
];

// Εγκατάσταση του service worker και αποθήκευση των αρχείων στην cache
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll(CACHE_FILES);
        })
    );
    self.skipWaiting();
});

// Ενεργοποίηση του service worker και καθαρισμός παλαιότερων caches
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cacheName) => {
                    if (cacheName !== CACHE_NAME) {
                        return caches.delete(cacheName);
                    }
                })
            );
        })
    );
    self.clients.claim();
});

// Διαχείριση των αιτημάτων fetch
self.addEventListener('fetch', (event) => {
    event.respondWith(
        caches.match(event.request).then((response) => {
            // Επιστροφή του response από την cache, αλλιώς δοκιμή να το φορτώσει από το δίκτυο
            return response || fetch(event.request).catch(() => caches.match(OFFLINE_URL));
        })
    );
});

// Επεξεργασία μηνυμάτων που στέλνονται στον service worker
self.addEventListener('message', (event) => {
    if (event.data.action === 'skipWaiting') {
        self.skipWaiting();
    }
});
