import websocket
import json
import pandas as pd
import requests
import threading
import time
from datetime import datetime

# === CONFIGURATION ===
TELEGRAM_BOT_TOKEN = "7691800437:AAHi4riJ_36kj_8uN3pucxBySgWRk3yY2FI"
TELEGRAM_CHAT_ID = "1248366985"
DERIV_API_URL = "wss://ws.deriv.com/websockets/v3"
SYMBOLS = [
    "R_10", "R_25", "R_50", "R_75", "R_100",
    "R_10_1s", "R_25_1s", "R_50_1s", "R_75_1s", "R_100_1s",
    "BOOM1000", "BOOM500", "CRASH1000", "CRASH500",
    "RB100", "RB1000", "STEPINDEX", "JD10", "JD25", "JD50", "JD75", "JD100",
    "XAUUSD"
]

INTERVAL = 60  # 1 minute
RSI_PERIOD = 14
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": message})

def get_price_history(symbol):
    try:
        ws = websocket.create_connection(DERIV_API_URL)
        payload = {
            "ticks_history": symbol,
            "adjust_start_time": 1,
            "count": 100,
            "end": "latest",
            "start": 1,
            "style": "candles",
            "granularity": 60
        }
        ws.send(json.dumps(payload))
        response = json.loads(ws.recv())
        ws.close()

        candles = response.get("candles", [])
        if not candles:
            return None

        df = pd.DataFrame(candles)
        df['time'] = pd.to_datetime(df['epoch'], unit='s')
        df.set_index('time', inplace=True)
        return df
    except Exception as e:
        print(f"Erreur WebSocket {symbol}:", e)
        return None

def calculate_indicators(df):
    close = df['close']
    delta = close.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(RSI_PERIOD).mean()
    avg_loss = loss.rolling(RSI_PERIOD).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    macd_line = close.ewm(span=MACD_FAST, adjust=False).mean() - close.ewm(span=MACD_SLOW, adjust=False).mean()
    signal_line = macd_line.ewm(span=MACD_SIGNAL, adjust=False).mean()

    return rsi, macd_line, signal_line

def determine_order_type(signal, price, sl, tp):
    if signal == "BUY":
        return "Buy Stop" if price < tp else "Buy Limit"
    elif signal == "SELL":
        return "Sell Stop" if price > tp else "Sell Limit"
    return "Market"

def analyze_symbol(symbol):
    df = get_price_history(symbol)
    if df is None or len(df) < MACD_SLOW:
        return

    rsi, macd, signal = calculate_indicators(df)
    current_price = round(df['close'].iloc[-1], 2)
    rsi_val = rsi.iloc[-1]
    macd_val = macd.iloc[-1]
    signal_val = signal.iloc[-1]

    if pd.isna(rsi_val) or pd.isna(macd_val) or pd.isna(signal_val):
        return

    direction = None
    if rsi_val < 30 and macd_val > signal_val:
        direction = "BUY"
    elif rsi_val > 70 and macd_val < signal_val:
        direction = "SELL"

    if direction:
        atr = (df['high'].rolling(14).max() - df['low'].rolling(14).min()).iloc[-1]
        sl = round(atr / 2, 2)
        tp = round(atr, 2)

        stop_loss = round(current_price - sl if direction == "BUY" else current_price + sl, 2)
        take_profit = round(current_price + tp if direction == "BUY" else current_price - tp, 2)
        order_type = determine_order_type(direction, current_price, sl, tp)

        confidence = estimate_confidence(rsi_val, macd_val, signal_val)

        now = datetime.utcnow().strftime('%Hh%Mmin')
        message = (
            f"📊 {symbol}\n"
            f"💵 Prix : {current_price}\n"
            f"📈 Signal : {direction}\n"
            f"⏰ Heure conseillée : {now}\n"
            f"🛠 Ordre : {order_type}\n"
            f"🎯 TP : {take_profit} | 🛑 SL : {stop_loss}\n"
            f"📊 Confiance : {confidence}%"
        )
        send_telegram_message(message)

def estimate_confidence(rsi, macd, signal):
    base = 50
    if rsi < 25 or rsi > 75:
        base += 15
    if abs(macd - signal) > 0.1:
        base += 10
    return min(base, 95)

def run_bot():
    send_telegram_message("🤖 Le robot WebSocket est lancé et analyse toutes les minutes.")
    while True:
        for symbol in SYMBOLS:
            analyze_symbol(symbol)
        time.sleep(INTERVAL)

# === DÉMARRAGE DANS THREAD SÉPARÉ ===
threading.Thread(target=run_bot).start()
