import os
import time
import requests
from datetime import datetime, timezone

# GitHub Secrets
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Delta Exchange URL & Symbols
DELTA_BASE_URL = "https://api.india.delta.exchange"
SYMBOLS = ["BTCUSD", "ETHUSD"]

# Timeframes
TIMEFRAMES = {
    "5m": 300,
    "15m": 900
}

LOOKBACK = 20

# -------------------------------------------------------------
# Risk-to-Reward Ratios (Aap apni pasand se adjust kar sakte hain)
# -------------------------------------------------------------
RR_RATIOS = [1.5, 2.0, 3.0]  # TP1: 1:1.5 | TP2: 1:2.0 | TP3: 1:3.0

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

    if not data or "result" not in data or not isinstance(data["result"], list):
        return

    candles_raw = data["result"]
    if len(candles_raw) < LOOKBACK + 2:
        return

    # Chronological sort (oldest to newest)
    candles = sorted(candles_raw, key=lambda x: x["time"])

    closed_candle = candles[-2]
    history_candles = candles[-(LOOKBACK + 2):-2]

    candle_high = float(closed_candle["high"])
    candle_low = float(closed_candle["low"])
    candle_close = float(closed_candle["close"])
    close_timestamp = closed_candle["time"] + tf_seconds

    swing_high = max(float(c["high"]) for c in history_candles)
    swing_low = min(float(c["low"]) for c in history_candles)

    utc_time = datetime.fromtimestamp(close_timestamp, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

    bullish_sweep = (candle_low < swing_low) and (candle_close > swing_low)
    bearish_sweep = (candle_high > swing_high) and (candle_close < swing_high)

    dec = 2

    # --- BUY / LONG SETUP ---
    if bullish_sweep:
        entry = candle_close
        sl = candle_low * 0.9995  # 0.05% safety buffer
        sl_points = entry - sl     # Total SL Points

        # Take-Profit levels based on SL points
        tp_text = ""
        for i, rr in enumerate(RR_RATIOS, 1):
            target_gain_points = sl_points * rr
            tp_price = entry + target_gain_points
            tp_text += f"🎯 *TP {i} (1:{rr} RR):* `${tp_price:,.{dec}f}` `(+{target_gain_points:,.{dec}f} pts)`\n"

        msg = (
            f"🟢 *[DELTA EXCHANGE: BUY / LONG SETUP]*\n\n"
            f"• *Symbol:* `{symbol}`\n"
            f"• *Timeframe:* `{timeframe}`\n"
            f"• *Closed Time:* `{utc_time} UTC`\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📍 *Entry Price:* `${entry:,.{dec}f}`\n"
            f"🛑 *Stop-Loss (SL):* `${sl:,.{dec}f}` `(-{sl_points:,.{dec}f} pts)`\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📈 *Targets by SL Points:*\n"
            f"{tp_text}"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 *Setup:* Sweep of `{swing_low:,.{dec}f}` Low"
        )
        send_telegram_alert(msg)
        print(f"Sent Buy Alert: {symbol} {timeframe}")

    # --- SELL / SHORT SETUP ---
    elif bearish_sweep:
        entry = candle_close
        sl = candle_high * 1.0005  # 0.05% safety buffer
        sl_points = sl - entry     # Total SL Points

        # Take-Profit levels based on SL points
        tp_text = ""
        for i, rr in enumerate(RR_RATIOS, 1):
            target_gain_points = sl_points * rr
            tp_price = entry - target_gain_points
            tp_text += f"🎯 *TP {i} (1:{rr} RR):* `${tp_price:,.{dec}f}` `(+{target_gain_points:,.{dec}f} pts)`\n"

        msg = (
            f"🔴 *[DELTA EXCHANGE: SELL / SHORT SETUP]*\n\n"
            f"• *Symbol:* `{symbol}`\n"
            f"• *Timeframe:* `{timeframe}`\n"
            f"• *Closed Time:* `{utc_time} UTC`\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📍 *Entry Price:* `${entry:,.{dec}f}`\n"
            f"🛑 *Stop-Loss (SL):* `${sl:,.{dec}f}` `(-{sl_points:,.{dec}f} pts)`\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📉 *Targets by SL Points:*\n"
            f"{tp_text}"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 *Setup:* Sweep of `{swing_high:,.{dec}f}` High"
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

