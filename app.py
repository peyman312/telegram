import asyncio
import logging
import os
import json
from pathlib import Path
from datetime import datetime
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
ADMIN_ID = 990167242  # آیدی ادمین
USERS_FILE = "users.json"  # فایل ذخیره کاربران

if not TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is not set in .env")

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
)
logger = logging.getLogger("bot")

# حالات مختلف ربات
MAIN, SUB, ASK_PHONE, ASK_NAME, ASK_COLLAB_NAME, ASK_COLLAB_TIME, ASK_OTHER_SERVICE_DESC = range(7)
ADMIN_BROADCAST_TEXT = 100  # حالت دریافت متن پیام همگانی

# منوی اصلی (Inline Keyboard)
MAIN_OPTS = [
    ("طراحی سایت", "main_web"),
    ("تبلیغات هدفمند", "main_ads"),
    ("طراحی لوگو", "main_logo"),
    ("ادمین شبکه‌های اجتماعی", "main_admin"),
    ("انجام میدم (همکار)", "main_collab"),
    ("سایر خدمات", "main_other"), # گزینه جدید
]

# زیرمنوها
SUB_OPTS = {
    "main_web": [
        ("درخواست سایت خدماتی", "sub_web_service"),
        ("درخواست سایت فروشگاهی", "sub_web_shop"),
        ("درخواست سایت تلفیقی", "sub_web_mix"),
    ],
    "main_ads": [("تبلیغات گوگل ادز", "sub_ads_google"), ("سایر", "sub_ads_other")],
    "main_logo": [("لوگو تلفیقی", "sub_logo_combo"), ("لوگو تایپی", "sub_logo_typo"), ("لوگو نماد", "sub_logo_icon")],
    "main_admin": [("اینستا", "sub_admin_instagram"), ("سایر", "sub_admin_other")],
    "main_other": [ # زیرمنوی جدید
        ("ساخت ربات تلگرام", "sub_other_bot"),
        ("سایر خدمات متفرقه", "sub_other_misc"),
    ],
}

# ========== توابع کمکی برای مدیریت کاربران ==========

def load_users():
    """بارگذاری لیست کاربران از فایل JSON"""
    if Path(USERS_FILE).exists():
        try:
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_users(users):
    """ذخیره لیست کاربران در فایل JSON"""
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def add_user(user_id, username=None, first_name=None):
    """اضافه کردن کاربر جدید"""
    users = load_users()
    user_id_str = str(user_id)
    if user_id_str not in users:
        users[user_id_str] = {
            "id": user_id,
            "username": username,
            "first_name": first_name,
            "joined_at": datetime.now().isoformat()
        }
        save_users(users)
        logger.info(f"✅ کاربر جدید اضافه شد: {user_id} ({first_name})")
    return users

def get_all_user_ids():
    """دریافت لیست تمام آیدی کاربران"""
    users = load_users()
    return [int(uid) for uid in users.keys()]

# ========== توابع رابط کاربری ==========

def rows_of_buttons(pairs, cols=2, extra=None):
    rows = []
    for i in range(0, len(pairs), cols):
        chunk = pairs[i:i+cols]
        rows.append([InlineKeyboardButton(t, callback_data=d) for t, d in chunk])
    if extra:
        rows.append(extra)
    return InlineKeyboardMarkup(rows)

