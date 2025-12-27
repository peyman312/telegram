import asyncio
import logging
import os
import json
from pathlib import Path
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton, ReplyKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application, ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler, ContextTypes, filters
)

# تنظیمات مستقیم (برای اطمینان از کارکرد در محیط پارس‌پک)
TOKEN = "2123990609:AAEq12cBf0c1snDNvDW8iNQUmknTXg1qMMo"
SITE_URL = "https://designeryas.com"
ADMIN_ID = 990167242
USERS_FILE = "users.json"

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("bot")

# حالات ربات
MAIN, SUB, ASK_PHONE, ASK_NAME, ASK_COLLAB_NAME, ASK_COLLAB_TIME, ASK_OTHER_SERVICE_DESC = range(7)
ADMIN_BROADCAST_TEXT = 100

MAIN_OPTS = [
    ("طراحی سایت", "main_web"),
    ("تبلیغات هدفمند", "main_ads"),
    ("طراحی لوگو", "main_logo"),
    ("ادمین شبکه‌های اجتماعی", "main_admin"),
    ("انجام میدم (همکار)", "main_collab"),
    ("سایر خدمات", "main_other"),
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
    "main_other": [
        ("ساخت ربات تلگرام", "sub_other_bot"),
        ("سایر خدمات متفرقه", "sub_other_misc"),
    ],
}

def load_users():
    if Path(USERS_FILE).exists():
        try:
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: return {}
    return {}

def save_users(users):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def add_user(user_id, username=None, first_name=None):
    users = load_users()
    uid = str(user_id)
    if uid not in users:
        users[uid] = {"id": user_id, "username": username, "first_name": first_name, "joined_at": datetime.now().isoformat()}
        save_users(users)
    return users

def rows_of_buttons(pairs, cols=2, extra=None):
    rows = []
    for i in range(0, len(pairs), cols):
        chunk = pairs[i:i+cols]
        rows.append([InlineKeyboardButton(t, callback_data=d) for t, d in chunk])
    if extra: rows.append(extra)
    return InlineKeyboardMarkup(rows)

# منوی دکمه‌ای دائمی
MAIN_MENU_KEYBOARD = ReplyKeyboardMarkup([[KeyboardButton("🏠 منوی اصلی")]], resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    add_user(user.id, user.username, user.first_name)
    context.user_data.clear()
    kb = rows_of_buttons(MAIN_OPTS)
    msg = "سلام 👋 به ربات طراحی یاس خوش آمدید. یکی از گزینه‌ها را انتخاب کنید:"
    if update.message:
        await update.message.reply_text(msg, reply_markup=kb)
        await update.message.reply_text("برای دسترسی سریع به منوی اصلی، از دکمه زیر استفاده کنید:", reply_markup=MAIN_MENU_KEYBOARD)
    else:
        await update.callback_query.edit_message_text(msg, reply_markup=kb)
    return MAIN

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ شما دسترسی به این بخش را ندارید.")
        return ConversationHandler.END
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 ارسال پیام همگانی", callback_data="admin_broadcast")],
        [InlineKeyboardButton("📊 تعداد کاربران", callback_data="admin_stats")],
        [InlineKeyboardButton("🔄 بازگشت به منو", callback_data="admin_back")],
    ])
    await update.message.reply_text("🔐 پنل مدیریت طراحی یاس:", reply_markup=kb)

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "admin_broadcast":
        await q.edit_message_text("📢 لطفاً متن پیام همگانی خود را ارسال کنید (می‌توانید از عکس یا فایل هم استفاده کنید):")
        return ADMIN_BROADCAST_TEXT
    elif q.data == "admin_stats":
        count = len(load_users())
        await q.edit_message_text(f"📊 تعداد کل کاربران ربات: {count}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ بازگشت", callback_data="admin_back")]]))
    elif q.data == "admin_back":
        return await start(update, context)
    return ConversationHandler.END

async def admin_broadcast_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text
    uids = [int(uid) for uid in load_users().keys()]
    s, f = 0, 0
    await update.message.reply_text(f"⏳ در حال ارسال پیام به {len(uids)} کاربر...")
    for uid in uids:
        try:
            await context.bot.send_message(chat_id=uid, text=txt, parse_mode=ParseMode.MARKDOWN)
            s += 1
        except: f += 1
    await update.message.reply_text(f"✅ عملیات ارسال پایان یافت.\n✔️ موفق: {s}\n❌ ناموفق: {f}")
    return ConversationHandler.END

