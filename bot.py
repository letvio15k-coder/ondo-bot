import os, threading, requests, time
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.environ.get("TOKEN")
ETHERSCAN_API = os.environ.get("ETHERSCAN_API")

app_flask = Flask(__name__)
@app_flask.route('/')
def home(): return "ONDO Whale Pro running!"

CONTRACT = "0xfAbA6f8e4a5E8Ab82F62fe7C39859FA577269BE3"
SEEN_TXS = set()
LAST_PRICE = {"text": "", "time": 0, "price": 0}
PRICE_HISTORY = []

# Ví nóng các sàn lớn trên Ethereum
EXCHANGE_WALLETS = {
    "0x28c6c06298d514db089934071355e5743bf21d60": "Binance 14",
    "0x21a31ee1afc51d94c2efccaa2092ad1028285549": "Binance 15",
    "0xdfd5293d8eb6f1f10008e494abea82c400cf762f": "Binance 16",
    "0xbeab2072183cc0eb44da95f5dcc6ebc0d5d93f06": "Binance 17",
    "0x71660c4005ba2814f82cbeae2e7b0fbba0d07100": "Coinbase",
    "0x4d2211dc33dccad2d33e688a60fbba72f7dc91d4": "Coinbase",
    "0xa9d1e08c7793af67e9d92fe308d5697fb81d3e43": "Coinbase",
    "0x28a9ad368259ba7c32ccb76a804f46309e859345": "OKX",
    "0x6cc5f688a315f3dc28a7781717a9a798a59fda7b": "OKX",
    "0x75e89d5979e65f60f77756a337d4649a07a6e61f": "Bybit",
    "0xf977814e90da44bfa03b6295a0616a897441ace": "Bybit",
}

def get_wallet_label(addr):
    if not addr: return "Unknown"
    low = addr.lower()
    if low in EXCHANGE_WALLETS:
        return f"🏦 {EXCHANGE_WALLETS[low]}"
    # check có phải contract không (Uniswap, v.v.)
    try:
        url = f"https://api.etherscan.io/v2/api?chainid=1&module=proxy&action=eth_getCode&address={addr}&apikey={ETHERSCAN_API}"
        r = requests.get(url, timeout=10).json()
        if r.get('result') and r['result']!= '0x' and r['result']!= '0x0':
            return "📜 Contract/DEX"
    except: pass
    return "🐋 Ví cá nhân"

def get_price_ondo_raw():
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        r = requests.get("https://data-api.binance.vision/api/v3/ticker/price?symbol=ONDOUSDT", headers=headers, timeout=10).json()
        return float(r['price']), "Binance"
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
        PRICE_HISTORY.append((now, price))
        PRICE_HISTORY[:] = [(t,p) for t,p in PRICE_HISTORY if now - t < 7200]
        return text
    except Exception as e:
        return f"❌ Lỗi giá: {e}"

def get_price_change_15m():
    if len(PRICE_HISTORY) < 2: return 0
    now = time.time()
    old_price = None
    for t,p in reversed(PRICE_HISTORY):
        if now - t >= 900:
            old_price = p
            break
    if not old_price: old_price = PRICE_HISTORY[0][1]
    current = LAST_PRICE.get("price", old_price) or old_price
    return (current - old_price) / old_price * 100 if old_price else 0

def get_whales():
    try:
        url = f"https://api.etherscan.io/v2/api?chainid=1&module=account&action=tokentx&contractaddress={CONTRACT}&page=1&offset=20&sort=desc&apikey={ETHERSCAN_API}"
        r = requests.get(url, timeout=15).json()
        if r['status']!= '1': return None, f"Etherscan: {r.get('result')}"
        whales=[]
        for tx in r['result']:
            v = int(tx['value']) / 10**18
            if v >= 100000: whales.append(tx)
            if len(whales) >=5: break
        return whales, None
    except Exception as e:
        return None, str(e)

