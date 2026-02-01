from models import Candle
from setup_manager import SetupManager
from setups import FallingStarSetup, HammerSetup, MaxVolumeZoneSetup, RSIZoneSetup
from falling_star_daemon import load_config, make_exchange


def main():
    cfg = load_config()
    exchange = make_exchange(cfg.exchange_id)

    setup_manager = SetupManager(
        setups=[
            FallingStarSetup(),
            HammerSetup(),
            MaxVolumeZoneSetup(exchange, cfg),
            RSIZoneSetup(exchange, cfg),
        ]
    )

    # тестовая свеча
    candle = Candle(
        symbol="BTC/USDT",
        timeframe="5m",
        t_close_ms=1700000000000,
        o=50000,
        h=50500,
        l=49500,
        c=49900,
    )

    signals = setup_manager.process_candle(candle)

    print("\n=== РЕЗУЛЬТАТЫ ТЕСТА ===")
    for sig in signals:
        print(sig)


if __name__ == "__main__":
    main()
