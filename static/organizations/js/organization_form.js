document.addEventListener("DOMContentLoaded", function () {
    const integrationCheckbox =
        document.getElementById("id_petrolplus_integration_enabled") ||
        document.querySelector('input[name="petrolplus_integration_enabled"]');

    const credentialsBlock = document.getElementById("petrolplus-credentials");

    function toggleCredentials() {
        if (!integrationCheckbox || !credentialsBlock) return;
        credentialsBlock.classList.toggle("is-hidden", !integrationCheckbox.checked);
    }

    if (integrationCheckbox) {
        integrationCheckbox.addEventListener("change", toggleCredentials);
    }

    toggleCredentials();
});