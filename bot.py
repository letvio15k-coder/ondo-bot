import os, threading, requests, time
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.environ.get("TOKEN")
ETHERSCAN_API = os.environ.get("ETHERSCAN_API")

app_flask = Flask(__name__)
@app_flask.route('/')
def home(): return "ONDO Bot 9 Lenh Fixed Running!"

CONTRACT = "0xfAbA6f8e4a5E8Ab82F62fe7C39859FA577269BE3"
SEEN_TXS = set()
LAST_PRICE = {"text": "", "time": 0, "price": 0}
PRICE_HISTORY = []

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
    if low in EXCHANGE_WALLETS: return f"🏦 {EXCHANGE_WALLETS[low]}"
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
    try:
        url = "https://www.okx.com/api/v5/market/candles?instId=ONDO-USDT&bar=15m&limit=2"
        r = requests.get(url, timeout=10).json()
        c1 = float(r['data'][0][4]); c2 = float(r['data'][1][4])
        return (c1 - c2) / c2 * 100
    except: return 0

def get_ondo_signal():
    try:
        url = "https://www.okx.com/api/v5/market/candles?instId=ONDO-USDT&bar=1H&limit=100"
        r = requests.get(url, timeout=10).json()
        data = r['data'][::-1]; closes = [float(x[4]) for x in data]
        price = closes[-1]
        gains = [max(closes[i]-closes[i-1],0) for i in range(1,len(closes))]
        losses = [max(closes[i-1]-closes[i],0) for i in range(1,len(closes))]
        avg_gain = sum(gains[-14:])/14; avg_loss = sum(losses[-14:])/14 or 0.00001
        rsi = 100 - (100/(1+avg_gain/avg_loss))
        ema20 = sum(closes[-20:])/20; ema50 = sum(closes[-50:])/50
        if rsi < 30: return f"📊 ONDO ${price:.4f} RSI:{rsi:.1f}\n🟢🟢 BUY MẠNH"
        elif rsi > 70: return f"📊 ONDO ${price:.4f} RSI:{rsi:.1f}\n🔴🔴 SELL MẠNH"
        elif ema20 > ema50: return f"📊 ONDO ${price:.4f} RSI:{rsi:.1f}\n🟢 BUY"
        else: return f"📊 ONDO ${price:.4f} RSI:{rsi:.1f}\n🔴 SELL/NEUTRAL"
    except Exception as e: return f"Lỗi tín hiệu: {e}"

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
    except Exception as e: return None, str(e)

def get_top_holders():
    try:
        url = f"https://api.ethplorer.io/getTopTokenHolders/{CONTRACT}?apiKey=freekey"
        r = requests.get(url, timeout=20).json()
        if 'holders' not in r: return None, f"Lỗi: {r}"
        return r['holders'], None
    except Exception as e: return None, str(e)

# --- COMMANDS ---
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Bot ONDO Phan Rang PRO - 9 Lệnh FIX\n\n"
        "Xem nhanh:\n/price - giá\n/whale - cá voi\n/signal - tín hiệu\n/top - Top 10 ví\n/top100 - thống kê Top 100\n\n"
        "AUTO:\n/auto_price - giá 1h\n/auto_whale - cá voi 5p\n/auto_signal - tín hiệu 15p"
    )
async def price_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(get_price_ondo())
async def signal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(get_ondo_signal())
async def whale_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    whales, err = get_whales()
    if err: await update.message.reply_text(err); return
    if not whales: await update.message.reply_text("Chưa có >100k"); return
    msg = get_price_ondo() + "\n\n🐋 Cá voi >100k:\n\n"
    for tx in whales:
        v=int(tx['value'])/10**18
        msg+=f"💰 {v:,.0f} ONDO\nTừ: {get_wallet_label(tx['from'])}\nĐến: {get_wallet_label(tx['to'])}\nhttps://etherscan.io/tx/{tx['hash']}\n\n"
    await update.message.reply_text(msg, disable_web_page_preview=True)

async def top_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Đang lấy Top 100 ví ONDO (Free API)...")
    holders, err = get_top_holders()
    if err: await update.message.reply_text(err); return
    if not holders: await update.message.reply_text("Không lấy được"); return
    msg = "🐋 TOP 10 VÍ NẮM ONDO:\n\n"
    for i, h in enumerate(holders[:10], 1):
        addr = h['address']; bal = float(h['balance']) / 10**18; percent = float(h['share'])
        label = get_wallet_label(addr); short = f"{addr[:6]}...{addr[-4:]}"
        msg += f"{i}. {label} {short}\n💰 {bal:,.0f} ({percent:.2f}%)\n\n"
    top10_total = sum(float(x['share']) for x in holders[:10])
    top100_total = sum(float(x['share']) for x in holders[:100])
    msg += f"📊 Top10: {top10_total:.2f}% | Top100: {top100_total:.2f}%"
    await update.message.reply_text(msg)

