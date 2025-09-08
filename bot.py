import asyncio
import logging
import os
import sys
import atexit
import time
import random
from datetime import datetime, timedelta, timezone
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import Conflict
from flask import Flask, jsonify
import threading
import pymongo
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from activity_reporter import create_reporter

# הגדרת לוגים
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# יצירת Flask app
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "bot": "running"})

def run_flask():
    """מפעיל את Flask בחוט נפרד"""
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

# הגדרות מהסביבה
BOT_TOKEN = os.getenv('BOT_TOKEN')
OWNER_CHAT_ID = os.getenv('OWNER_CHAT_ID')

# יצירת activity reporter
reporter = create_reporter(
    mongodb_uri="mongodb+srv://mumin:M43M2TFgLfGvhBwY@muminai.tm6x81b.mongodb.net/?retryWrites=true&w=majority&appName=muminAI",
    service_id="srv-d29qsb1r0fns73e52vig",
    service_name="BotForAll"
)

# MongoDB URI לנעילה
MONGODB_URI = os.environ.get('MONGODB_URI') or "mongodb+srv://mumin:M43M2TFgLfGvhBwY@muminai.tm6x81b.mongodb.net/?retryWrites=true&w=majority&appName=muminAI"
SERVICE_ID = os.environ.get('SERVICE_ID') or "srv-d29qsb1r0fns73e52vig"
INSTANCE_ID = os.environ.get('RENDER_INSTANCE_ID') or f"pid-{os.getpid()}"

# פרמטרים לנעילה (Lease + Heartbeat)
LOCK_LEASE_SECONDS = int(os.environ.get('LOCK_LEASE_SECONDS', '60'))
LOCK_HEARTBEAT_INTERVAL = max(5, int(LOCK_LEASE_SECONDS * 0.4))
LOCK_WAIT_FOR_ACQUIRE = os.environ.get('LOCK_WAIT_FOR_ACQUIRE', 'false').lower() == 'true'
LOCK_ACQUIRE_MAX_WAIT = int(os.environ.get('LOCK_ACQUIRE_MAX_WAIT', '0'))  # 0 = ללא גבול

# אובייקטים גלובליים לניהול heartbeat
_lock_stop_event = threading.Event()
_lock_heartbeat_thread = None

def _ensure_lock_indexes(collection):
    """יוצר אינדקס TTL על expiresAt ואינדקס ייחודי על _id (מובנה)."""
    try:
        # TTL על expiresAt (expireAfterSeconds=0 כדי שיפוג בדיוק בזמן)
        collection.create_index("expiresAt", expireAfterSeconds=0, background=True)
    except Exception as e:
        logger.warning(f"יצירת אינדקס TTL נכשלה/כבר קיים: {e}")

def _start_heartbeat(client):
    """מפעיל heartbeat חוטי שמאריך את ה-lease עד שהבוט נסגר."""
    global _lock_heartbeat_thread

    def _beat():
        collection = client.bot_locks.service_locks
        while not _lock_stop_event.is_set():
            time.sleep(LOCK_HEARTBEAT_INTERVAL)
            now = datetime.now(timezone.utc)
            new_expiry = now + timedelta(seconds=LOCK_LEASE_SECONDS)
            try:
                res = collection.update_one(
                    {"_id": SERVICE_ID, "owner": INSTANCE_ID},
                    {"$set": {"expiresAt": new_expiry, "updatedAt": now}}
                )
                if res.matched_count == 0:
                    logger.error("איבדנו את הנעילה במהלך הריצה - יוצא כדי למנוע קונפליקט")
                    os._exit(0)
            except Exception as e:
                logger.error(f"שגיאה בעדכון heartbeat לנעילה: {e}")
                # נסיון נוסף בסיבוב הבא; אם זה נמשך, ה-TTL ישחרר לבד

    _lock_heartbeat_thread = threading.Thread(target=_beat, daemon=True)
    _lock_heartbeat_thread.start()

