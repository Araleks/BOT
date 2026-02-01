// web/frontend/js/index.js

async function loadInitialInfo() {
    document.getElementById("initial-balance").innerText = "Начальный депозит: 100 000$";
    document.getElementById("start-date").innerText = "Дата запуска: 2025-01-01";
}

async function loadClosedStats() {
    try {
        const trades = await window.apiGet("/trades");
        const closed = trades.filter(t => t.closed_at_ms);

        const pnl = closed.reduce((s, t) => s + (t.pnl_usdt || 0), 0);
        const wins = closed.filter(t => (t.pnl_usdt || 0) > 0);
        const losses = closed.filter(t => (t.pnl_usdt || 0) < 0);
        const longs = closed.filter(t => t.direction === "long");
        const shorts = closed.filter(t => t.direction === "short");

        document.getElementById("closed-balance").innerText =
            "Баланс (закрытые): " + (100000 + pnl).toFixed(2);
        document.getElementById("closed-pnl").innerText =
            "PnL закрытых: " + pnl.toFixed(2);
        document.getElementById("closed-count").innerText =
            "Закрытых сделок: " + closed.length;
        document.getElementById("closed-win").innerText =
            "Прибыльных: " + wins.length;
        document.getElementById("closed-loss").innerText =
            "Убыточных: " + losses.length;
        document.getElementById("closed-long").innerText =
            "Лонги: " + longs.length;
        document.getElementById("closed-short").innerText =
            "Шорты: " + shorts.length;
        document.getElementById("closed-winrate").innerText =
            "Winrate: " + (closed.length ? (wins.length / closed.length * 100).toFixed(1) : "0.0") + "%";
    } catch (e) {
        console.error("Ошибка при загрузке закрытой статистики:", e);
    }
}

async function loadSetups() {
    try {
        const setups = await window.apiGet("/setup-analytics");

        const grid = document.getElementById("setups-grid");
        grid.innerHTML = "";

        const items = Array.isArray(setups) ? setups : setups.items || [];

        items.forEach(s => {
            const totalPnl =
                (s.profit_tp1_tp2_usdt || 0) +
                (s.profit_tp1_sl_usdt || 0) +
                (s.loss_sl_usdt || 0);

            const card = document.createElement("div");
            card.className = "setup-card";
            card.innerHTML = `
                <h3>${s.setup}</h3>
                <p>Сделок: ${s.total_trades}</p>
                <p>PnL: ${totalPnl.toFixed(2)}</p>
                <p>TP1+TP2: ${s.tp1_tp2_count}</p>
                <p>TP1+SL: ${s.tp1_sl_count}</p>
                <p>SL-only: ${s.sl_only_count}</p>
            `;
            card.onclick = () => window.location.href = `setup.html?name=${encodeURIComponent(s.setup)}`;
            grid.appendChild(card);
        });
    } catch (e) {
        console.error("Ошибка при загрузке сетапов:", e);
    }
}

async function loadTrades() {
    try {
        const trades = await window.apiGet("/trades");
        const list = document.getElementById("trades-list");
        list.innerHTML = "";

        trades.forEach(t => {
            const status = t.closed_at_ms ? "Закрыта" : "Открыта";

            const reason = t.close_reason || (
                t.tp1_hit && t.tp2_hit ? "TP1+TP2" :
                t.tp1_hit && t.sl_hit  ? "TP1+SL"  :
                t.sl_hit               ? "SL-only" :
                "—"
            );

            const positionValue = (t.size_usdt * t.entry_price).toFixed(2);

            const card = document.createElement("div");
            card.className = "trade-card";
            card.innerHTML = `
                <b>${t.symbol}</b> | ${t.setup}<br>
                Кол-во: ${t.size_usdt}<br>
                Цена входа: ${t.entry_price}<br>
                Стоимость позиции: ${positionValue}<br>
                TP1: ${t.tp1_price}<br>
                TP2: ${t.tp2_price}<br>
                SL: ${t.sl_price}<br>
                Статус: ${status}<br>
                Основание закрытия: ${reason}
            `;
            list.appendChild(card);
        });
    } catch (e) {
        console.error("Ошибка при загрузке сделок:", e);
    }
}


// Инициализация после загрузки DOM
window.addEventListener("DOMContentLoaded", () => {
    loadInitialInfo();
    loadClosedStats();
    loadSetups();
    loadTrades();
});
