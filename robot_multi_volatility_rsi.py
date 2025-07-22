import websocket, json, time, threading, pandas as pd, requests
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
SYMBOLS = ["R_10", "R_25", "R_50", "R_75", "R_100", "R_10_1s", "R_25_1s",
           "R_50_1s", "R_75_1s", "R_100_1s", "BOOM1000", "BOOM500",
           "CRASH1000", "CRASH500", "RB_100", "RB_1000", "JD_10", "JD_25",
           "JD_50", "JD_75", "JD_100", "STP"]

def send_telegram(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                       data={"chat_id": TELEGRAM_USER_ID, "text": msg})
    except Exception as e:
        print("Telegram error:", e)

def calculate_rsi(prices):
    delta = prices.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    return 100 - (100 / (1 + (gain.rolling(RSI_PERIOD).mean() / loss.rolling(RSI_PERIOD).mean())))

def calculate_macd(prices):
    macd = prices.ewm(span=MACD_FAST, adjust=False).mean() - prices.ewm(span=MACD_SLOW, adjust=False).mean()
    signal = macd.ewm(span=MACD_SIGNAL, adjust=False).mean()
    return macd, signal

def analyse_symbol(symbol):
    try:
        ws = websocket.create_connection(f"wss://ws.derivws.com/websockets/v3?app_id=1089")
        ws.send(json.dumps({
            "ticks_history": symbol, "count":100, "end":"latest",
            "style":"candles", "granularity":300, "req_id":symbol
        }))
        raw = ws.recv()
        print(f"📥 RAW candles for {symbol}: {raw}")
        data = json.loads(raw)

        if "candles" in data and data["candles"]:
            df = pd.DataFrame(data["candles"])
            df["close"] = pd.to_numeric(df["close"])
        else:
            # fallback to ticks if no candles
            ws.send(json.dumps({
                "ticks_history": symbol, "count":500, "end":"latest", "style":"ticks", "req_id":symbol
            }))
            raw_ticks = ws.recv()
            print(f"📥 RAW ticks for {symbol}: {raw_ticks}")
            hist = json.loads(raw_ticks).get("history", {}).get("prices", [])
            if not hist:
                send_telegram(f"⚠️ Aucune donnée du tout pour {symbol}")
                return None
            df = pd.DataFrame({"close":[float(p) for p in hist]})

        ws.close()

        prices = df["close"]
        rsi = calculate_rsi(prices)
        macd, signal = calculate_macd(prices)
        if len(rsi)<RSI_PERIOD or len(macd)<MACD_SLOW: return None
        last_rsi = rsi.iloc[-1]; last_macd = macd.iloc[-1]; last_signal = signal.iloc[-1]
        print(f"{symbol} → RSI: {last_rsi:.2f}, MACD: {last_macd:.2f}, Signal: {last_signal:.2f}")

        if last_rsi<30 and last_macd>last_signal:
            signal_type = "BUY"
        elif last_rsi>70 and last_macd<last_signal:
            signal_type = "SELL"
        else:
            return None

        atr = df.get("high", prices).rolling(14).max() - df.get("low", prices).rolling(14).min()
        sl, tp = round(atr.iloc[-1]/2,2), round(atr.iloc[-1],2)
        lp = prices.iloc[-1]; slp = round(lp - sl if signal_type=="BUY" else lp+sl,2); tpp = round(lp+tp if signal_type=="BUY" else lp-tp,2)
        order_type = "Buy Stop" if signal_type=="BUY" else "Sell Stop"
        return (f"📊 {symbol}\n🎯 Prix : {lp}\n📈 Signal : {signal_type}\n"
                f"🕒 {datetime.utcnow().strftime('%Hh%Mmin')} UTC\n🛠 Ordre : {order_type}\n"
                f"💰 TP : {tpp} | 🛑 SL : {slp}")

    except Exception as e:
        err = f"❌ Erreur Deriv pour {symbol} : {e}"
        print(err)
        send_telegram(err)
        return None

def analyse_all():
    send_telegram("🤖 Analyse en cours…")
    for s in SYMBOLS:
        res = analyse_symbol(s)
        if res: send_telegram(res)

def loop():
    print("🟢 Bot démarré")
    while True:
        analyse_all()
        time.sleep(INTERVAL_SECONDS)

threading.Thread(target=loop, daemon=True).start()
