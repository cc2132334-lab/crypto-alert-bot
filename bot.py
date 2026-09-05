import os
import time
import requests
from datetime import datetime, timezone

# GitHub Secrets se credentials aayenge
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Delta Exchange India / Global base URL
# Agar Delta Global use kar rahe hain to "https://api.delta.exchange" use karein
DELTA_BASE_URL = "https://api.india.delta.exchange"

# Delta Exchange Symbols (Perpetual Futures)
SYMBOLS = ["BTCUSD", "ETHUSD"]

# Timeframes
TIMEFRAMES = {
    "5m": 300,   # 5 minute = 300 seconds
    "15m": 900   # 15 minute = 900 seconds
}

LOOKBACK = 20  # Swing high/low track karne ke liye candles

def send_telegram_alert(message):
    if not BOT_TOKEN or not CHAT_ID:
        print("Telegram credentials missing!")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")

def check_delta_liquidity_sweep(symbol, timeframe, tf_seconds):
    # Delta Exchange requires UNIX timestamps in seconds
    end_time = int(time.time())
    start_time = end_time - ((LOOKBACK + 10) * tf_seconds)

    url = f"{DELTA_BASE_URL}/v2/history/candles"
    params = {
        "symbol": symbol,
        "resolution": timeframe,
        "start": start_time,
        "end": end_time
    }
    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0"
    }

    try:
        res = requests.get(url, params=params, headers=headers, timeout=10)
        data = res.json()
    except Exception as e:
        print(f"Fetch error for {symbol} {timeframe}: {e}")
        return

    # Response validation
    if not data or "result" not in data or not isinstance(data["result"], list):
        return

    candles_raw = data["result"]
    if len(candles_raw) < LOOKBACK + 2:
        return

    # Delta API candles reverse order me deta he, isliye chronologically sort karein
    candles = sorted(candles_raw, key=lambda x: x["time"])

    # Index -1: Running (incomplete) candle, Index -2: Just closed candle
    closed_candle = candles[-2]
    history_candles = candles[-(LOOKBACK + 2):-2]

    candle_high = float(closed_candle["high"])
    candle_low = float(closed_candle["low"])
    candle_close = float(closed_candle["close"])
    
    # Candle close timestamp (in seconds)
    close_timestamp = closed_candle["time"] + tf_seconds

    # Swing high aur swing low calculate karein
    swing_high = max(float(c["high"]) for c in history_candles)
    swing_low = min(float(c["low"]) for c in history_candles)

    # UTC Time formatting
    utc_time = datetime.fromtimestamp(close_timestamp, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

    # Sweep Conditions
    bullish_sweep = (candle_low < swing_low) and (candle_close > swing_low)
    bearish_sweep = (candle_high > swing_high) and (candle_close < swing_high)

    dec = 2

    # --- BUY / LONG ALERT ---
    if bullish_sweep:
        entry = candle_close
        sl = candle_low * 0.9995  # 0.05% safety buffer
        risk = entry - sl
        tp1 = entry + (risk * 2.0)
        tp2 = max(entry + (risk * 3.0), swing_high)

        msg = (
            f"🟢 *[DELTA EXCHANGE: BUY / LONG SIGNAL]*\n\n"
            f"• *Exchange:* `Delta Exchange`\n"
            f"• *Symbol:* `{symbol}`\n"
            f"• *Timeframe:* `{timeframe}`\n"
            f"• *Closed Time:* `{utc_time} UTC`\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 *Entry Zone:* `${entry:,.{dec}f}` (Retest to `${swing_low:,.{dec}f}`)\n"
            f"🛑 *Stop-Loss (SL):* `${sl:,.{dec}f}`\n"
            f"🚀 *Target 1 (1:2 RR):* `${tp1:,.{dec}f}`\n"
            f"🚀 *Target 2 (1:3 / Swing High):* `${tp2:,.{dec}f}`\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 *Risk per Contract:* `${risk:,.{dec}f}`\n"
            f"💡 *Setup:* Bullish Sweep of `${swing_low:,.{dec}f}` Low"
        )
        send_telegram_alert(msg)
        print(f"Sent Buy Alert: {symbol} {timeframe}")

    # --- SELL / SHORT ALERT ---
    elif bearish_sweep:
        entry = candle_close
        sl = candle_high * 1.0005  # 0.05% safety buffer
        risk = sl - entry
        tp1 = entry - (risk * 2.0)
        tp2 = min(entry - (risk * 3.0), swing_low)

        msg = (
            f"🔴 *[DELTA EXCHANGE: SELL / SHORT SIGNAL]*\n\n"
            f"• *Exchange:* `Delta Exchange`\n"
            f"• *Symbol:* `{symbol}`\n"
            f"• *Timeframe:* `{timeframe}`\n"
            f"• *Closed Time:* `{utc_time} UTC`\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 *Entry Zone:* `${entry:,.{dec}f}` (Retest to `${swing_high:,.{dec}f}`)\n"
            f"🛑 *Stop-Loss (SL):* `${sl:,.{dec}f}`\n"
            f"🚀 *Target 1 (1:2 RR):* `${tp1:,.{dec}f}`\n"
            f"🚀 *Target 2 (1:3 / Swing Low):* `${tp2:,.{dec}f}`\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 *Risk per Contract:* `${risk:,.{dec}f}`\n"
            f"💡 *Setup:* Bearish Sweep of `${swing_high:,.{dec}f}` High"
        )
        send_telegram_alert(msg)
        print(f"Sent Sell Alert: {symbol} {timeframe}")

def main():
    print("Checking Delta Exchange for Liquidity Sweeps...")
    for symbol in SYMBOLS:
        for tf, tf_seconds in TIMEFRAMES.items():
            check_delta_liquidity_sweep(symbol, tf, tf_seconds)

if __name__ == "__main__":
    main()

