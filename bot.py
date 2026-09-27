import os, threading, requests
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.environ.get("TOKEN")
ETHERSCAN_API = os.environ.get("ETHERSCAN_API")

app_flask = Flask(__name__)
@app_flask.route('/')
def home(): return "ONDO Whale Bot is running!"

CONTRACT = "0xfAbA6f8e4a5E8Ab82F62fe7C39859FA577269BE3"
SEEN_TXS = set()

def get_price():
    # OKX - không chặn, chạy ngon nhất
    try:
        url = "https://www.okx.com/api/v5/market/ticker?instId=ONDO-USDT"
        r = requests.get(url, timeout=10).json()
        data = r['data'][0]
        return f"🔴 ONDO: ${data['last']} ({float(data['volCcy24h']):,.0f} vol 24h)"
    except Exception as e:
        print(f"OKX fail: {e}")
    # Bybit
    try:
        url = "https://api.bybit.com/v5/market/tickers?category=spot&symbol=ONDOUSDT"
        r = requests.get(url, timeout=10).json()
        d = r['result']['list'][0]
        return f"🔴 ONDO: ${d['lastPrice']} ({float(d['price24hPcnt'])*100:.2f}% 24h)"
    except Exception as e:
        print(f"Bybit fail: {e}")
    # CoinGecko cuối cùng
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=ondo-finance&vs_currencies=usd"
        r = requests.get(url, timeout=10, headers={'User-Agent':'Mozilla/5.0'}).json()
        return f"🔴 ONDO: ${r['ondo-finance']['usd']} (CoinGecko)"
    except Exception as e:
        print(f"CG fail: {e}")
        return f"Lỗi lấy giá thật: {e}"

def get_whales(min_value=100000, limit=5):
    try:
        url = f"https://api.etherscan.io/api?module=account&action=tokentx&contractaddress={CONTRACT}&page=1&offset=20&sort=desc&apikey={ETHERSCAN_API}"
        r = requests.get(url, timeout=15).json()
        if r['status']!= '1':
            return None, "Chưa có ETHERSCAN_API key"
        whales = []
        for tx in r['result']:
            value = int(tx['value']) / 10**18
            if value >= min_value:
                whales.append(tx)
            if len(whales) >= limit:
                break
        return whales, None
    except Exception as e:
        return None, str(e)

async def price_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(get_price())

async def whale_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    whales, err = get_whales(100000, 5)
    if err:
        await update.message.reply_text(err)
        return
    if not whales:
        await update.message.reply_text("24h qua chưa có giao dịch >100k ONDO.")
        return
    msg = "🐋 5 cá voi ONDO (>100k):\n\n"
    for tx in whales:
        v = int(tx['value']) / 10**18
        msg += f"💰 {v:,.0f} ONDO\nhttps://etherscan.io/tx/{tx['hash']}\n\n"
    await update.message.reply_text(msg, disable_web_page_preview=True)

async def auto_whale_job(context: ContextTypes.DEFAULT_TYPE):
    whales, err = get_whales(100000, 3)
    if err or not whales: return
    for tx in whales:
        if tx['hash'] in SEEN_TXS: continue
        SEEN_TXS.add(tx['hash'])
        v = int(tx['value']) / 10**18
        msg = f"🚨 CÁ VOI 100k+ ONDO!\n💰 {v:,.0f} ONDO\nhttps://etherscan.io/tx/{tx['hash']}"
        await context.bot.send_message(chat_id=context.job.chat_id, text=msg, disable_web_page_preview=True)

async def auto_whale_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    for job in context.job_queue.get_jobs_by_name(f"whale_{chat_id}"):
        job.schedule_removal()
        await update.message.reply_text("Đã TẮT báo cá voi.")
        return
    context.job_queue.run_repeating(auto_whale_job, interval=300, first=0, chat_id=chat_id, name=f"whale_{chat_id}")
    await update.message.reply_text("Đã BẬT báo cá voi >100k (5p check).")

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app_flask.run(host='0.0.0.0', port=port)

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    print("ONDO Whale Bot is starting...")
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("price", price_cmd))
    application.add_handler(CommandHandler("whale", whale_cmd))
    application.add_handler(CommandHandler("auto_whale", auto_whale_cmd))
    application.run_polling(stop_signals=None, close_loop=False)
