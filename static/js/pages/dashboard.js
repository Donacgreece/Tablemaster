"use strict";

function dismissWarning() {
    fetch("/dismiss_warning", {
        method: "POST",
        headers: { "Content-Type": "application/json" }
    })
        .then(function (response) { return response.json(); })
        .then(function (data) {
            if (data.success) {
                const warning = document.querySelector(".persistent-warning");
                if (warning) warning.remove();
            }
        })
        .catch(function (error) { console.error("Error:", error); });
}
