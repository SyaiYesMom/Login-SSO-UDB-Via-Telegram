import base64
import json
from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)

BOT_TOKEN = "TOKEN TELEGRAM"

CAPTCHA, USERNAME, PASSWORD = range(3)

session = cffi_requests.Session()
session.headers.update({
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Language': 'en-US,en;q=0.9',
    'Connection': 'keep-alive',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36',
    'sec-ch-ua': '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
})


def captcha():
    response = session.get('https://auth.sso.udb.ac.id/renewcaptcha')
    data = response.json()
    return data.get('newtoken'), data.get('newimage')

def save_captcha_image(base64_data, filename="captcha.png"):
    if "," in base64_data:
        base64_data = base64_data.split(",", 1)[1]
    image_bytes = base64.b64decode(base64_data)
    with open(filename, "wb") as f:
        f.write(image_bytes)

def login(username, password, token, captcha_text):
    data = {
        'url': '',
        'timezone': '7',
        'skin': 'bootstrap',
        'token': token,
        'user': username,
        'password': password,
        'captcha': captcha_text,
    }
    response = session.post('https://auth.sso.udb.ac.id/', data=data)

    cookies_dict = dict(session.cookies)

    with open("cookies.json", "w") as f:
        json.dump(cookies_dict, f, indent=4)

    return response, cookies_dict

def afterlogin():
    response = session.get('https://mahasiswa.udb.ac.id/')
    with open("afterlogin.html", "w", encoding="utf-8") as f:
        f.write(response.text)
    return response

def main():
    response = session.get('https://mahasiswa.udb.ac.id/main')
    with open("main.html", "w", encoding="utf-8") as f:
        f.write(response.text)
    return response



async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Mengambil captcha...")

    token, image_base64 = captcha()
    save_captcha_image(image_base64)

    context.user_data['token'] = token

    with open("captcha.png", "rb") as img:
        await update.message.reply_photo(img, caption="Masukkan angka captcha yang terlihat pada gambar:")

    return CAPTCHA


async def handle_captcha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['captcha'] = update.message.text
    await update.message.reply_text("Masukkan username (NIM) Anda:")
    return USERNAME


async def handle_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['username'] = update.message.text
    await update.message.reply_text("Masukkan password Anda:")
    return PASSWORD


async def handle_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['password'] = update.message.text

    username   = context.user_data['username']
    password   = context.user_data['password']
    token      = context.user_data['token']
    captcha_r  = context.user_data['captcha']

    await update.message.reply_text("Mencoba login...")

    try:
        res, cookies_dict = login(username, password, token, captcha_r)

        with open("login.html", "w", encoding="utf-8") as f:
            f.write(res.text)

        if res.status_code == 200:
            cookies_info = "\n".join([f"  {k}: {v}" for k, v in cookies_dict.items()])
            await update.message.reply_text(
                f"Login berhasil! (Status: {res.status_code})\n"
                f"Username: {username}\n\n"
                f"Cookies tersimpan di cookies.json:\n{cookies_info}"
            )

            await update.message.reply_text("Redirect ke mahasiswa.udb.ac.id...")
            afterlogin()

            await update.message.reply_text("Mengambil halaman main...")
            main_res = main()
            await update.message.reply_text(f"main.html disimpan (Status: {main_res.status_code})")
        else:
            await update.message.reply_text(
                f"Login gagal! (Status: {res.status_code})\n"
                "Coba lagi dengan /start"
            )
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Proses login dibatalkan. Ketik /start untuk memulai lagi.")
    return ConversationHandler.END



if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CAPTCHA:   [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_captcha)],
            USERNAME:  [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_username)],
            PASSWORD:  [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_password)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)

    print("Bot berjalan... Tekan Ctrl+C untuk berhenti.")
    app.run_polling()
