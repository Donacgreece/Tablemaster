"use strict";

function resetFilters() {
    document.getElementById("status").selectedIndex = 0;
    document.getElementById("user_id").selectedIndex = 0;
    document.getElementById("table_id").value = "";
    document.getElementById("date_from").value = "";
    document.getElementById("date_to").value = "";
    document.getElementById("ordersForm").submit();
}
