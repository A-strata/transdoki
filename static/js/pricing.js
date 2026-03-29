(function () {
    const calc = document.getElementById('pricing-calc');
    if (!calc) return;

    const FREE_ORGS     = parseInt(calc.dataset.freeOrgs, 10);
    const FREE_VEHICLES = parseInt(calc.dataset.freeVehicles, 10);
    const FREE_USERS    = parseInt(calc.dataset.freeUsers, 10);
    const PRICE_ORG     = parseInt(calc.dataset.priceOrg, 10);
    const PRICE_VEHICLE = parseInt(calc.dataset.priceVehicle, 10);
    const PRICE_USER    = parseInt(calc.dataset.priceUser, 10);

    function calcPricing() {
        const firms = parseInt(document.getElementById('c-firms').value, 10);
        const cars  = parseInt(document.getElementById('c-cars').value, 10);
        const users = parseInt(document.getElementById('c-users').value, 10);

        document.getElementById('c-firms-val').textContent = firms;
        document.getElementById('c-cars-val').textContent  = cars;
        document.getElementById('c-users-val').textContent = users;

        const paidFirms = Math.max(0, firms - FREE_ORGS);
        const paidCars  = Math.max(0, cars  - FREE_VEHICLES);
        const paidUsers = Math.max(0, users - FREE_USERS);

        const total = paidFirms * PRICE_ORG + paidCars * PRICE_VEHICLE + paidUsers * PRICE_USER;

        const totalEl     = document.getElementById('c-total');
        const breakdownEl = document.getElementById('c-breakdown');
        const ctaEl       = document.getElementById('c-cta');

        if (total === 0) {
            totalEl.textContent = '0 ₽ — бесплатно';
            totalEl.className   = 'calc-result-amount is-free';
            breakdownEl.textContent = 'Вы укладываетесь в бесплатный тариф';
            ctaEl.textContent   = 'Начать бесплатно';
        } else {
            totalEl.textContent = '~' + total.toLocaleString('ru-RU') + ' ₽';
            totalEl.className   = 'calc-result-amount';
            const parts = [];
            if (paidFirms > 0) parts.push(paidFirms + ' доп. фирм × ' + PRICE_ORG + ' ₽');
            if (paidCars  > 0) parts.push(paidCars  + ' доп. авто × ' + PRICE_VEHICLE + ' ₽');
            if (paidUsers > 0) parts.push(paidUsers + ' доп. польз. × ' + PRICE_USER + ' ₽');
            breakdownEl.textContent = parts.join(' + ');
            ctaEl.textContent = 'Попробовать бесплатно';
        }
    }

    calc.querySelectorAll('input[type=range]').forEach(function (input) {
        input.addEventListener('input', calcPricing);
    });

    calcPricing();
})();
