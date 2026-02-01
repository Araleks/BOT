from handlers.paper_trading import PaperTradingEngine

engine = PaperTradingEngine(exchange=None)
engine.completed_trades = []  # или подставь реальные сделки
engine.save_trades_to_json()