async def on_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    if data == "main_collab":
        context.user_data["category"] = "همکاری"
        await q.edit_message_text("🧩 لطفاً نام پروژه یا تخصص خود را وارد کنید:")
        return ASK_COLLAB_NAME
    
    context.user_data["category"] = next((t for t, d in MAIN_OPTS if d == data), data)
    subs = SUB_OPTS.get(data, [])
    
    extra = [InlineKeyboardButton("⬅️ بازگشت", callback_data="back_to_main")]
    if data == "main_web":
        extra.insert(0, InlineKeyboardButton("💰 مشاهده قیمت‌ها", url="https://designeryas.com/services/%d8%ae%d8%af%d9%85%d8%a7%d8%aa-%d8%b7%d8%b1%d8%a7%d8%ad%db%8c-%d8%b3%d8%a7%db%8c%d8%aa/"))
    
    await q.edit_message_text(f"✅ بخش انتخاب شده: {context.user_data['category']}\nلطفاً یکی از زیرگزینه‌ها را انتخاب کنید:", reply_markup=rows_of_buttons(subs, extra=extra))
    return SUB

async def on_sub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "back_to_main": return await start(update, context)
    
    context.user_data["service"] = next((t for pairs in SUB_OPTS.values() for (t, d) in pairs if d == q.data), q.data)
    await q.delete_message()
    
    if q.data in ["sub_other_bot", "sub_other_misc"]:
        await context.bot.send_message(chat_id=q.message.chat_id, text="📝 لطفاً توضیحات کامل خود را جهت خدمات مد نظر بنویسید:", reply_markup=ReplyKeyboardRemove())
        return ASK_OTHER_SERVICE_DESC
    
    kb = ReplyKeyboardMarkup([[KeyboardButton("📲 ارسال شماره موبایل", request_contact=True)]], resize_keyboard=True, one_time_keyboard=True)
    await context.bot.send_message(chat_id=q.message.chat_id, text="📱 لطفا شماره موبایل خود را ارسال کنید یا بنویسید:", reply_markup=kb)
    return ASK_PHONE

async def ask_other_service_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["description"] = update.message.text
    kb = ReplyKeyboardMarkup([[KeyboardButton("📲 ارسال شماره موبایل", request_contact=True)]], resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text("✅ توضیحات ثبت شد. حالا شماره موبایل خود را ارسال کنید:", reply_markup=kb)
    return ASK_PHONE

async def ask_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["phone"] = update.message.contact.phone_number if update.message.contact else update.message.text
    await update.message.reply_text("👤 لطفاً نام و نام خانوادگی خود را وارد کنید:", reply_markup=ReplyKeyboardRemove())
    return ASK_NAME

async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text
    d = context.user_data
    res = (f"✅ درخواست شما با موفقیت ثبت شد\n\n"
           f"**دسته:** {d.get('category')}\n"
           f"**خدمت:** {d.get('service')}\n"
           f"**نام:** {name}\n"
           f"**شماره:** {d.get('phone')}")
    if d.get('description'): res += f"\n**توضیحات:** {d.get('description')}"
    
    await update.message.reply_text(res, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🌐 مشاهده وب‌سایت ما", url=SITE_URL)]]))
    
    # گزارش به ادمین
    admin_msg = (f"📋 درخواست جدید دریافت شد!\n\n"
                 f"👤 نام: {name}\n"
                 f"📱 شماره: {d.get('phone')}\n"
                 f"📂 دسته: {d.get('category')}\n"
                 f"🎯 خدمت: {d.get('service')}\n"
                 f"📝 توضیحات: {d.get('description', 'ندارد')}")
    try: await context.bot.send_message(chat_id=ADMIN_ID, text=admin_msg)
    except: pass
    
    await update.message.reply_text("می‌توانید درخواست جدیدی ثبت کنید:", reply_markup=rows_of_buttons(MAIN_OPTS))
    context.user_data.clear()
    return MAIN

async def collab_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["project_name"] = update.message.text
    await update.message.reply_text("⏱️ زمان موردنیاز برای انجام پروژه را وارد کنید:")
    return ASK_COLLAB_TIME

async def collab_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = f"✅ اطلاعات همکاری شما ثبت شد\n**پروژه:** {context.user_data.get('project_name')}\n**زمان:** {update.message.text}"
    await update.message.reply_text(txt, reply_markup=rows_of_buttons(MAIN_OPTS))
    context.user_data.clear()
    return MAIN

async def async_main():
    app = ApplicationBuilder().token(TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start), MessageHandler(filters.Regex("🏠 منوی اصلی"), start)],
        states={
            MAIN: [CallbackQueryHandler(on_main, pattern=r"^main_")],
            SUB: [CallbackQueryHandler(on_sub, pattern=r"^sub_"), CallbackQueryHandler(on_back, pattern=r"^back_to_main$")],
            ASK_OTHER_SERVICE_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_other_service_desc)],
            ASK_PHONE: [MessageHandler((filters.TEXT | filters.CONTACT) & ~filters.COMMAND, ask_phone)],
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_name)],
            ASK_COLLAB_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, collab_name)],
            ASK_COLLAB_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, collab_time)],
            ADMIN_BROADCAST_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_broadcast_text)],
        },
        fallbacks=[CommandHandler("start", start), MessageHandler(filters.Regex("🏠 منوی اصلی"), start)],
        name="main_flow",
        persistent=False
    )
    app.add_handler(conv)
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CallbackQueryHandler(admin_callback, pattern=r"^admin_"))
    
    logging.info("🤖 Bot is starting...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(async_main())
