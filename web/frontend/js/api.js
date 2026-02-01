// web/frontend/js/api.js

const API_BASE = "http://localhost:8080"; // если у тебя другой порт — поправь здесь

async function apiGet(path) {
    const url = `${API_BASE}${path}`;
    const res = await fetch(url);

    if (!res.ok) {
        throw new Error(`API error ${res.status} for ${url}`);
    }

    return res.json();
}

// Делаем функции глобальными, чтобы index.js и setup.js могли их вызывать
window.apiGet = apiGet;
