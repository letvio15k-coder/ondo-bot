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
    errors = []
    # Thử 1: Binance VISION - link này không bị chặn
    try:
        url = "https://data-api.binance.vision/api/v3/ticker/24hr?symbol=ONDOUSDT"
        r = requests.get(url, timeout=10).json()
        return f"🔴 ONDO: ${r['lastPrice']} ({float(r['priceChangePercent']):.2f}% 24h)"
    except Exception as e:
        errors.append(f"Binance Vision: {e}")

    # Thử 2: Bybit - cũng không chặn
    try:
        url = "https://api.bybit.com/v5/market/tickers?category=spot&symbol=ONDOUSDT"
        r = requests.get(url, timeout=10).json()
        data = r['result']['list'][0]
        return f"🔴 ONDO: ${data['lastPrice']} ({float(data['price24hPcnt'])*100:.2f}% 24h) Bybit"
    except Exception as e:
        errors.append(f"Bybit: {e}")

    # Thử 3: CoinGecko
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        url = "https://api.coingecko.com/api/v3/simple/price?ids=ondo-finance&vs_currencies=usd&include_24hr_change=true"
        r = requests.get(url, headers=headers, timeout=15).json()
        price = r['ondo-finance']['usd']
        change = r['ondo-finance']['usd_24h_change']
        return f"🔴 ONDO: ${price} ({change:.2f}% 24h) CG"
    except Exception as e:
        errors.append(f"CG: {e}")

    print("LOI LAY GIA:", errors) # in ra log Render để mình xem
    return f"Lỗi lấy giá. Chi tiết log: {errors[0] if errors else 'unknown'}"

def get_whales(min_value=100000, limit=5):
    try:
        url = f"https://api.etherscan.io/api?module=account&action=tokentx&contractaddress={CONTRACT}&page=1&offset=20&sort=desc&apikey={ETHERSCAN_API}"
        r = requests.get(url, timeout=15).json()
        if r['status']!= '1':
            return None, "Bạn chưa thêm ETHERSCAN_API key vào Render hoặc key sai."
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

async def debug_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        r = requests.get("https://data-api.binance.vision/api/v3/ticker/24hr?symbol=ONDOUSDT", timeout=10)
        await update.message.reply_text(f"Debug OK: status {r.status_code}\n{r.text[:500]}")
    except Exception as e:
        await update.message.reply_text(f"Debug Lỗi: {e}")

async def whale_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    whales, err = get_whales(min_value=100000, limit=5)
    if err:
        await update.message.reply_text(err)
        return
    if not whales:
        await update.message.reply_text("24h qua chưa có giao dịch cá voi >100k ONDO.")
        return
    msg = "🐋 5 cá voi ONDO gần nhất (>100k):\n\n"
    for tx in whales:
        value = int(tx['value']) / 10**18
        msg += f"💰 {value:,.0f} ONDO\nhttps://etherscan.io/tx/{tx['hash']}\n\n"
    await update.message.reply_text(msg, disable_web_page_preview=True)

async def auto_whale_job(context: ContextTypes.DEFAULT_TYPE):
    whales, err = get_whales(min_value=100000, limit=3)
    if err or not whales:
        return
    for tx in whales:
        if tx['hash'] in SEEN_TXS:
            continue
        SEEN_TXS.add(tx['hash'])
        value = int(tx['value']) / 10**18
        msg = f"🚨 CÁ VOI ONDO!\n💰 {value:,.0f} ONDO\nhttps://etherscan.io/tx/{tx['hash']}"
        await context.bot.send_message(chat_id=context.job.chat_id, text=msg, disable_web_page_preview=True)

async def auto_whale_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    for job in context.job_queue.get_jobs_by_name(f"whale_{chat_id}"):
        job.schedule_removal()
        await update.message.reply_text("Đã TẮT báo cá voi.")
        return
    context.job_queue.run_repeating(auto_whale_job, interval=300, first=0, chat_id=chat_id, name=f"whale_{chat_id}")
    await update.message.reply_text("Đã BẬT báo cá voi >100k (5p check 1 lần).")

def run_flask():
    app_flask.run(host='0.0.0.0', port=10000)

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("price", price_cmd))
    application.add_handler(CommandHandler("whale", whale_cmd))
    application.add_handler(CommandHandler("auto_whale", auto_whale_cmd))
    application.add_handler(CommandHandler("debug", debug_cmd))
    application.run_polling(stop_signals=None, close_loop=False)