def cleanup_mongo_lock():
    """שחרור הנעילה והפסקת heartbeat בעת יציאה."""
    try:
        _lock_stop_event.set()
        client = pymongo.MongoClient(MONGODB_URI)
        db = client.bot_locks
        collection = db.service_locks
        result = collection.delete_one({"_id": SERVICE_ID, "owner": INSTANCE_ID})
        if result.deleted_count > 0:
            logger.info("נעילת MongoDB שוחררה בהצלחה")
        else:
            logger.debug("לא נמצאה נעילה בבעלותנו למחיקה")
    except Exception as e:
        logger.error(f"שגיאה בשחרור נעילת MongoDB: {e}")

def manage_mongo_lock():
    """רכישת נעילה מבוזרת (Lease) עם Heartbeat ו-TTL, עם המתנה אופציונלית לרכישה."""
    try:
        client = pymongo.MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        db = client.bot_locks
        collection = db.service_locks
        _ensure_lock_indexes(collection)

        start_time = time.time()
        attempt = 0
        while True:
            attempt += 1
            now = datetime.now(timezone.utc)
            new_expiry = now + timedelta(seconds=LOCK_LEASE_SECONDS)
            try:
                # שלב 1: נסה לתפוס/להאריך נעילה קיימת שפגה או בבעלותנו (ללא upsert)
                doc = collection.find_one_and_update(
                    {
                        "_id": SERVICE_ID,
                        "$or": [
                            {"expiresAt": {"$lte": now}},
                            {"owner": INSTANCE_ID},
                        ]
                    },
                    {
                        "$set": {
                            "owner": INSTANCE_ID,
                            "host": os.environ.get('RENDER_SERVICE_NAME', 'unknown'),
                            "updatedAt": now,
                            "expiresAt": new_expiry,
                        },
                        "$setOnInsert": {"createdAt": now},
                    },
                    upsert=False,
                    return_document=ReturnDocument.AFTER,
                )

                if doc and doc.get("owner") == INSTANCE_ID:
                    logger.info(f"נעילת MongoDB נרכשה בהצלחה עבור {SERVICE_ID} (instance: {INSTANCE_ID})")
                    _start_heartbeat(client)
                    atexit.register(cleanup_mongo_lock)
                    return

                # שלב 2: אם אין נעילה שתפוג או בבעלותנו, אז ננסה ליצור חדשה באמצעות insert
                try:
                    collection.insert_one(
                        {
                            "_id": SERVICE_ID,
                            "owner": INSTANCE_ID,
                            "host": os.environ.get('RENDER_SERVICE_NAME', 'unknown'),
                            "createdAt": now,
                            "updatedAt": now,
                            "expiresAt": new_expiry,
                        }
                    )
                    logger.info(f"נעילת MongoDB נוצרה ונרכשה בהצלחה עבור {SERVICE_ID} (instance: {INSTANCE_ID})")
                    _start_heartbeat(client)
                    atexit.register(cleanup_mongo_lock)
                    return
                except DuplicateKeyError:
                    # תהליך אחר יצר את הרשומה במקביל — מתייחסים כ"נעילה לא הושגה"
                    pass

                # לא נרכשה - יש בעלים אחר ועדיין בתוקף
                if not LOCK_WAIT_FOR_ACQUIRE:
                    logger.info("תהליך אחר מחזיק בנעילה - יוצא נקי")
                    sys.exit(0)

                # המתנה עם backoff ואקראיות קלה כדי לצמצם מירוצים
                waited = time.time() - start_time
                if LOCK_ACQUIRE_MAX_WAIT and waited >= LOCK_ACQUIRE_MAX_WAIT:
                    logger.error("חרגנו מזמן ההמתנה לנעילה - יוצא כדי למנוע קונפליקט")
                    sys.exit(0)

                sleep_s = min(5.0, 0.5 + random.random())
                if attempt % 20 == 0:
                    logger.info("ממתין לשחרור נעילה מתהליך אחר...")
                time.sleep(sleep_s)
                continue

            except Exception as e:
                logger.error(f"שגיאה בניסיון רכישת נעילת MongoDB: {e}")
                time.sleep(1.0)
                if attempt >= 5 and not LOCK_WAIT_FOR_ACQUIRE:
                    sys.exit(0)

    except Exception as e:
        logger.error(f"שגיאה בניהול נעילת MongoDB: {e}")
        logger.error("לא ניתן להבטיח נעילה - יוצא כדי למנוע קונפליקט")
        sys.exit(0)

