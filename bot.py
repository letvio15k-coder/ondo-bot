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
LAST_PRICE = {"text": "", "time": 0}

# --- LẤY GIÁ ONDO - 4 NGUỒN CHỐNG LỖI ---
def get_price_ondo():
    now = time.time()
    if now - LAST_PRICE["time"] < 90 and LAST_PRICE["text"]:
        return LAST_PRICE["text"] + " (cache 90s)"

    headers = {'User-Agent': 'Mozilla/5.0'}
    result = None

    try:
        url = "https://data-api.binance.vision/api/v3/ticker/price?symbol=ONDOUSDT"
        r = requests.get(url, headers=headers, timeout=10).json()
        if 'price' in r:
            result = f"🔴 ONDO: ${float(r['price']):.5f} (Binance)"
    except: pass

    if not result:
        try:
            url = "https://min-api.cryptocompare.com/data/price?fsym=ONDO&tsyms=USD"
            r = requests.get(url, headers=headers, timeout=10).json()
            result = f"🔴 ONDO: ${r['USD']} (CryptoCompare)"
        except: pass

    if not result:
        try:
            url = "https://www.okx.com/api/v5/market/ticker?instId=ONDO-USDT"
            r = requests.get(url, headers=headers, timeout=10).json()
            result = f"🔴 ONDO: ${r['data'][0]['last']} (OKX)"
        except: pass

    if not result:
        try:
            url = "https://api.coingecko.com/api/v3/simple/price?ids=ondo-finance&vs_currencies=usd"
            r = requests.get(url, headers=headers, timeout=10).json()
            result = f"🔴 ONDO: ${r['ondo-finance']['usd']} (CoinGecko)"
        except Exception as e:
            return f"❌ Lỗi lấy giá ONDO: {e}"

    LAST_PRICE["text"] = result
    LAST_PRICE["time"] = now
    return result

# --- TÍNH TÍN HIỆU RSI + BREAKOUT CHO ONDO ---
def get_ondo_signal():
    try:
        url = "https://www.okx.com/api/v5/market/candles?instId=ONDO-USDT&bar=1H&limit=100"
        r = requests.get(url, timeout=10).json()
        data = r['data'][::-1]
        closes = [float(x[4]) for x in data]
        highs = [float(x[2]) for x in data]
        lows = [float(x[3]) for x in data]
        vols = [float(x[5]) for x in data]
        price = closes[-1]

        # RSI 14
        gains = [max(closes[i]-closes[i-1],0) for i in range(1,len(closes))]
        losses = [max(closes[i-1]-closes[i],0) for i in range(1,len(closes))]
        avg_gain = sum(gains[-14:])/14
        avg_loss = sum(losses[-14:])/14 or 0.00001
        rsi = 100 - (100/(1+avg_gain/avg_loss))

        ema20 = sum(closes[-20:])/20
        ema50 = sum(closes[-50:])/50
        highest_20 = max(highs[-21:-1])
        lowest_20 = min(lows[-21:-1])
        avg_vol = sum(vols[-21:-1])/20 or 1
        vol_spike = vols[-1] > avg_vol * 1.5

        if price > highest_20 and vol_spike:
            return f"📊 ONDO ${price:.4f}\nRSI:{rsi:.1f}\n🚀 BREAKOUT BUY - Phá đỉnh 20H ${highest_20:.4f} + Vol tăng"
        elif price < lowest_20 and vol_spike:
            return f"📊 ONDO ${price:.4f}\nRSI:{rsi:.1f}\n💥 BREAKDOWN SELL - Phá đáy 20H ${lowest_20:.4f}"
        elif rsi < 30:
            return f"📊 ONDO ${price:.4f}\nRSI:{rsi:.1f}\n🟢🟢 BUY MẠNH - RSI quá bán"
        elif rsi > 70:
            return f"📊 ONDO ${price:.4f}\nRSI:{rsi:.1f}\n🔴🔴 SELL MẠNH - RSI quá mua"
        elif ema20 > ema50:
            return f"📊 ONDO ${price:.4f}\nRSI:{rsi:.1f} EMA20>{50}\n🟢 BUY - Xu hướng tăng"
        else:
            return f"📊 ONDO ${price:.4f}\nRSI:{rsi:.1f} EMA20<{50}\n🔴 SELL - Xu hướng giảm / NEUTRAL"
    except Exception as e:
        return f"Lỗi tín hiệu: {e}"

