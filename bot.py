import asyncio
import logging
import os
import sys
import atexit
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from flask import Flask, jsonify
import threading
import pymongo
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
MONGODB_URI = "mongodb+srv://mumin:M43M2TFgLfGvhBwY@muminai.tm6x81b.mongodb.net/?retryWrites=true&w=majority&appName=muminAI"
SERVICE_ID = "srv-d29qsb1r0fns73e52vig"

def cleanup_mongo_lock():
    """מנקה את נעילת MongoDB בעת יציאה מהתוכנית"""
    try:
        client = pymongo.MongoClient(MONGODB_URI)
        db = client.bot_locks
        collection = db.service_locks
        
        result = collection.delete_one({"service_id": SERVICE_ID})
        if result.deleted_count > 0:
            logger.info("נעילת MongoDB שוחררה בהצלחה")
        else:
            logger.debug("לא נמצאה נעילה למחיקה")
            
    except Exception as e:
        logger.error(f"שגיאה בשחרור נעילת MongoDB: {e}")

def manage_mongo_lock():
    """מנהל את נעילת MongoDB למניעת ריצה מרובה של הבוט"""
    try:
        client = pymongo.MongoClient(MONGODB_URI)
        db = client.bot_locks
        collection = db.service_locks
        
        # יצירת אינדקס ייחודי על service_id אם לא קיים
        try:
            collection.create_index("service_id", unique=True)
        except:
            pass  # האינדקס כבר קיים
        
        # ניסיון ליצור מסמך נעילה
        lock_document = {
            "service_id": SERVICE_ID,
            "locked_at": datetime.utcnow(),
            "process_info": {
                "pid": os.getpid() if hasattr(os, 'getpid') else None,
                "host": os.environ.get('RENDER_SERVICE_NAME', 'unknown'),
                "instance": os.environ.get('RENDER_INSTANCE_ID', 'unknown')
            }
        }
        
        try:
            collection.insert_one(lock_document)
            logger.info(f"נעילת MongoDB נרכשה בהצלחה עבור {SERVICE_ID}")
            
            # רישום פונקציית הניקוי לרוץ ביציאה
            atexit.register(cleanup_mongo_lock)
            
        except DuplicateKeyError:
            # הנעילה כבר תפוסה על ידי תהליך אחר
            existing_lock = collection.find_one({"service_id": SERVICE_ID})
            if existing_lock:
                locked_time = existing_lock.get('locked_at', 'לא ידוע')
                logger.info(f"תהליך אחר של הבוט כבר רץ (נעול מאז: {locked_time})")
                logger.info("יוצא בצורה נקייה כדי למנוע קונפליקט טלגרם")
            else:
                logger.info("תהליך אחר של הבוט כבר רץ")
            
            sys.exit(0)
            
    except Exception as e:
        logger.error(f"שגיאה בניהול נעילת MongoDB: {e}")
        logger.error("ממשיך בכל זאת - ייתכן שיהיה קונפליקט")
        # לא יוצאים במקרה של שגיאה כדי לא לשבור את הבוט לגמרי

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
    logger.error(f"שגיאה: {context.error}")

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
    
    # יצירת האפליקציה
    application = Application.builder().token(BOT_TOKEN).build()
    
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
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
