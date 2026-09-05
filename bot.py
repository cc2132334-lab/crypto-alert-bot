import os
import requests
from datetime import datetime, timezone

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

SYMBOLS = ["BTCUSDT", "ETHUSDT"]
TIMEFRAMES = ["5m", "15m"]
LOOKBACK = 20

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

def check_liquidity_sweep(symbol, timeframe):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={timeframe}&limit={LOOKBACK + 5}"
    try:
        res = requests.get(url, timeout=10)
        data = res.json()
    except Exception as e:
        print(f"Fetch error for {symbol} {timeframe}: {e}")
        return

    if not isinstance(data, list) or len(data) < LOOKBACK + 2:
        return

    closed_candle = data[-2]
    history_candles = data[-(LOOKBACK + 2):-2]

    candle_high = float(closed_candle[2])
    candle_low = float(closed_candle[3])
    candle_close = float(closed_candle[4])
    close_timestamp = closed_candle[6]

    swing_high = max(float(c[2]) for c in history_candles)
    swing_low = min(float(c[3]) for c in history_candles)

    utc_time = datetime.fromtimestamp(close_timestamp / 1000, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

    bullish_sweep = (candle_low < swing_low) and (candle_close > swing_low)
    bearish_sweep = (candle_high > swing_high) and (candle_close < swing_high)

    dec = 2

    if bullish_sweep:
        entry = candle_close
        sl = candle_low * 0.9995
        risk = entry - sl
        tp1 = entry + (risk * 2.0)
        tp2 = max(entry + (risk * 3.0), swing_high)

        msg = (
            f"🟢 *[BUY / LONG SIGNAL DETECTED]*\n\n"
            f"• *Asset:* `{symbol}`\n"
            f"• *Timeframe:* `{timeframe}`\n"
            f"• *Time:* `{utc_time} UTC`\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 *Entry Zone:* `${entry:,.{dec}f}` (Retest to `${swing_low:,.{dec}f}`)\n"
            f"🛑 *Stop-Loss (SL):* `${sl:,.{dec}f}`\n"
            f"🚀 *Target 1 (1:2 RR):* `${tp1:,.{dec}f}`\n"
            f"🚀 *Target 2 (1:3 / Swing High):* `${tp2:,.{dec}f}`\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 *Risk per Unit:* `${risk:,.{dec}f}`\n"
            f"💡 *Setup:* Bullish Sweep of `${swing_low:,.{dec}f}` Low"
        )
        send_telegram_alert(msg)
        print(f"Sent Buy Alert: {symbol} {timeframe}")

    elif bearish_sweep:
        entry = candle_close
        sl = candle_high * 1.0005
        risk = sl - entry
        tp1 = entry - (risk * 2.0)
        tp2 = min(entry - (risk * 3.0), swing_low)

        msg = (
            f"🔴 *[SELL / SHORT SIGNAL DETECTED]*\n\n"
            f"• *Asset:* `{symbol}`\n"
            f"• *Timeframe:* `{timeframe}`\n"
            f"• *Time:* `{utc_time} UTC`\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 *Entry Zone:* `${entry:,.{dec}f}` (Retest to `${swing_high:,.{dec}f}`)\n"
            f"🛑 *Stop-Loss (SL):* `${sl:,.{dec}f}`\n"
            f"🚀 *Target 1 (1:2 RR):* `${tp1:,.{dec}f}`\n"
            f"🚀 *Target 2 (1:3 / Swing Low):* `${tp2:,.{dec}f}`\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 *Risk per Unit:* `${risk:,.{dec}f}`\n"
            f"💡 *Setup:* Bearish Sweep of `${swing_high:,.{dec}f}` High"
        )
        send_telegram_alert(msg)
        print(f"Sent Sell Alert: {symbol} {timeframe}")

def main():
    for symbol in SYMBOLS:
        for tf in TIMEFRAMES:
            check_liquidity_sweep(symbol, tf)

if __name__ == "__main__":
    main()
