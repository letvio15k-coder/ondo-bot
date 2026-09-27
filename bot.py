import os
import threading
from flask import Flask
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.environ.get("TOKEN")

app_flask = Flask(__name__)
@app_flask.route('/')
def home():
    return "ONDO Bot is running!"

def get_price():
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=ondo-finance&vs_currencies=usd"
        r = requests.get(url, timeout=10).json()
        price = r['ondo-finance']['usd']
        return f"ONDO: ${price}"
    except:
        return "Lỗi lấy giá ONDO!"

async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(get_price())

async def auto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    # Xóa job cũ nếu có
    for job in context.job_queue.get_jobs_by_name(str(chat_id)):
        job.schedule_removal()
    context.job_queue.run_repeating(lambda ctx: ctx.bot.send_message(chat_id=chat_id, text=f"Báo giá tự động - {get_price()}"), interval=3600, first=0, name=str(chat_id))
    await update.message.reply_text("Đã bật báo giá tự động mỗi 1 giờ!")

def run_flask():
    app_flask.run(host='0.0.0.0', port=10000)

if __name__ == '__main__':
    # Chạy Flask ở thread phụ
    threading.Thread(target=run_flask, daemon=True).start()
    
    # Chạy bot ở thread chính (sửa lỗi set_wakeup_fd)
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("price", price))
    application.add_handler(CommandHandler("auto", auto))
    application.run_polling(stop_signals=None, close_loop=False)
