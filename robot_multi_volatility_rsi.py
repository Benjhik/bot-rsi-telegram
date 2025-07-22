import websocket
import json
import pandas as pd
import time
import datetime
import threading
import requests

# === CONFIGURATION ===
DERIV_SYMBOLS = [
    "R_10", "R_25", "R_50", "R_75", "R_100",
    "R_10_1s", "R_25_1s", "R_50_1s", "R_75_1s", "R_100_1s"
]

RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

TELEGRAM_BOT_TOKEN = "7691800437:AAHi4riJ_36kj_8uN3pucxBySgWRk3yY2FI"
TELEGRAM_CHAT_ID = "1248366985"

TP_POINTS = 200
SL_POINTS = 100

# === FONCTIONS UTILITAIRES ===
def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        response = requests.post(url, data=data)
        print(f"✅ Message Telegram envoyé : {response.status_code}")
    except Exception as e:
        print("Erreur Telegram:", e)

def calculate_rsi(prices, period):
    delta = prices.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_macd(prices):
    ema_fast = prices.ewm(span=MACD_FAST, adjust=False).mean()
    ema_slow = prices.ewm(span=MACD_SLOW, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=MACD_SIGNAL, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def determine_signal(rsi, macd_line, signal_line):
    if rsi < RSI_OVERSOLD and macd_line.iloc[-1] > signal_line.iloc[-1]:
        return "BUY", "Buy Stop"
    elif rsi > RSI_OVERBOUGHT and macd_line.iloc[-1] < signal_line.iloc[-1]:
        return "SELL", "Sell Stop"
    return None, None

def analyze_symbol(symbol):
    try:
        ws = websocket.create_connection("wss://ws.derivws.com/websockets/v3?app_id=1089")
        ws.send(json.dumps({
            "ticks_history": symbol,
            "count": 500,
            "end": "latest",
            "style": "ticks",
            "subscribe": 0,
            "req_id": symbol
        }))

        data = json.loads(ws.recv())
        ws.close()

        prices_raw = data.get("history", {}).get("prices", [])
        if len(prices_raw) < RSI_PERIOD:
            print(f"⚠️ Pas assez de données pour {symbol}")
            return

        prices = pd.Series([float(p) for p in prices_raw])
        rsi_series = calculate_rsi(prices, RSI_PERIOD)
        macd_line, signal_line, histogram = calculate_macd(prices)

        signal, order_type = determine_signal(rsi_series.iloc[-1], macd_line, signal_line)
        if signal:
            price = prices.iloc[-1]
            sl = round(price - SL_POINTS if signal == "BUY" else price + SL_POINTS, 2)
            tp = round(price + TP_POINTS if signal == "BUY" else price - TP_POINTS, 2)
            now = datetime.datetime.utcnow()
            message = f"""📊 {symbol}
Prix : {price}
Signal : {signal}
Heure : {now.strftime('%H:%M')} (UTC)
Ordre : {order_type}
SL : {sl} | TP : {tp}"""
            send_telegram_message(message)
    except Exception as e:
        print(f"⛔ Erreur lors de l'analyse de {symbol} :", e)

def scheduled_analysis():
    print("🟢 SCRIPT LANCÉ")
    while True:
        print("🚀 Nouvelle itération d'analyse")
        for symbol in DERIV_SYMBOLS:
            threading.Thread(target=analyze_symbol, args=(symbol,), daemon=True).start()
        time.sleep(900)  # 15 minutes

if __name__ == "__main__":
    send_telegram_message("🚀 Le robot RSI + MACD multi-volatility a démarré avec succès !")
    scheduled_analysis()
