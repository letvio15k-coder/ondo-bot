import os, requests, threading
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.environ.get("TOKEN")
app_flask = Flask(__name__)
@app_flask.route('/')
def home(): return "Bot ONDO dang chay 24/7"

def lay_gia_ondo():
    try:
        r = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=ondo-finance&vs_currencies=usd&include_24hr_change=true", timeout=10).json()
        d = r['ondo-finance']; return d['usd'], d['usd_24h_change']
    except: return 0,0

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot 24/7 FREE đang chạy!\n/price xem giá\n/auto báo mỗi giờ")
async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    gia,ch = lay_gia_ondo(); icon="🟢" if ch>=0 else "🔴"
    await update.message.reply_text(f"{icon} ONDO: ${gia:.6f} ({ch:+.2f}%)")
async def auto_send(context: ContextTypes.DEFAULT_TYPE):
    gia,ch = lay_gia_ondo()
    if gia:
        await context.bot.send_message(chat_id=context.job.chat_id, text=f"⏰ ONDO: ${gia:.6f} ({ch:+.2f}%)")
async def auto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id=update.effective_chat.id
    for job in context.job_queue.get_jobs_by_name(str(chat_id)): job.schedule_removal()
    context.job_queue.run_repeating(auto_send, interval=3600, first=5, chat_id=chat_id, name=str(chat_id))
    await update.message.reply_text("⏰ Đã bật báo mỗi giờ!")
async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for job in context.job_queue.get_jobs_by_name(str(update.effective_chat.id)): job.schedule_removal()
    await update.message.reply_text("Đã tắt báo tự động.")

def run_bot():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start)); app.add_handler(CommandHandler("price", price))
    app.add_handler(CommandHandler("auto", auto)); app.add_handler(CommandHandler("stop", stop))
    app.run_polling()

if __name__ == "__main__":
    threading.Thread(target=run_bot).start()
    app_flask.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
