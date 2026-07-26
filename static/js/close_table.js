document.addEventListener("DOMContentLoaded", function() {
    var closeTableButton = document.querySelector('.close-table-button');
    var paymentMethodModal = document.getElementById('paymentMethodModal');
    var cashPaymentButton = document.getElementById('cashPayment');
    var cardPaymentButton = document.getElementById('cardPayment');
    
    closeTableButton.addEventListener('click', function(event) {
        event.preventDefault();
        $(paymentMethodModal).modal('show');
    });

    function submitCloseTable(paymentMethod) {
        // Στείλτε το αίτημα για να κλείσει το τραπέζι με τη μέθοδο πληρωμής
        fetch(`/close_table/${table_id}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ payment_method: paymentMethod })
        }).then(response => {
            if (response.ok) {
                window.location.href = '/tables';
            } else {
                alert('Σφάλμα κατά το κλείσιμο του τραπεζιού.');
            }
        });
    }

    cashPaymentButton.addEventListener('click', function() {
        submitCloseTable('cash');
    });

    cardPaymentButton.addEventListener('click', function() {
        submitCloseTable('card');
    });
});