# --- COMMANDS ---
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot ONDO Phan Rang PRO\n/price\n/whale\n/auto_whale - kèm ví sàn")

async def price_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(get_price_ondo())

async def whale_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    whales, err = get_whales()
    if err: await update.message.reply_text(err); return
    if not whales: await update.message.reply_text("Chưa có >100k"); return
    msg = get_price_ondo() + "\n\n🐋 Cá voi ONDO >100k:\n\n"
    for tx in whales:
        v=int(tx['value'])/10**18
        from_label = get_wallet_label(tx['from'])
        to_label = get_wallet_label(tx['to'])
        msg+=f"💰 {v:,.0f} ONDO\nTừ: {from_label}\nĐến: {to_label}\nhttps://etherscan.io/tx/{tx['hash']}\n\n"
    await update.message.reply_text(msg, disable_web_page_preview=True)

async def auto_whale_job(context: ContextTypes.DEFAULT_TYPE):
    whales, err = get_whales()
    if err or not whales: return
    for tx in whales:
        if tx['hash'] in SEEN_TXS: continue
        SEEN_TXS.add(tx['hash'])
        v=int(tx['value'])/10**18
        try:
            price_val, source = get_price_ondo_raw()
            usd_val = v * price_val
            change_15m = get_price_change_15m()

            from_addr = tx['from']
            to_addr = tx['to']
            from_label = get_wallet_label(from_addr)
            to_label = get_wallet_label(to_addr)

            # Phân tích hành động
            action = "🔄 Chuyển ví"
            if "🏦" in from_label and "🐋" in to_label: action = "✅ RÚT KHỎI SÀN - Đang GOM 🟢"
            elif "🐋" in from_label and "🏦" in to_label: action = "⚠️ NẠP LÊN SÀN - Có thể XẢ 🔴"
            elif "🏦" in from_label and "🏦" in to_label: action = "🏦 Chuyển giữa các sàn"

            trend = "Đi ngang"
            if change_15m > 0.5: trend = "Đang tăng"
            elif change_15m < -0.5: trend = "Đang giảm"

            msg = (f"🚨 CÁ VOI 100k+ ONDO!\n"
                   f"💰 {v:,.0f} ONDO (~${usd_val:,.0f})\n"
                   f"💵 Giá lúc chuyển: ${price_val:.5f} ({source})\n"
                   f"📊 15p trước: {change_15m:+.2f}% ({trend})\n\n"
                   f"Từ: {from_label}\n`{from_addr[:10]}...`\n"
                   f"Đến: {to_label}\n`{to_addr[:10]}...`\n\n"
                   f"👉 {action}\n"
                   f"https://etherscan.io/tx/{tx['hash']}")
            await context.bot.send_message(chat_id=context.job.chat_id, text=msg, disable_web_page_preview=True, parse_mode='Markdown')
            get_price_ondo()
        except Exception as e:
            print(f"whale error {e}")

async def auto_whale_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id=update.effective_chat.id
    jobs=context.job_queue.get_jobs_by_name(f"whale_{chat_id}")
    if jobs:
        for j in jobs: j.schedule_removal()
        await update.message.reply_text("Đã TẮT auto cá voi PRO")
        return
    context.job_queue.run_repeating(auto_whale_job, interval=300, first=5, chat_id=chat_id, name=f"whale_{chat_id}")
    await update.message.reply_text("Đã BẬT auto cá voi PRO!\nKèm: Giá + USD + % 15p + Ví sàn (Binance/Coinbase/Ví cá nhân) + Phân tích Gom/Xả")

def run_flask():
    app_flask.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("price", price_cmd))
    app.add_handler(CommandHandler("whale", whale_cmd))
    app.add_handler(CommandHandler("auto_whale", auto_whale_cmd))
    print("ONDO Bot PRO starting...")
    app.run_polling(stop_signals=None, close_loop=False)
