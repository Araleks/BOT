#C:\DM\BOT_FS\web\backend\app\main.py
from fastapi import FastAPI, Query
from typing import List, Optional

from fastapi.middleware.cors import CORSMiddleware

from .repository import load_trades
from .services import (
    calculate_stats,
    build_equity,
    get_setups,
    calculate_setup_analytics,
    calculate_setup_symbol_analytics,
)
from .models import (
    CompletedTrade,
    StatsResponse,
    EquityResponse,
    SetupsResponse,
    SetupAnalyticsResponse,
    SetupSymbolAnalyticsResponse,
)

app = FastAPI(
    title="Paper Trading Analytics API",
    version="1.0.0",
    debug=True,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/trades", response_model=List[CompletedTrade])
def api_trades():
    return load_trades()

@app.get("/stats", response_model=StatsResponse)
def api_stats():
    trades = load_trades()
    return calculate_stats(trades)

@app.get("/equity", response_model=EquityResponse)
def api_equity(setup: Optional[str] = Query(default=None)):
    trades = load_trades()
    return build_equity(trades, setup)

@app.get("/setups", response_model=SetupsResponse)
def api_setups():
    trades = load_trades()
    return SetupsResponse(setups=get_setups(trades))

@app.get("/setup-analytics", response_model=SetupAnalyticsResponse)
def api_setup_analytics():
    trades = load_trades()
    return calculate_setup_analytics(trades)

@app.get("/setup-analytics/by-symbol", response_model=SetupSymbolAnalyticsResponse)
def api_setup_symbol_analytics():
    trades = load_trades()
    return calculate_setup_symbol_analytics(trades)
