import os, threading, requests, time
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.environ.get("TOKEN")
ETHERSCAN_API = os.environ.get("ETHERSCAN_API")

app_flask = Flask(__name__)
@app_flask.route('/')
def home(): return "ONDO Bot running!"

CONTRACT = "0xfAbA6f8e4a5E8Ab82F62fe7C39859FA577269BE3"
SEEN_TXS = set()
LAST_PRICE = {"text": "", "time": 0, "price": 0}
PRICE_HISTORY = [] # lưu giá 15p để tính biến động

def get_price_ondo_raw():
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        r = requests.get("https://data-api.binance.vision/api/v3/ticker/price?symbol=ONDOUSDT", headers=headers, timeout=10).json()
        return float(r['price']), f"Binance"
    except:
        try:
            r = requests.get("https://min-api.cryptocompare.com/data/price?fsym=ONDO&tsyms=USD", headers=headers, timeout=10).json()
            return float(r['USD']), "CryptoCompare"
        except:
            r = requests.get("https://www.okx.com/api/v5/market/ticker?instId=ONDO-USDT", headers=headers, timeout=10).json()
            return float(r['data'][0]['last']), "OKX"

def get_price_ondo():
    now = time.time()
    if now - LAST_PRICE["time"] < 90 and LAST_PRICE["text"]:
        return LAST_PRICE["text"]
    try:
        price, source = get_price_ondo_raw()
        text = f"🔴 ONDO: ${price:.5f} ({source})"
        LAST_PRICE.update({"text": text, "time": now, "price": price})
        # Lưu lịch sử giá
        PRICE_HISTORY.append((now, price))
        # Chỉ giữ 2 tiếng gần nhất
        PRICE_HISTORY[:] = [(t,p) for t,p in PRICE_HISTORY if now - t < 7200]
        return text
    except Exception as e:
        return f"❌ Lỗi giá: {e}"

def get_price_change_15m():
    if len(PRICE_HISTORY) < 2: return 0
    now = time.time()
    # tìm giá cách đây ~15 phút
    old_price = None
    for t,p in reversed(PRICE_HISTORY):
        if now - t >= 900: # 15p
            old_price = p
            break
    if not old_price: old_price = PRICE_HISTORY[0][1]
    current = LAST_PRICE.get("price", old_price)
    if old_price == 0: return 0
    return (current - old_price) / old_price * 100

def get_ondo_signal():
    try:
        url = "https://www.okx.com/api/v5/market/candles?instId=ONDO-USDT&bar=1H&limit=100"
        r = requests.get(url, timeout=10).json()
        data = r['data'][::-1]
        closes = [float(x[4]) for x in data]
        price = closes[-1]
        gains = [max(closes[i]-closes[i-1],0) for i in range(1,len(closes))]
        losses = [max(closes[i-1]-closes[i],0) for i in range(1,len(closes))]
        avg_gain = sum(gains[-14:])/14
        avg_loss = sum(losses[-14:])/14 or 0.00001
        rsi = 100 - (100/(1+avg_gain/avg_loss))
        ema20 = sum(closes[-20:])/20
        ema50 = sum(closes[-50:])/50
        if rsi < 30: return f"📊 ONDO ${price:.4f} RSI:{rsi:.1f}\n🟢🟢 BUY MẠNH - Quá bán"
        elif rsi > 70: return f"📊 ONDO ${price:.4f} RSI:{rsi:.1f}\n🔴🔴 SELL MẠNH - Quá mua"
        elif ema20 > ema50: return f"📊 ONDO ${price:.4f} RSI:{rsi:.1f}\n🟢 BUY - EMA20>EMA50"
        else: return f"📊 ONDO ${price:.4f} RSI:{rsi:.1f}\n🔴 SELL/NEUTRAL - EMA20<EMA50"
    except Exception as e:
        return f"Lỗi tín hiệu: {e}"

