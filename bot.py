import os, threading, requests
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.environ.get("TOKEN")
app_flask = Flask(__name__)

@app_flask.route('/')
def home(): return "ONDO Bot is running!"

def get_price():
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        # Thử CoinGecko trước
        url = "https://api.coingecko.com/api/v3/coins/ondo-finance?localization=false&tickers=false&market_data=true&community_data=false"
        r = requests.get(url, headers=headers, timeout=15)
        data = r.json()
        price = data['market_data']['current_price']['usd']
        change = data['market_data']['price_change_percentage_24h']
        return f"🔴 ONDO: ${price}\n24h: {change:.2f}%"
    except Exception as e:
        print(f"Loi Coingecko: {e}")
        # Fallback sang Binance nếu Coingecko chặn
        try:
            url2 = "https://api.binance.com/api/v3/ticker/24hr?symbol=ONDOUSDT"
            r2 = requests.get(url2, timeout=10).json()
            return f"🔴 ONDO: ${r2['lastPrice']}\n24h: {float(r2['priceChangePercent']):.2f}% (Binance)"
        except:
            return f"Lỗi lấy giá ONDO! Thử lại sau 1 phút nhé."

async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(get_price())

async def auto_job(context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=context.job.chat_id, text=f"Báo giá tự động - {get_price()}")

async def auto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    for job in context.job_queue.get_jobs_by_name(str(chat_id)):
        job.schedule_removal()
    context.job_queue.run_repeating(auto_job, interval=3600, first=0, chat_id=chat_id, name=str(chat_id))
    await update.message.reply_text("Đã bật báo giá tự động mỗi 1 giờ!")

def run_flask():
    app_flask.run(host='0.0.0.0', port=10000)

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("price", price))
    application.add_handler(CommandHandler("auto", auto))
    application.run_polling(stop_signals=None, close_loop=False)
