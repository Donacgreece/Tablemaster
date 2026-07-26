document.addEventListener('DOMContentLoaded', function () {
    const checkboxes = document.querySelectorAll('.item-checkbox');
    const selectedTotalElement = document.getElementById('selectedTotal');
    const completePaymentButton = document.getElementById('completePaymentButton');
    const paymentForm = document.getElementById('paymentForm');
    const amountGivenInput = document.getElementById('amountGiven');
    const changeDueElement = document.getElementById('changeDue');

    function calculateTotal() {
        let total = 0;
        checkboxes.forEach(checkbox => {
            if (checkbox.checked) {
                total += parseFloat(checkbox.getAttribute('data-price'));
            }
        });
        selectedTotalElement.textContent = total.toFixed(2) + '€';
        calculateChange();
    }

    function calculateChange() {
        const total = parseFloat(selectedTotalElement.textContent.replace('€', '')) || 0;
        const amountGiven = parseFloat(amountGivenInput.value) || 0;
        const change = amountGiven - total;
        changeDueElement.textContent = change.toFixed(2) + '€';
        changeDueElement.classList.toggle('text-danger', change < 0);
    }

    completePaymentButton.addEventListener('click', function (event) {
        event.preventDefault();
        const selectedItems = Array.from(checkboxes).filter(cb => cb.checked).map(cb => cb.value);

        if (selectedItems.length === 0) {
            alert('Δεν έχετε επιλέξει προϊόν!');
            return;
        }

        const totalItems = checkboxes.length;
        const allPaid = selectedItems.length === totalItems;

        if (allPaid) {
            $('#closeTableModal').modal('show');
        } else {
            $('#paymentMethodModal').modal('show');
        }
    });

    document.querySelectorAll('.payment-method-btn').forEach(button => {
        button.addEventListener('click', function () {
            const method = this.getAttribute('data-method');
            const input = document.createElement('input');
            input.type = 'hidden';
            input.name = 'payment_method';
            input.value = method;
            paymentForm.appendChild(input);
            paymentForm.submit();
        });
    });

    checkboxes.forEach(checkbox => checkbox.addEventListener('change', calculateTotal));
    amountGivenInput.addEventListener('input', calculateChange);

    calculateTotal();
});