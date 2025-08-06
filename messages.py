"""
קובץ המכיל את כל ההודעות והטקסטים של הבוט
"""

# הודעות ראשיות
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

# הודעות שגיאה ועזרה
ERROR_MESSAGE = "מצטער, משהו השתבש. אנא נסה שוב מאוחר יותר."

HELP_MESSAGE = """
🤖 **עזרה - איך להשתמש בבוט:**

**האפשרויות הזמינות:**
💬 **צור קשר בוואטסאפ** - מעביר אותך ישירות לשיחה בוואטסאפ
ℹ️ **מידע על השירות** - מידע על השירותים שאני מציע
⏳ **בקשה שאחזור ללקוח** - השאר פרטים ואני אחזור אליך

**פקודות זמינות:**
/start - התחל שיחה חדשה
/help - הצג הודעת עזרה זו

יש לך שאלות? פשוט השאר הודעה ואני אחזור אליך!
"""

DEFAULT_RESPONSE = """
אני כאן לעזור! בחר באחת מהאפשרויות למטה 👇

או השאר הודעה ואני אחזור אליך בהקדם.
"""

# הודעות מערכת
NOTIFICATION_TEMPLATE = """
🔔 **פנייה חדשה מהבוט!**

**מהמשתמש:** {user_name} (@{username})
**מזהה:** {user_id}

**תוכן ההודעה:**
{message_text}

**זמן:** {timestamp}
"""

WHATSAPP_MESSAGE = """
🔗 **לחץ כאן ליצירת קשר בוואטסאפ:**
{whatsapp_link}

אני זמין לענות על כל השאלות שלך!
"""

# הודעות מצב
BOT_STARTING = "הבוט מתחיל לפעול..."
BOT_STOPPING = "הבוט נעצר..."
USER_JOINED = "המשתמש {user_name} התחיל שיחה"

# הודעות דיבאג
DEBUG_USER_STATE = "מצב משתמש {user_id}: {state}"
DEBUG_MESSAGE_RECEIVED = "התקבלה הודעה מ-{user_name}: {message}"
DEBUG_ERROR = "שגיאה ב-{function}: {error}"

# הודעות לפי שלבים
STEPS = {
    'waiting_for_details': {
        'prompt': CONTACT_REQUEST,
        'response': REQUEST_RECEIVED,
        'description': 'ממתין לפרטי קשר מהמשתמש'
    }
}

def get_whatsapp_message(phone_number):
    """מחזיר הודעת וואטסאפ עם הקישור"""
    clean_number = phone_number.replace('+', '').replace('-', '').replace(' ', '')
    whatsapp_link = f"https://wa.me/{clean_number}"
    return WHATSAPP_MESSAGE.format(whatsapp_link=whatsapp_link)

def get_notification_message(user_name, username, user_id, message_text, timestamp):
    """מחזיר הודעת התראה מעוצבת"""
    return NOTIFICATION_TEMPLATE.format(
        user_name=user_name,
        username=username or 'אין username',
        user_id=user_id,
        message_text=message_text,
        timestamp=timestamp
    )