def get_whales():
    try:
        url = f"https://api.etherscan.io/v2/api?chainid=1&module=account&action=tokentx&contractaddress={CONTRACT}&page=1&offset=20&sort=desc&apikey={ETHERSCAN_API}"
        r = requests.get(url, timeout=15).json()
        if r['status']!= '1': return None, f"Etherscan: {r.get('message')} {r.get('result')}"
        whales=[]
        for tx in r['result']:
            v = int(tx['value']) / 10**int(tx.get('tokenDecimal','18'))
            if v >= 100000: whales.append(tx)
            if len(whales) >=5: break
        return whales, None
    except Exception as e:
        return None, str(e)

# --- LỆNH ---
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot ONDO Phan Rang - chỉ theo dõi ONDO\n/price - giá ONDO\n/signal - RSI+Breakout ONDO\n/whale - cá voi >100k\n/auto_signal - auto báo tín hiệu 15p\n/auto_whale - auto báo cá voi 5p")

async def price_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(get_price_ondo())

async def signal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(get_ondo_signal())

async def whale_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    whales, err = get_whales()
    if err: await update.message.reply_text(err); return
    if not whales: await update.message.reply_text("24h qua chưa có giao dịch ONDO >100k"); return
    msg="🐋 Cá voi ONDO >100k:\n\n"
    for tx in whales:
        v=int(tx['value'])/10**18
        msg+=f"💰 {v:,.0f} ONDO\nhttps://etherscan.io/tx/{tx['hash']}\n\n"
    await update.message.reply_text(msg, disable_web_page_preview=True)

async def auto_signal_job(context: ContextTypes.DEFAULT_TYPE):
    sig = get_ondo_signal()
    if "BUY MẠNH" in sig or "SELL MẠNH" in sig or "BREAKOUT" in sig or "BREAKDOWN" in sig:
        await context.bot.send_message(chat_id=context.job.chat_id, text=f"🚨 AUTO ONDO\n{sig}")

async def auto_whale_job(context: ContextTypes.DEFAULT_TYPE):
    whales, err = get_whales()
    if err or not whales: return
    for tx in whales:
        if tx['hash'] in SEEN_TXS: continue
        SEEN_TXS.add(tx['hash'])
        v=int(tx['value'])/10**18
        await context.bot.send_message(chat_id=context.job.chat_id, text=f"🚨 CÁ VOI ONDO!\n💰 {v:,.0f} ONDO\nhttps://etherscan.io/tx/{tx['hash']}", disable_web_page_preview=True)

async def auto_signal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id=update.effective_chat.id
    jobs=context.job_queue.get_jobs_by_name(f"sig_{chat_id}")
    if jobs:
        for j in jobs: j.schedule_removal()
        await update.message.reply_text("Đã TẮT auto tín hiệu ONDO")
        return
    context.job_queue.run_repeating(auto_signal_job, interval=900, first=5, chat_id=chat_id, name=f"sig_{chat_id}")
    await update.message.reply_text("Đã BẬT auto tín hiệu ONDO - 15 phút check 1 lần")

async def auto_whale_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id=update.effective_chat.id
    jobs=context.job_queue.get_jobs_by_name(f"whale_{chat_id}")
    if jobs:
        for j in jobs: j.schedule_removal()
        await update.message.reply_text("Đã TẮT auto cá voi")
        return
    context.job_queue.run_repeating(auto_whale_job, interval=300, first=5, chat_id=chat_id, name=f"whale_{chat_id}")
    await update.message.reply_text("Đã BẬT auto cá voi ONDO >100k - 5 phút check 1 lần")

def run_flask():
    app_flask.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("price", price_cmd))
    app.add_handler(CommandHandler("signal", signal_cmd))
    app.add_handler(CommandHandler("whale", whale_cmd))
    app.add_handler(CommandHandler("auto_signal", auto_signal_cmd))
    app.add_handler(CommandHandler("auto_whale", auto_whale_cmd))
    print("ONDO Bot starting...")
    app.run_polling(stop_signals=None, close_loop=False)