def get_whales():
    try:
        url = f"https://api.etherscan.io/v2/api?chainid=1&module=account&action=tokentx&contractaddress={CONTRACT}&page=1&offset=20&sort=desc&apikey={ETHERSCAN_API}"
        r = requests.get(url, timeout=15).json()
        if r['status']!= '1': return None, f"Etherscan: {r.get('message')}"
        whales=[]
        for tx in r['result']:
            v = int(tx['value']) / 10**18
            if v >= 100000: whales.append(tx)
            if len(whales) >=5: break
        return whales, None
    except Exception as e:
        return None, str(e)

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("/price - giá\n/signal - tín hiệu\n/whale - cá voi >100k\n/auto_whale - bật auto cá voi kèm giá\n/auto_signal - bật auto tín hiệu")

async def price_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(get_price_ondo())

async def signal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(get_ondo_signal())

async def whale_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    whales, err = get_whales()
    if err: await update.message.reply_text(err); return
    if not whales: await update.message.reply_text("Chưa có giao dịch >100k"); return
    price_now = get_price_ondo()
    msg=f"{price_now}\n\n🐋 Cá voi ONDO >100k:\n\n"
    for tx in whales:
        v=int(tx['value'])/10**18
        msg+=f"💰 {v:,.0f} ONDO (~${v*LAST_PRICE.get('price',0.57):,.0f})\nhttps://etherscan.io/tx/{tx['hash']}\n\n"
    await update.message.reply_text(msg, disable_web_page_preview=True)

async def auto_whale_job(context: ContextTypes.DEFAULT_TYPE):
    whales, err = get_whales()
    if err or not whales: return
    for tx in whales:
        if tx['hash'] in SEEN_TXS: continue
        SEEN_TXS.add(tx['hash'])
        v=int(tx['value'])/10**18
        # Lấy giá lúc cá voi chuyển
        try:
            price_val, source = get_price_ondo_raw()
            usd_val = v * price_val
            change_15m = get_price_change_15m()
            trend = "🔺 Đang GOM" if change_15m > 0 else "🔻 Đang XẢ"
            if abs(change_15m) < 0.3: trend = "➡️ Đi ngang"

            msg = (f"🚨 CÁ VOI 100k+ ONDO!\n"
                   f"💰 {v:,.0f} ONDO (~${usd_val:,.0f})\n"
                   f"💵 Giá lúc chuyển: ${price_val:.5f} ({source})\n"
                   f"📊 Biến động 15p trước: {change_15m:+.2f}% {trend}\n"
                   f"https://etherscan.io/tx/{tx['hash']}")
            await context.bot.send_message(chat_id=context.job.chat_id, text=msg, disable_web_page_preview=True)
            # Cập nhật cache giá
            get_price_ondo()
        except Exception as e:
            print(f"whale job error {e}")

async def auto_signal_job(context: ContextTypes.DEFAULT_TYPE):
    sig = get_ondo_signal()
    if "MẠNH" in sig or "BREAKOUT" in sig:
        await context.bot.send_message(chat_id=context.job.chat_id, text=f"🚨 AUTO ONDO\n{sig}")

async def auto_whale_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id=update.effective_chat.id
    jobs=context.job_queue.get_jobs_by_name(f"whale_{chat_id}")
    if jobs:
        for j in jobs: j.schedule_removal()
        await update.message.reply_text("Đã TẮT auto cá voi")
        return
    context.job_queue.run_repeating(auto_whale_job, interval=300, first=5, chat_id=chat_id, name=f"whale_{chat_id}")
    await update.message.reply_text("Đã BẬT auto cá voi >100k kèm giá lúc chuyển + biến động 15p!")

async def auto_signal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id=update.effective_chat.id
    jobs=context.job_queue.get_jobs_by_name(f"sig_{chat_id}")
    if jobs:
        for j in jobs: j.schedule_removal()
        await update.message.reply_text("Đã TẮT auto tín hiệu")
        return
    context.job_queue.run_repeating(auto_signal_job, interval=900, first=5, chat_id=chat_id, name=f"sig_{chat_id}")
    await update.message.reply_text("Đã BẬT auto tín hiệu ONDO")

def run_flask():
    app_flask.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("price", price_cmd))
    app.add_handler(CommandHandler("signal", signal_cmd))
    app.add_handler(CommandHandler("whale", whale_cmd))
    app.add_handler(CommandHandler("auto_whale", auto_whale_cmd))
    app.add_handler(CommandHandler("auto_signal", auto_signal_cmd))
    print("ONDO Bot starting...")
    app.run_polling(stop_signals=None, close_loop=False)
