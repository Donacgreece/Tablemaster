document.addEventListener("DOMContentLoaded", function() {
    // Φίλτρο προϊόντων ανά κατηγορία
    var categorySelect = document.getElementById('category_id');
    var productSelect = document.getElementById('product_id');
    var addAnotherButton = document.getElementById('addAnotherButton');
    var orderForm = document.getElementById('orderForm');

    var allProducts = Array.from(productSelect.querySelectorAll('option'));

    function filterProducts() {
        var selectedCategoryId = categorySelect.value;

        productSelect.innerHTML = allProducts[0].outerHTML;

        allProducts.slice(1).forEach(function(option) {
            if (option.getAttribute('data-category') === selectedCategoryId) {
                productSelect.appendChild(option);
            }
        });

        productSelect.value = '';
    }

    categorySelect.addEventListener('change', filterProducts);
    filterProducts();

    // Διαχείριση της προσθήκης νέου προϊόντος χωρίς ανανέωση της σελίδας
    addAnotherButton.addEventListener('click', function() {
        var formData = new FormData(orderForm);

        fetch(orderForm.action, {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Επαναφορά φόρμας χωρίς ανανέωση της σελίδας
                orderForm.reset();
                categorySelect.value = '';
                productSelect.innerHTML = '<option value="">Επιλέξτε Προϊόν</option>';
                filterProducts();
            } else {
                alert('Σφάλμα κατά την προσθήκη του προϊόντος.');
            }
        })
        .catch(error => console.error('Σφάλμα:', error));
    });

    // Διαχείριση της ολοκλήρωσης της παραγγελίας και εκτύπωση των νέων στοιχείων
    orderForm.addEventListener('submit', function(e) {
        e.preventDefault();
        var formData = new FormData(orderForm);

        fetch(orderForm.action, {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Εκτύπωση μόνο των νέων στοιχείων που προστέθηκαν στην τρέχουσα παραγγελία
                printOrder(data.order_id);
                // Ανανεώνει τη σελίδα μετά την ολοκλήρωση παραγγελίας
                setTimeout(() => window.location.reload(), 1000);
            } else {
                alert('Σφάλμα κατά την ολοκλήρωση της παραγγελίας.');
            }
        })
        .catch(error => console.error('Σφάλμα:', error));
    });

    function printOrder(orderId) {
        fetch(`/print_order/${orderId}`, {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            if (!data.success) {
                alert('Σφάλμα κατά την εκτύπωση της παραγγελίας.');
            }
        })
        .catch(error => console.error('Σφάλμα:', error));
    }

    var statusForm = document.querySelector('form[action*="change_table_status"]');
    
    statusForm.addEventListener('submit', function(e) {
        e.preventDefault();
        var formData = new FormData(statusForm);

        fetch(statusForm.action, {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                location.reload();
            } else {
                alert('Σφάλμα κατά την ενημέρωση της κατάστασης.');
            }
        })
        .catch(error => console.error('Σφάλμα:', error));
    });

    // Υποβολή της φόρμας μεταφοράς παραγγελιών
    var transferOrdersForm = document.getElementById('transferOrdersForm');
    transferOrdersForm.addEventListener('submit', function(e) {
        e.preventDefault();
        var formData = new FormData(transferOrdersForm);

        fetch(transferOrdersForm.action, {
            method: 'POST',
            body: formData
        })
        .then(response => {
            if (response.redirected) {
                window.location.href = response.url;
            } else {
                return response.json();
            }
        })
        .catch(error => console.error('Σφάλμα:', error));
    });
});
