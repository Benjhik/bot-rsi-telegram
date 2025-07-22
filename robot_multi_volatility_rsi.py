import websocket
import json
import time
import threading
import pandas as pd
import requests
from datetime import datetime

# === CONFIGURATION ===
DERIV_API_TOKEN = "Zr835xahVCQH9jh"
TELEGRAM_BOT_TOKEN = "7691800437:AAHi4riJ_36kj_8uN3pucxBySgWRk3yY2FI"
TELEGRAM_USER_ID = "1248366985"
RSI_PERIOD = 14
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
INTERVAL_SECONDS = 900  # 15 minutes

SYMBOLS = [
    "R_10", "R_25", "R_50", "R_75", "R_100",
    "R_10_1s", "R_25_1s", "R_50_1s", "R_75_1s", "R_100_1s",
    "BOOM1000", "BOOM500", "CRASH1000", "CRASH500",
    "RB_100", "RB_1000", "JD_10", "JD_25", "JD_50", "JD_75", "JD_100", "STP"
]

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_USER_ID, "text": message}
    try:
        requests.post(url, data=data)
    except Exception as e:
        print("Telegram error:", e)

def calculate_rsi(prices, period=RSI_PERIOD):
    delta = prices.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_macd(prices):
    fast_ema = prices.ewm(span=MACD_FAST, adjust=False).mean()
    slow_ema = prices.ewm(span=MACD_SLOW, adjust=False).mean()
    macd = fast_ema - slow_ema
    signal = macd.ewm(span=MACD_SIGNAL, adjust=False).mean()
    return macd, signal

def determine_order_type(signal, current_price, tp):
    if signal == "BUY":
        return "Buy Stop" if current_price < tp else "Buy Limit"
    elif signal == "SELL":
        return "Sell Stop" if current_price > tp else "Sell Limit"
    return "Market Execution"

def analyse_symbol(symbol):
    try:
        print(f"🌐 Connexion WebSocket à Deriv pour {symbol}...")
        ws = websocket.create_connection("wss://ws.derivws.com/websockets/v3?app_id=1089")
        print(f"✅ WebSocket ouverte pour {symbol}")
        
        ws.send(json.dumps({
            "ticks_history": symbol,
            "adjust_start_time": 1,
            "count": 100,
            "end": "latest",
            "start": 1,
            "style": "candles",
            "granularity": 300,
            "req_id": symbol
        }))

        response_raw = ws.recv()
        ws.close()
        print(f"📩 Donnée reçue pour {symbol}")

        response = json.loads(response_raw)

        if "candles" not in response:
            send_telegram(f"⚠️ Aucune donnée reçue pour {symbol}.")
            print(f"⚠️ Aucune donnée valide pour {symbol}")
            return None

        df = pd.DataFrame(response["candles"])
        df["close"] = pd.to_numeric(df["close"])
        df["high"] = pd.to_numeric(df["high"])
        df["low"] = pd.to_numeric(df["low"])
        df["epoch"] = pd.to_datetime(df["epoch"], unit="s")
        df.set_index("epoch", inplace=True)

        rsi = calculate_rsi(df["close"])
        macd, signal_line = calculate_macd(df["close"])

        if len(rsi) < RSI_PERIOD or len(macd) < MACD_SLOW:
            print(f"⚠️ Pas assez de données pour {symbol}")
            return None

        last_price = df["close"].iloc[-1]
        last_rsi = rsi.iloc[-1]
        last_macd = macd.iloc[-1]
        last_signal = signal_line.iloc[-1]

        if last_rsi < 30 and last_macd > last_signal:
            signal_type = "BUY"
        elif last_rsi > 70 and last_macd < last_signal:
            signal_type = "SELL"
        else:
            return None

        atr = df["high"].rolling(14).max() - df["low"].rolling(14).min()
        sl = round(atr.iloc[-1] / 2, 2)
        tp = round(atr.iloc[-1], 2)

        sl_price = round(last_price - sl if signal_type == "BUY" else last_price + sl, 2)
        tp_price = round(last_price + tp if signal_type == "BUY" else last_price - tp, 2)
        order_type = determine_order_type(signal_type, last_price, tp_price)
        entry_time = datetime.now().strftime("%Hh%Mmin")

        return f"""📊 {symbol}
🎯 Prix actuel : {round(last_price, 2)}
📈 Signal : {signal_type}
🕒 Heure conseillée : {entry_time}
🛠 Type d'ordre : {order_type}
💰 TP : {tp_price} | 🛑 SL : {sl_price}"""

    except Exception as e:
        error_msg = f"❌ Erreur WebSocket pour {symbol} : {e}"
        print(error_msg)
        send_telegram(error_msg)
        return None

def analyse_all():
    send_telegram("🤖 Analyse en cours de tous les indices Deriv...")
    for symbol in SYMBOLS:
        result = analyse_symbol(symbol)
        if result:
            send_telegram(result)

def loop():
    while True:
        analyse_all()
        time.sleep(INTERVAL_SECONDS)

# Lancement
print("🟢 DÉMARRAGE DU SCRIPT")
threading.Thread(target=loop).start()
