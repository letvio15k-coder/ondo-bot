from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import requests

TOKEN = "8690238045:AAG4UpI1tVbgi65FUGH6pPKQNd3SqXWf5_k"

def lay_gia_ondo():
    try:
        r = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=ondo-finance&vs_currencies=usd&include_24hr_change=true", timeout=10).json()
        data = r['ondo-finance']
        return data['usd'], data['usd_24h_change']
    except:
        return 0, 0

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✅ Bot ONDO Phan Rang đã bật AUTO!\n"
        "Gõ /auto để bắt đầu báo giá mỗi giờ.\n"
        "Gõ /stop để tắt báo tự động."
    )

async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    gia, change = lay_gia_ondo()
    icon = "🟢" if change >= 0 else "🔴"
    await update.message.reply_text(f"{icon} ONDO: ${gia:.6f}\n24h: {change:+.2f}%")

async def auto_send(context: ContextTypes.DEFAULT_TYPE):
    gia, change = lay_gia_ondo()
    if gia:
        icon = "🟢" if change >= 0 else "🔴"
        await context.bot.send_message(
            chat_id=context.job.chat_id,
            text=f"⏰ Báo giá tự động - ONDO: ${gia:.6f} ({change:+.2f}% 24h)"
        )

async def auto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    # Xóa báo cũ nếu có
    for job in context.job_queue.get_jobs_by_name(str(chat_id)):
        job.schedule_removal()

    context.job_queue.run_repeating(auto_send, interval=3600, first=5, chat_id=chat_id, name=str(chat_id))
    await update.message.reply_text("⏰ Đã bật báo tự động mỗi 1 GIỜ! 5 giây nữa sẽ báo thử.")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    for job in context.job_queue.get_jobs_by_name(str(chat_id)):
        job.schedule_removal()
    await update.message.reply_text("Đã tắt báo tự động.")

app = Application.builder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("price", price))
app.add_handler(CommandHandler("auto", auto))
app.add_handler(CommandHandler("stop", stop))

print("Bot AUTO đang chạy... đừng tắt cửa sổ này")
app.run_polling()