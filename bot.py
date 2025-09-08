import asyncio
import logging
import os
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from flask import Flask, jsonify
import threading
import database
try:
    from activity_reporter import create_reporter
except Exception:
    create_reporter = None

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

# אתחול activity reporter
class _NoopReporter:
    def report_activity(self, *args, **kwargs):
        pass

if create_reporter is not None:
    try:
        reporter = create_reporter(
            mongodb_uri="mongodb+srv://mumin:M43M2TFgLfGvhBwY@muminai.tm6x81b.mongodb.net/?retryWrites=true&w=majority&appName=muminAI",
            service_id="srv-d29qsb1r0fns73e52vig",
            service_name="BotForAll"
        )
    except Exception as e:
        logger.warning(f"יצירת reporter נכשלה: {e}")
        reporter = _NoopReporter()
else:
    reporter = _NoopReporter()

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
    try:
        database.log_action(user.id, 'start', {
            'username': user.username,
            'full_name': user.full_name,
        })
    except Exception as e:
        logger.warning(f"לא ניתן לרשום סטטיסטיקת start: {e}")

async def handle_whatsapp(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """טיפול בכפתור וואטסאפ"""
    reporter.report_activity(update.effective_user.id)
    from config import WHATSAPP_NUMBER
    whatsapp_number = WHATSAPP_NUMBER
    whatsapp_link = f"https://wa.me/{whatsapp_number.replace('+', '')}"
    
    await update.message.reply_text(
        f"🔗 **לחץ כאן ליצירת קשר בוואטסאפ:**\n{whatsapp_link}",
        parse_mode='Markdown',
        reply_markup=create_main_keyboard()
    )
    try:
        user = update.effective_user
        database.log_action(user.id, 'open_whatsapp')
    except Exception as e:
        logger.debug(f"log_action open_whatsapp נכשל: {e}")

async def handle_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """טיפול בכפתור מידע"""
    reporter.report_activity(update.effective_user.id)
    await update.message.reply_text(
        SERVICE_INFO,
        parse_mode='Markdown',
        reply_markup=create_main_keyboard()
    )
    try:
        user = update.effective_user
        database.log_action(user.id, 'view_info')
    except Exception as e:
        logger.debug(f"log_action view_info נכשל: {e}")

async def handle_share_friend(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """טיפול בכפתור שלח לחבר"""
    reporter.report_activity(update.effective_user.id)
    share_message = """ראיתי בוט שעוזר לבנות בוטים לטלגרם בקלות ובמחיר נוח.
    
אם מעניין אותך - 
https://t.me/BotForAll4_Bot

(אפשר לפנות ישירות ולספר מה צריך)"""
    
    await update.message.reply_text(
        share_message,
        reply_markup=create_main_keyboard()
    )
    try:
        user = update.effective_user
        database.log_action(user.id, 'share_to_friend')
    except Exception as e:
        logger.debug(f"log_action share_to_friend נכשל: {e}")

async def handle_callback_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """טיפול בבקשה לחזרה"""
    reporter.report_activity(update.effective_user.id)
    user_id = update.effective_user.id
    user_states[user_id] = 'waiting_for_details'
    
    await update.message.reply_text(
        CONTACT_REQUEST,
        reply_markup=create_main_keyboard()
    )
    try:
        database.log_action(user_id, 'callback_request_opened')
    except Exception as e:
        logger.debug(f"log_action callback_request_opened נכשל: {e}")

async def handle_contact_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """טיפול בפרטי קשר שהמשתמש שלח"""
    reporter.report_activity(update.effective_user.id)
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
    
    # רישום למסד הנתונים
    try:
        database.log_action(user_id, 'contact_details_submitted')
        # ניסיון לשמור בקשת לקוח
        database.save_request(user_id, user.username or '', user.full_name or '', message_text)
    except Exception as e:
        logger.debug(f"רישום למסד הנתונים נכשל: {e}")
    
    # איפוס מצב המשתמש
    user_states.pop(user_id, None)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """טיפול בהודעות טקסט רגילות"""
    reporter.report_activity(update.effective_user.id)
    user = update.effective_user
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
        try:
            database.log_action(user.id, 'free_text_message')
        except Exception as e:
            logger.debug(f"log_action free_text_message נכשל: {e}")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """טיפול בשגיאות"""
    logger.error(f"שגיאה: {context.error}")

def _is_admin(user_id: int) -> bool:
    """בודק אם המשתמש הוא האדמין המוגדר"""
    return bool(OWNER_CHAT_ID) and str(user_id) == str(OWNER_CHAT_ID)

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """פקודת אדמין: סטטיסטיקות שימוש שבוע/חודש, כולל מי השתמש"""
    user = update.effective_user
    reporter.report_activity(user.id)
    if not _is_admin(user.id):
        await update.message.reply_text("אין לך הרשאה לפקודה זו ❌")
        return

    try:
        week_users = database.get_active_users(7)
        month_users = database.get_active_users(30)

        def format_users(users, limit=50):
            lines = []
            for idx, u in enumerate(users[:limit], start=1):
                name = u.get('full_name') or 'לא ידוע'
                username = (('@' + u['username']) if u.get('username') else '—')
                lines.append(f"{idx}. {name} {username} | ID: {u.get('user_id')}")
            if len(users) > limit:
                lines.append(f"... ועוד {len(users) - limit} משתמשים")
            return "\n".join(lines) if lines else "(אין נתונים)"

        text = (
            "📊 סטטיסטיקות שימוש\n\n" +
            f"בשבוע האחרון: {len(week_users)} משתמשים ייחודיים\n" +
            format_users(week_users) +
            "\n\n" +
            f"בחודש האחרון: {len(month_users)} משתמשים ייחודיים\n" +
            format_users(month_users)
        )

        await update.message.reply_text(text)
        try:
            database.log_action(user.id, 'admin_stats_view', {
                'week_count': len(week_users),
                'month_count': len(month_users),
            })
        except Exception:
            pass
    except Exception as e:
        logger.error(f"שגיאה בפקודת admin_stats: {e}")
        await update.message.reply_text("אירעה שגיאה בעת שליפת הסטטיסטיקות ❌")

def main():
    """פונקציה ראשית"""
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
    application.add_handler(CommandHandler("admin_stats", admin_stats))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # הוספת error handler
    application.add_error_handler(error_handler)
    
    logger.info("הבוט מתחיל לפעול...")
    
    # הפעלת הבוט
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
