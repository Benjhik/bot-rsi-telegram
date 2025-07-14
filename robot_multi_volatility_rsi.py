import os
import websocket
import json
import requests
import threading
import time
import datetime

# === CONFIGURATION ===
DERIV_API_TOKEN = os.getenv("DERIV_API_TOKEN")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_USER_ID = os.getenv("TELEGRAM_USER_ID")
RSI_PERIOD = 14
ANALYSE_INTERVAL = 900

SYMBOLS = [
    "R_10", "R_25", "R_50", "R_75", "R_100",
    "R_10_1s", "R_25_1s", "R_50_1s", "R_75_1s", "R_100_1s"
]

price_data = {symbol: [] for symbol in SYMBOLS}

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_USER_ID, "text": message}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print(f"Erreur Telegram : {e}")

def calculate_rsi(prices, period=14):
    if len(prices) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, period + 1):
        delta = prices[-i] - prices[-i - 1]
        gains.append(max(delta, 0))
        losses.append(-min(delta, 0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)

def get_trend(prices):
    if len(prices) < 5:
        return "Indéterminée"
    return "📈 Hausse" if prices[-1] > prices[-5] else "📉 Baisse"

def handle_tick(symbol, price):
    price_data[symbol].append(price)
    if len(price_data[symbol]) > RSI_PERIOD + 1:
        rsi = calculate_rsi(price_data[symbol])
        trend = get_trend(price_data[symbol])
        heure = datetime.datetime.now().strftime("%H:%M:%S")

        message = f"""📊 *{symbol}*
🕒 {heure}
💰 Prix actuel : {price}
📈 RSI : {rsi}
📉 Tendance : {trend}
"""
        send_telegram_message(message)

        if rsi is not None:
            if rsi < 30:
                send_telegram_message(f"✅ *SIGNAL D'ACHAT* - {symbol}
RSI = {rsi}
Prix = {price}")
            elif rsi > 70:
                send_telegram_message(f"⚠️ *SIGNAL DE VENTE* - {symbol}
RSI = {rsi}
Prix = {price}")

    if len(price_data[symbol]) > 100:
        price_data[symbol] = price_data[symbol][-100:]

def periodic_analysis():
    while True:
        time.sleep(ANALYSE_INTERVAL)
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        for symbol in SYMBOLS:
            rsi = calculate_rsi(price_data[symbol])
            trend = get_trend(price_data[symbol])
            if rsi is not None and price_data[symbol]:
                last_price = price_data[symbol][-1]
                message = f"""🔄 *Analyse Périodique*
📊 {symbol}
🕒 {now}
💰 Prix : {last_price}
📈 RSI : {rsi}
📉 Tendance : {trend}
"""
                send_telegram_message(message)

def start_symbol_ws(symbol):
    def on_message(ws, message):
        data = json.loads(message)
        if "tick" in data:
            price = float(data["tick"]["quote"])
            handle_tick(symbol, price)

    def on_open(ws):
        ws.send(json.dumps({"authorize": DERIV_API_TOKEN}))

    def on_authorized(ws):
        ws.send(json.dumps({"ticks_subscribe": symbol}))

    def on_message_with_auth(ws, message):
        data = json.loads(message)
        if data.get("msg_type") == "authorize":
            print(f"✅ Autorisé : {symbol}")
            on_authorized(ws)
        else:
            on_message(ws, message)

    ws = websocket.WebSocketApp(
        "wss://ws.deriv.com/websockets/v3",
        on_message=on_message_with_auth,
        on_open=on_open
    )
    ws.run_forever()

send_telegram_message("🚀 Le robot RSI multi-volatility a démarré avec succès !")
threading.Thread(target=periodic_analysis, daemon=True).start()

for symbol in SYMBOLS:
    threading.Thread(target=start_symbol_ws, args=(symbol,), daemon=True).start()
    time.sleep(1)

while True:
    time.sleep(60)
