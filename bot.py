import os
import logging
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import requests
import sqlite3
from datetime import datetime

# Logging setup
logging.basicConfig(level=logging.INFO)

# Flask app for webhook
app = Flask(__name__)

# Environment Variables
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
WEBHOOK_BASE_URL = os.environ.get('WEBHOOK_BASE_URL')

INSTAMOJO_API_KEY = os.environ.get('INSTAMOJO_API_KEY')
INSTAMOJO_AUTH_TOKEN = os.environ.get('INSTAMOJO_AUTH_TOKEN')
INSTAMOJO_ENDPOINT = os.environ.get('INSTAMOJO_ENDPOINT', 'https://www.instamojo.com/api/1.1/')

# SQLite setup for user payments
DB_FILE = "payments.db"
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
cur = conn.cursor()
cur.execute('''
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY,
        telegram_id INTEGER,
        name TEXT,
        email TEXT,
        amount REAL,
        purpose TEXT,
        payment_link TEXT,
        status TEXT,
        created_at TEXT
    )
''')
conn.commit()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Welcome to Consult Zone India Telegram Bot! Use /pay <amount> <purpose> to generate payment link.")

async def pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2:
        return await update.message.reply_text("Usage: /pay <amount> <purpose>")
    
    amount = args[0]
    purpose = " ".join(args[1:])
    user = update.effective_user

    payment_link = create_payment_link(amount, purpose, user.full_name, user.username + "@telegram.me")
    if payment_link:
        cur.execute("INSERT INTO payments (telegram_id, name, email, amount, purpose, payment_link, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (user.id, user.full_name, user.username + "@telegram.me", amount, purpose, payment_link, "PENDING", datetime.now()))
        conn.commit()
        await update.message.reply_text(f"Payment Link: {payment_link}")
    else:
        await update.message.reply_text("Error creating payment link!")

def create_payment_link(amount, purpose, buyer_name, buyer_email):
    payload = {
        "purpose": purpose,
        "amount": amount,
        "buyer_name": buyer_name,
        "email": buyer_email,
        "redirect_url": f"{WEBHOOK_BASE_URL}/instamojo_callback",
        "send_email": True,
        "allow_repeated_payments": False
    }
    headers = {
        "X-Api-Key": INSTAMOJO_API_KEY,
        "X-Auth-Token": INSTAMOJO_AUTH_TOKEN
    }
    try:
        res = requests.post(f"{INSTAMOJO_ENDPOINT}payment-requests/", data=payload, headers=headers).json()
        return res["payment_request"]["longurl"]
    except:
        return None

@app.post("/telegram_webhook")
async def telegram_webhook():
    update = Update.de_json(request.get_json(), application.bot)
    await application.process_update(update)
    return jsonify(success=True)

@app.get("/instamojo_callback")
def instamojo_callback():
    payment_id = request.args.get("payment_id")
    status = request.args.get("payment_status")
    cur.execute("UPDATE payments SET status = ? WHERE payment_link LIKE ?", (status, f"%{payment_id}%"))
    conn.commit()
    return "Payment updated"

def setup_webhook():
    url = f"{WEBHOOK_BASE_URL}/telegram_webhook"
    webhook_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook?url={url}"
    print(requests.get(webhook_url).text)

if __name__ == "__main__":
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("pay", pay))
    
    setup_webhook()
    app.run(host="0.0.0.0", port=5000)