# دکمه منوی اصلی (Reply Keyboard)
MAIN_MENU_KEYBOARD = ReplyKeyboardMarkup(
    [[KeyboardButton("🏠 منوی اصلی")]],
    resize_keyboard=True,
    one_time_keyboard=False
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور /start - شروع ربات"""
    user_id = update.effective_user.id
    username = update.effective_user.username
    first_name = update.effective_user.first_name
    
    # اضافه کردن کاربر به لیست
    add_user(user_id, username, first_name)
    
    context.user_data.clear()
    kb = rows_of_buttons(MAIN_OPTS)
    
    # اگر پیام از طریق دکمه منوی اصلی یا دستور /start آمد
    if update.message:
        await update.message.reply_text(
            "سلام 👋 یکی از گزینه‌ها را انتخاب کنید:", 
            reply_markup=kb
        )
        # ارسال Reply Keyboard برای منوی دکمه‌ای
        await update.message.reply_text(
            "برای دسترسی سریع به منوی اصلی، از دکمه زیر استفاده کنید:",
            reply_markup=MAIN_MENU_KEYBOARD
        )
    # اگر از طریق Callback Query (مثلاً بازگشت از زیرمنو) آمد
    else:
        await update.callback_query.edit_message_text(
            "سلام 👋 یکی از گزینه‌ها را انتخاب کنید:", 
            reply_markup=kb
        )
    return MAIN

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور /admin - نمایش پنل مدیریت (فقط برای ادمین)"""
    user_id = update.effective_user.id
    
    # بررسی اینکه آیا کاربر ادمین است
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ شما دسترسی به این قابلیت ندارید.")
        return ConversationHandler.END
    
    # نمایش منوی ادمین
    admin_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 ارسال پیام همگانی", callback_data="admin_broadcast")],
        [InlineKeyboardButton("📊 تعداد کاربران", callback_data="admin_stats")],
        [InlineKeyboardButton("🔄 بازگشت به منوی اصلی", callback_data="admin_back")],
    ])
    await update.message.reply_text("🔐 پنل مدیریت:\n\nچه کاری می‌خواهید انجام دهید؟", reply_markup=admin_kb)

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت دکمه‌های پنل ادمین"""
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    
    if user_id != ADMIN_ID:
        await q.edit_message_text("❌ شما دسترسی ندارید.")
        return ConversationHandler.END
    
    if q.data == "admin_broadcast":
        await q.edit_message_text(
            "📢 متن پیام همگانی را وارد کنید:\n\n"
            "(می‌توانید از Markdown استفاده کنید: **بولد** و *ایتالیک*)"
        )
        return ADMIN_BROADCAST_TEXT
    
    elif q.data == "admin_stats":
        users = load_users()
        count = len(users)
        await q.edit_message_text(
            f"📊 آمار کاربران:\n\n"
            f"👥 تعداد کل کاربران: {count}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ بازگشت", callback_data="admin_back")]])
        )
        return ConversationHandler.END
    
    elif q.data == "admin_back":
        return await start(update, context)
    
    return ConversationHandler.END

async def admin_broadcast_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت متن پیام همگانی و ارسال آن"""
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ شما دسترسی ندارید.")
        return ConversationHandler.END
    
    message_text = update.message.text
    user_ids = get_all_user_ids()
    
    if not user_ids:
        await update.message.reply_text("❌ هیچ کاربری برای ارسال پیام وجود ندارد.")
        return ConversationHandler.END
    
    # ارسال پیام به تمام کاربران
    success_count = 0
    failed_count = 0
    
    await update.message.reply_text(f"⏳ در حال ارسال پیام به {len(user_ids)} کاربر...")
    
    for uid in user_ids:
        try:
            await context.bot.send_message(
                chat_id=uid,
                text=message_text,
                parse_mode=ParseMode.MARKDOWN
            )
            success_count += 1
        except Exception as e:
            logger.warning(f"⚠️ خطا در ارسال به {uid}: {str(e)}")
            failed_count += 1
    
    # گزارش نتیجه
    report = (
        f"✅ پیام همگانی ارسال شد!\n\n"
        f"✔️ موفق: {success_count}\n"
        f"❌ ناموفق: {failed_count}\n"
        f"📊 کل: {len(user_ids)}"
    )
    await update.message.reply_text(report)
    
    logger.info(f"📢 پیام همگانی ارسال شد: {success_count} موفق، {failed_count} ناموفق")
    
    return ConversationHandler.END