# הודעות
WELCOME_MESSAGE = """
היי! 👋 
ברוך הבא לבוט שירות שמקצר תהליכים – בוטים בקלות, שירות באהבה. 
אני כאן לעזור לך לקבל בוט טלגרם בהתאמה אישית, במהירות וביחס אנושי.

בחר אפשרות בתפריט למטה ✨
"""

SERVICE_INFO = """
אני מפתח בוטים לטלגרם – בהתאמה לכל מטרה ותקציב. 
הבוטים שלי מתאימים לעסקים, ערוצים, מועדונים, יוזמות פרטיות – או לכל מי שרוצה אוטומציה, סדר ונוחות בטלגרם.

🚀 מה אפשר לבקש?
• בוט למענה אוטומטי (שאלות/שליחת הודעות/שמירת מידע)
• בוטים לניהול תורים או משימות
• חיבור לאתרים חיצוניים או שירותי צד ג׳
• בוטים בהתאמה אישית – לפי רעיון שלך!

👥 למי זה מתאים?
- כל מי שרוצה לייעל את העבודה, להיראות מקצועי או לחסוך זמן.

———
נבנה באהבה ע"י אמיר – מפתח בוטים בטלגרם 🤖✨
"""

CONTACT_REQUEST = """
תודה על הפנייה! 🙏

אנא שתף אותי:
• את השם שלך
• איך אפשר ליצור קשר (טלפון/אימייל)  
• מה בדיוק אתה מחפש?

אני אחזור אליך בהקדם האפשרי!
"""

REQUEST_RECEIVED = """
תודה! 📩 הבקשה שלך התקבלה.

אני אחזור אליך בהקדם האפשרי.
בינתיים, אפשר ליצור קשר גם דרך וואטסאפ ⬇️
"""

# משתנה לאחסון מצב המשתמש
user_states = {}