async def top100_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    holders, err = get_top_holders()
    if err: await update.message.reply_text(err); return
    def calc(n): return sum(float(x['share']) for x in holders[:n])
    top10, top20, top50, top100 = calc(10), calc(20), calc(50), calc(100)
    status = "🔒 Tập trung cao" if top10 > 60 else "✅ Phân tán tốt" if top10 < 40 else "⚠️ Trung bình"
    msg = f"📈 PHÂN BỔ ONDO (10B)\n\nTop 10: {top10:.2f}%\nTop 20: {top20:.2f}%\nTop 50: {top50:.2f}%\nTop 100: {top100:.2f}%\n\n{status}"
    await update.message.reply_text(msg)

# --- JOBS ---
async def auto_price_job(context: ContextTypes.DEFAULT_TYPE):
    try:
        price_text = get_price_ondo(); change = get_price_change_15m()
        await context.bot.send_message(chat_id=context.job.chat_id, text=f"⏰ AUTO GIÁ 1H\n{price_text}\n15p: {change:+.2f}%")
    except: pass
async def auto_whale_job(context: ContextTypes.DEFAULT_TYPE):
    whales, err = get_whales()
    if err or not whales: return
    for tx in whales:
        if tx['hash'] in SEEN_TXS: continue
        SEEN_TXS.add(tx['hash']); v=int(tx['value'])/10**18
        try:
            price_val, source = get_price_ondo_raw(); usd_val = v * price_val; change_15m = get_price_change_15m()
            from_label = get_wallet_label(tx['from']); to_label = get_wallet_label(tx['to'])
            action = "🔄 Chuyển ví"
            if "🏦" in from_label and "🐋" in to_label: action = "✅ RÚT KHỎI SÀN - GOM 🟢"
            elif "🐋" in from_label and "🏦" in to_label: action = "⚠️ NẠP LÊN SÀN - Có thể XẢ 🔴"
            elif "🏦" in from_label and "🏦" in to_label: action = "🏦 Chuyển giữa các sàn"
            msg = (f"🚨 CÁ VOI 100k+ ONDO!\n💰 {v:,.0f} (~${usd_val:,.0f})\n💵 ${price_val:.5f} ({source})\n📊 15p: {change_15m:+.2f}%\n\nTừ: {from_label}\n`{tx['from'][:10]}...`\nĐến: {to_label}\n`{tx['to'][:10]}...`\n\n👉 {action}\nhttps://etherscan.io/tx/{tx['hash']}")
            await context.bot.send_message(chat_id=context.job.chat_id, text=msg, disable_web_page_preview=True, parse_mode='Markdown')
            get_price_ondo()
        except Exception as e: print(f"whale error {e}")
async def auto_signal_job(context: ContextTypes.DEFAULT_TYPE):
    sig = get_ondo_signal()
    if "MẠNH" in sig: await context.bot.send_message(chat_id=context.job.chat_id, text=f"🚨 AUTO SIGNAL\n{sig}")

async def auto_price_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id=update.effective_chat.id; jobs=context.job_queue.get_jobs_by_name(f"price_{chat_id}")
    if jobs:
        for j in jobs: j.schedule_removal()
        await update.message.reply_text("Đã TẮT auto giá 1h"); return
    context.job_queue.run_repeating(auto_price_job, interval=3600, first=10, chat_id=chat_id, name=f"price_{chat_id}")
    await update.message.reply_text("Đã BẬT auto giá 1h")
async def auto_whale_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id=update.effective_chat.id; jobs=context.job_queue.get_jobs_by_name(f"whale_{chat_id}")
    if jobs:
        for j in jobs: j.schedule_removal()
        await update.message.reply_text("Đã TẮT auto cá voi PRO"); return
    context.job_queue.run_repeating(auto_whale_job, interval=300, first=5, chat_id=chat_id, name=f"whale_{chat_id}")
    await update.message.reply_text("Đã BẬT auto cá voi PRO")
async def auto_signal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id=update.effective_chat.id; jobs=context.job_queue.get_jobs_by_name(f"sig_{chat_id}")
    if jobs:
        for j in jobs: j.schedule_removal()
        await update.message.reply_text("Đã TẮT auto tín hiệu"); return
    context.job_queue.run_repeating(auto_signal_job, interval=900, first=5, chat_id=chat_id, name=f"sig_{chat_id}")
    await update.message.reply_text("Đã BẬT auto tín hiệu")

def run_flask():
    app_flask.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("price", price_cmd))
    app.add_handler(CommandHandler("whale", whale_cmd))
    app.add_handler(CommandHandler("signal", signal_cmd))
    app.add_handler(CommandHandler("top", top_cmd))
    app.add_handler(CommandHandler("top100", top100_cmd))
    app.add_handler(CommandHandler("auto_price", auto_price_cmd))
    app.add_handler(CommandHandler("auto_whale", auto_whale_cmd))
    app.add_handler(CommandHandler("auto_signal", auto_signal_cmd))
    print("ONDO Bot 9 lenh FIX starting...")
    app.run_polling(stop_signals=None, close_loop=False)
