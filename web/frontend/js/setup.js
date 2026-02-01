// web/frontend/js/setup.js

function getQueryParam(name) {
    return new URLSearchParams(window.location.search).get(name);
}

async function loadSetup() {
    const setup = getQueryParam("name");
    if (!setup) {
        console.error("Не передано имя сетапа в параметрах URL");
        return;
    }

    document.getElementById("setup-title").innerText = setup;

    try {
        const data = await window.apiGet("/setup-analytics/by-symbol");
        const items = Array.isArray(data) ? data : data.items || [];

        const filtered = items.filter(i => i.setup === setup);

        const totalTrades = filtered.reduce((s, x) => s + (x.total_trades || 0), 0);

        const stats = document.getElementById("setup-stats");
        stats.innerHTML = `
            <p>Сделок: ${totalTrades}</p>
        `;

        const table = document.getElementById("coins-table");
        table.innerHTML = filtered.map(i => `
            <div class="trade-card">
                <b>${i.symbol}</b> — ${i.total_trades} сделок
            </div>
        `).join("");
    } catch (e) {
        console.error("Ошибка при загрузке аналитики по сетапу:", e);
    }
}

window.addEventListener("DOMContentLoaded", loadSetup);
