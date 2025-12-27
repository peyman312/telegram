import asyncio
import logging
import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton, ReplyKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application, ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler, ContextTypes, filters
)

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SITE_URL = os.getenv("SITE_URL", "https://designeryas.com")
if not TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is not set in .env")

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
)
logger = logging.getLogger("bot")

MAIN, SUB, ASK_PHONE, ASK_NAME, ASK_COLLAB_NAME, ASK_COLLAB_TIME = range(6)

MAIN_OPTS = [
    ("طراحی سایت", "main_web"),
    ("تبلیغات هدفمند", "main_ads"),
    ("طراحی لوگو", "main_logo"),
    ("ادمین شبکه‌های اجتماعی", "main_admin"),
    ("انجام میدم (همکار)", "main_collab"),
]
SUB_OPTS = {
    "main_web": [
        ("درخواست سایت خدماتی", "sub_web_service"),
        ("درخواست سایت فروشگاهی", "sub_web_shop"),
        ("درخواست سایت تلفیقی", "sub_web_mix"),
    ],
    "main_ads": [("تبلیغات گوگل ادز", "sub_ads_google"), ("سایر", "sub_ads_other")],
    "main_logo": [("لوگو تلفیقی", "sub_logo_combo"), ("لوگو تایپی", "sub_logo_typo"), ("لوگو نماد", "sub_logo_icon")],
    "main_admin": [("اینستا", "sub_admin_instagram"), ("سایر", "sub_admin_other")],
}

def rows_of_buttons(pairs, cols=2, extra=None):
    rows = []
    for i in range(0, len(pairs), cols):
        chunk = pairs[i:i+cols]
        rows.append([InlineKeyboardButton(t, callback_data=d) for t, d in chunk])
    if extra:
        rows.append(extra)
    return InlineKeyboardMarkup(rows)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    kb = rows_of_buttons(MAIN_OPTS)
    if update.message:
        await update.message.reply_text("سلام 👋 یکی از گزینه‌ها را انتخاب کنید:", reply_markup=kb)
    else:
        await update.callback_query.edit_message_text("سلام 👋 یکی از گزینه‌ها را انتخاب کنید:", reply_markup=kb)
    return MAIN

async def on_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    if data == "main_collab":
        context.user_data["category"] = "انجام میدم (همکار)"
        await q.edit_message_text("🧩 نام پروژه را وارد کنید:", reply_markup=None)
        return ASK_COLLAB_NAME
    context.user_data["category"] = next((t for t, d in MAIN_OPTS if d == data), data)
    subs = SUB_OPTS.get(data, [])
    kb = rows_of_buttons(subs, cols=2, extra=[InlineKeyboardButton("⬅️ بازگشت", callback_data="back_to_main")])
    await q.edit_message_text(f"✅ انتخاب شد: {context.user_data['category']}\nیکی از زیرگزینه‌ها را انتخاب کنید:", reply_markup=kb)
    return SUB

async def on_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    return await start(update, context)

async def on_sub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    if data == "back_to_main":
        return await start(update, context)
    context.user_data["service"] = next(
        (t for pairs in SUB_OPTS.values() for (t, d) in pairs if d == data), data
    )
    # We use a ReplyKeyboardMarkup for the contact button
    contact_kb = ReplyKeyboardMarkup(
        [[KeyboardButton("📲 ارسال شماره موبایل", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    # Since we can't attach ReplyKeyboardMarkup to an edit_message_text (which is for Inline),
    # we send a new message or just inform the user.
    await q.delete_message()
    await context.bot.send_message(
        chat_id=q.message.chat_id,
        text="📱 لطفا با استفاده از دکمه زیر شماره خود را ارسال کنید یا آن را تایپ کنید:",
        reply_markup=contact_kb
    )
    return ASK_PHONE

async def ask_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.contact:
        phone = update.message.contact.phone_number
    else:
        phone = (update.message.text or "").strip()
        if not phone or len(phone) < 7:
            await update.message.reply_text("شماره معتبر نیست. دوباره وارد کن یا از دکمه ارسال شماره استفاده کن:")
            return ASK_PHONE
    
    context.user_data["phone"] = phone
    await update.message.reply_text(
        f"✅ شماره {phone} ثبت شد.\n👤 حالا نام خود را وارد کنید:",
        reply_markup=ReplyKeyboardRemove()
    )
    return ASK_NAME

async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = (update.message.text or "").strip()
    if len(name) < 2:
        await update.message.reply_text("نام خیلی کوتاهه. دوباره وارد کن.")
        return ASK_NAME
    context.user_data["name"] = name
    cat = context.user_data.get("category", "-")
    svc = context.user_data.get("service", "-")
    phone = context.user_data.get("phone", "-")
    txt = ("درخواست شما ثبت شد ✅\n"
           "به زودی با شما تماس می‌گیریم.\n\n"
           f"**دسته:** {cat}\n**خدمت:** {svc}\n**نام:** {name}\n**شماره:** {phone}")
    await update.message.reply_text(
        txt, parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🌐 وب‌سایت ما", url=SITE_URL)]])
    )
    kb = rows_of_buttons(MAIN_OPTS)
    await update.message.reply_text("می‌تونی درخواست جدید ثبت کنی:", reply_markup=kb)
    context.user_data.clear()
    return MAIN

async def collab_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    project = (update.message.text or "").strip()
    if len(project) < 2:
        await update.message.reply_text("نام پروژه معتبر نیست. دوباره وارد کن:")
        return ASK_COLLAB_NAME
    context.user_data["project_name"] = project
    await update.message.reply_text("⏱️ زمان موردنیاز (مثلاً 3 روز، 1 هفته) را وارد کنید:")
    return ASK_COLLAB_TIME

async def collab_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    time_need = (update.message.text or "").strip()
    if len(time_need) < 2:
        await update.message.reply_text("زمان معتبر نیست. دوباره وارد کن:")
        return ASK_COLLAB_TIME
    project = context.user_data.get("project_name", "-")
    txt = ("✅ اطلاعات شما ثبت شد.\n\n"
           f"**نام پروژه:** {project}\n**زمان موردنیاز:** {time_need}")
    await update.message.reply_text(
        txt, parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🌐 مشاهده سایت", url=SITE_URL)]])
    )
    kb = rows_of_buttons(MAIN_OPTS)
    await update.message.reply_text("می‌تونی از منوی زیر ادامه بدی:", reply_markup=kb)
    context.user_data.clear()
    return MAIN

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("لغو شد ❌", reply_markup=ReplyKeyboardRemove())
    context.user_data.clear()
    return ConversationHandler.END

async def async_main() -> None:
    application: Application = ApplicationBuilder().token(TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MAIN: [CallbackQueryHandler(on_main, pattern=r"^main_")],
            SUB: [CallbackQueryHandler(on_sub, pattern=r"^sub_"), CallbackQueryHandler(on_back, pattern=r"^back_to_main$")],
            ASK_PHONE: [MessageHandler((filters.TEXT | filters.CONTACT) & ~filters.COMMAND, ask_phone)],
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_name)],
            ASK_COLLAB_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, collab_name)],
            ASK_COLLAB_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, collab_time)],
        },
        fallbacks=[CommandHandler("cancel", cancel), CallbackQueryHandler(on_back, pattern=r"^back_to_main$")],
        name="lead-flow-inline",
        persistent=False,
    )
    application.add_handler(conv)
    logging.info("🤖 Bot is starting (polling)...")
    await application.initialize()
    await application.start()
    async with application:
        await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(async_main())