def create_main_keyboard():
    """יוצר את המקלדת הראשית"""
    keyboard = [
        [KeyboardButton("💬 צור קשר בוואטסאפ")],
        [KeyboardButton("ℹ️ מידע על השירות")],
        [KeyboardButton("⏳ בקשה שאחזור ללקוח")],
        [KeyboardButton("📤 שלח לחבר שרוצה בוט")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """פונקציית /start"""
    user = update.effective_user
    reporter.report_activity(user.id)
    logger.info(f"המשתמש {user.full_name} התחיל שיחה")
    
    # אפס את מצב המשתמש
    user_states[user.id] = None
    
    await update.message.reply_text(
        WELCOME_MESSAGE,
        reply_markup=create_main_keyboard()
    )

async def handle_whatsapp(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """טיפול בכפתור וואטסאפ"""
    from config import WHATSAPP_NUMBER
    whatsapp_number = WHATSAPP_NUMBER
    whatsapp_link = f"https://wa.me/{whatsapp_number.replace('+', '')}"
    
    await update.message.reply_text(
        f"🔗 **לחץ כאן ליצירת קשר בוואטסאפ:**\n{whatsapp_link}",
        parse_mode='Markdown',
        reply_markup=create_main_keyboard()
    )

async def handle_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """טיפול בכפתור מידע"""
    await update.message.reply_text(
        SERVICE_INFO,
        parse_mode='Markdown',
        reply_markup=create_main_keyboard()
    )

async def handle_share_friend(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """טיפול בכפתור שלח לחבר"""
    share_message = """ראיתי בוט שעוזר לבנות בוטים לטלגרם בקלות ובמחיר נוח.
    
אם מעניין אותך - 
https://t.me/BotForAll4_Bot

(אפשר לפנות ישירות ולספר מה צריך)"""
    
    await update.message.reply_text(
        share_message,
        reply_markup=create_main_keyboard()
    )

async def handle_callback_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """טיפול בבקשה לחזרה"""
    user_id = update.effective_user.id
    user_states[user_id] = 'waiting_for_details'
    
    await update.message.reply_text(
        CONTACT_REQUEST,
        reply_markup=create_main_keyboard()
    )

async def handle_contact_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """טיפול בפרטי קשר שהמשתמש שלח"""
    user = update.effective_user
    user_id = user.id
    message_text = update.message.text
    
    # שליחת הודעה למשתמש
    await update.message.reply_text(
        REQUEST_RECEIVED,
        reply_markup=create_main_keyboard()
    )
    
    # שליחת הודעה לבעל הבוט
    if OWNER_CHAT_ID:
        notification = f"""
🔔 **פנייה חדשה מהבוט!**

**מהמשתמש:** {user.full_name} (@{user.username or 'אין username'})
**מזהה:** {user_id}

**תוכן ההודעה:**
{message_text}

**זמן:** {update.message.date.strftime('%d/%m/%Y %H:%M')}
"""
        try:
            await context.bot.send_message(chat_id=OWNER_CHAT_ID, text=notification, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"שגיאה בשליחת הודעה לבעל הבוט: {e}")
    
    # איפוס מצב המשתמש
    user_states.pop(user_id, None)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """טיפול בהודעות טקסט רגילות"""
    user = update.effective_user
    reporter.report_activity(user.id)
    text = update.message.text
    
    # טיפול בכפתורים ראשונים - לפני בדיקת מצב המשתמש
    if text == "💬 צור קשר בוואטסאפ":
        await handle_whatsapp(update, context)
    elif text == "ℹ️ מידע על השירות":
        await handle_info(update, context)
    elif text == "⏳ בקשה שאחזור ללקוח":
        await handle_callback_request(update, context)
    elif text == "📤 שלח לחבר שרוצה בוט":
        await handle_share_friend(update, context)
    # רק אחרי זה בודק אם המשתמש במצב המתנה לפרטים
    elif user.id in user_states and user_states[user.id] == 'waiting_for_details':
        await handle_contact_details(update, context)
    else:
        await update.message.reply_text(
            "אני כאן לעזור! בחר באחת מהאפשרויות למטה 👇",
            reply_markup=create_main_keyboard()
        )

async def stats_week(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """הצגת סטטיסטיקות שבועיות - רק לבעל הבוט"""
    user = update.effective_user
    
    # בדיקה שזה בעל הבוט
    if str(user.id) != OWNER_CHAT_ID:
        await update.message.reply_text("אין לך הרשאה לצפות בסטטיסטיקות.")
        return
    
    reporter.report_activity(user.id)
    
    # קבלת סטטיסטיקות שבועיות
    stats = reporter.get_weekly_stats()
    
    if "error" in stats:
        await update.message.reply_text(f"שגיאה בקבלת סטטיסטיקות: {stats['error']}")
        return
    
    # עיצוב הודעת הסטטיסטיקות
    message = f"""📊 **סטטיסטיקות שימוש - {stats['period']}**

👥 **משתמשים ייחודיים:** {stats['unique_users']}
🔄 **סך הפעילויות:** {stats['total_activities']}

📅 **פירוט יומי:**"""
    
    # הוספת פירוט יומי
    for day_stat in stats['daily_breakdown'][:7]:  # רק 7 הימים האחרונים
        date_formatted = day_stat['date']
        users_count = day_stat['unique_users_count']
        activities_count = day_stat['total_activities']
        message += f"\n• {date_formatted}: {users_count} משתמשים, {activities_count} פעילויות"
    
    await update.message.reply_text(message, parse_mode='Markdown')

async def stats_month(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """הצגת סטטיסטיקות חודשיות - רק לבעל הבוט"""
    user = update.effective_user
    
    # בדיקה שזה בעל הבוט
    if str(user.id) != OWNER_CHAT_ID:
        await update.message.reply_text("אין לך הרשאה לצפות בסטטיסטיקות.")
        return
    
    reporter.report_activity(user.id)
    
    # קבלת סטטיסטיקות חודשיות
    stats = reporter.get_monthly_stats()
    
    if "error" in stats:
        await update.message.reply_text(f"שגיאה בקבלת סטטיסטיקות: {stats['error']}")
        return
    
    # עיצוב הודעת הסטטיסטיקות
    message = f"""📊 **סטטיסטיקות שימוש - {stats['period']}**

👥 **משתמשים ייחודיים:** {stats['unique_users']}
🔄 **סך הפעילויות:** {stats['total_activities']}

📅 **פירוט יומי (10 הימים האחרונים):**"""
    
    # הוספת פירוט יומי - רק 10 הימים האחרונים
    for day_stat in stats['daily_breakdown'][:10]:
        date_formatted = day_stat['date']
        users_count = day_stat['unique_users_count']
        activities_count = day_stat['total_activities']
        message += f"\n• {date_formatted}: {users_count} משתמשים, {activities_count} פעילויות"
    
    await update.message.reply_text(message, parse_mode='Markdown')

async def admin_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """הצגת עזרה לבעל הבוט"""
    user = update.effective_user
    
    # בדיקה שזה בעל הבוט
    if str(user.id) != OWNER_CHAT_ID:
        await update.message.reply_text("אין לך הרשאה לצפות בפקודות ניהול.")
        return
    
    reporter.report_activity(user.id)
    
    help_message = """🔧 **פקודות ניהול זמינות:**

📊 `/stats_week` - סטטיסטיקות שימוש לשבוע האחרון
📊 `/stats_month` - סטטיסטיקות שימוש לחודש האחרון
❓ `/admin_help` - הצגת רשימת פקודות זו

**הערה:** כל הפקודות זמינות רק לבעל הבוט.

**להגדרת פקודות ב-BotFather:**
```
start - התחל שיחה עם הבוט
stats_week - סטטיסטיקות שבועיות (אדמין)
stats_month - סטטיסטיקות חודשיות (אדמין) 
admin_help - עזרה לאדמין (אדמין)
```"""
    
    await update.message.reply_text(help_message, parse_mode='Markdown')

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """טיפול בשגיאות"""
    err = context.error
    # במקרה של Conflict שמגיע מעומק ה-Polling, נתעד ברמה נמוכה יותר
    if isinstance(err, Conflict) or (hasattr(err, "message") and "Conflict" in str(err)):
        logger.warning("זוהתה התנגשות getUpdates (Conflict) - ייתכן שתהליך אחר התחיל. נסגר בחן.")
        return
    logger.error(f"שגיאה: {err}")

async def _post_init(application: Application) -> None:
    """Callback אסינכרוני שירוץ בעת אתחול האפליקציה בתוך הלופ של PTB.
    משמש להסרת webhook מבלי לפתוח/לסגור event loop חיצוני."""
    try:
        await application.bot.delete_webhook(drop_pending_updates=True)
        logger.info("Webhook הוסר בהצלחה (אם היה)")
    except Exception as e:
        logger.warning(f"נכשלה הסרת webhook: {e}")

def main():
    """פונקציה ראשית"""
    # ניהול נעילת MongoDB למניעת ריצה מרובה
    manage_mongo_lock()
    
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN לא מוגדר!")
        return
    
    if not OWNER_CHAT_ID:
        logger.warning("OWNER_CHAT_ID לא מוגדר - לא תתקבלנה הודעות")
    
    # הפעלת Flask בחוט נפרד
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    logger.info("Flask server started")
    
    # יצירת האפליקציה + הסרת webhook בתוך ה-loop של PTB באמצעות post_init
    application = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .post_init(_post_init)
        .build()
    )
    
    # הוספת handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats_week", stats_week))
    application.add_handler(CommandHandler("stats_month", stats_month))
    application.add_handler(CommandHandler("admin_help", admin_help))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # הוספת error handler
    application.add_error_handler(error_handler)
    
    logger.info("הבוט מתחיל לפעול...")
    
    # הפעלת הבוט
    # הבטחת event loop ברירת מחדל עבור Python 3.13 לפני קריאה פנימית ל-asyncio.get_event_loop()
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())
    try:
        application.run_polling(drop_pending_updates=True)
    except Conflict:
        # אם בכל זאת קרה, נסיים בשקט כדי לא לזהם לוגים
        logger.info("Conflict מזוהה בעת run_polling - יוצא נקי (instance אחר פעיל)")
        return

if __name__ == '__main__':
    main()