# ========== توابع فرم درخواست خدمات ==========

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
    
    extra_buttons = [InlineKeyboardButton("⬅️ بازگشت", callback_data="back_to_main")]
    
    # افزودن دکمه قیمت برای طراحی سایت
    if data == "main_web":
        extra_buttons.insert(0, InlineKeyboardButton("💰 قیمت‌ها", url="https://designeryas.com/services/%d8%ae%d8%af%d9%85%d8%a7%d8%aa-%d8%b7%d8%b1%d8%a7%d8%ad%db%8c-%d8%b3%d8%a7%db%8c%d8%aa/"))
        kb = rows_of_buttons(subs, cols=2, extra=extra_buttons)
    else:
        kb = rows_of_buttons(subs, cols=2, extra=[extra_buttons[1]]) # فقط بازگشت
        
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
    
    # اگر زیرمجموعه "سایر خدمات متفرقه" باشد، باید توضیحات را بپرسیم
    if data == "sub_other_misc" or data == "sub_other_bot":
        await q.delete_message()
        await context.bot.send_message(
            chat_id=q.message.chat_id,
            text="📝 لطفاً توضیحات کامل خدمات مد نظر خود را بنویسید:",
            reply_markup=ReplyKeyboardRemove()
        )
        return ASK_OTHER_SERVICE_DESC
    
    # در غیر این صورت، روال عادی درخواست شماره را ادامه می‌دهیم
    contact_kb = ReplyKeyboardMarkup(
        [[KeyboardButton("📲 ارسال شماره موبایل", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await q.delete_message()
    await context.bot.send_message(
        chat_id=q.message.chat_id,
        text="📱 لطفا با استفاده از دکمه زیر شماره خود را ارسال کنید یا آن را تایپ کنید:",
        reply_markup=contact_kb
    )
    return ASK_PHONE

async def ask_other_service_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت توضیحات خدمات متفرقه و سپس درخواست شماره"""
    desc = (update.message.text or "").strip()
    if len(desc) < 10:
        await update.message.reply_text("توضیحات شما خیلی کوتاه است. لطفاً جزئیات بیشتری بنویسید:")
        return ASK_OTHER_SERVICE_DESC
    
    context.user_data["description"] = desc
    
    contact_kb = ReplyKeyboardMarkup(
        [[KeyboardButton("📲 ارسال شماره موبایل", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await update.message.reply_text(
        "✅ توضیحات ثبت شد.\n📱 حالا لطفا با استفاده از دکمه زیر شماره خود را ارسال کنید یا آن را تایپ کنید:",
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
    desc = context.user_data.get("description", "ندارد") # توضیحات جدید
    user_id = update.effective_user.id
    username = update.effective_user.username or "ندارد"
    
    txt = ("درخواست شما ثبت شد ✅\n"
           "به زودی با شما تماس می‌گیریم.\n\n"
           f"**دسته:** {cat}\n**خدمت:** {svc}\n**نام:** {name}\n**شماره:** {phone}")
    
    if desc != "ندارد":
        txt += f"\n**توضیحات:** {desc}"
        
    await update.message.reply_text(
        txt, parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🌐 وب‌سایت ما", url=SITE_URL)]])
    )
    
    # ارسال گزارش به ادمین
    admin_report = (
        f"📋 درخواست جدید دریافت شد!\n\n"
        f"👤 نام: {name}\n"
        f"📱 شماره: {phone}\n"
        f"🔗 یوزرنیم: @{username}\n"
        f"🆔 آیدی: {user_id}\n"
        f"📂 دسته: {cat}\n"
        f"🎯 خدمت: {svc}\n"
        f"📝 توضیحات: {desc}\n"
        f"⏰ زمان: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=admin_report, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"خطا در ارسال گزارش به ادمین: {e}")
    
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
    
    # ConversationHandler برای فرم درخواست خدمات
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start), MessageHandler(filters.Regex("🏠 منوی اصلی"), start)],
        states={
            MAIN: [CallbackQueryHandler(on_main, pattern=r"^main_")],
            SUB: [CallbackQueryHandler(on_sub, pattern=r"^sub_"), CallbackQueryHandler(on_back, pattern=r"^back_to_main$")],
            ASK_OTHER_SERVICE_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_other_service_desc)], # حالت جدید
            ASK_PHONE: [MessageHandler((filters.TEXT | filters.CONTACT) & ~filters.COMMAND, ask_phone)],
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_name)],
            ASK_COLLAB_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, collab_name)],
            ASK_COLLAB_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, collab_time)],
            ADMIN_BROADCAST_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_broadcast_text)],
        },
        fallbacks=[CommandHandler("cancel", cancel), CallbackQueryHandler(on_back, pattern=r"^back_to_main$")],
        name="lead-flow-inline",
        persistent=False,
    )
    
    # ConversationHandler برای پنل ادمین
    admin_conv = ConversationHandler(
        entry_points=[CommandHandler("admin", admin_panel)],
        states={
            ConversationHandler.END: [CallbackQueryHandler(admin_callback, pattern=r"^admin_")],
            ADMIN_BROADCAST_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_broadcast_text)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        name="admin-panel",
        persistent=False,
    )
    
    application.add_handler(conv)
    application.add_handler(admin_conv)
    application.add_handler(CallbackQueryHandler(admin_callback, pattern=r"^admin_"))
    application.add_handler(CommandHandler("start", start)) # برای اطمینان از اینکه /start همیشه کار کند
    
    logging.info("🤖 Bot is starting (polling)...")
    await application.initialize()
    await application.start()
    async with application:
        await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(async_main())
