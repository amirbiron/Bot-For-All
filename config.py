import os

# הגדרות הבוט - שים כאן את הטוקן שלך מ-@BotFather
BOT_TOKEN = os.getenv('BOT_TOKEN')

# המזהה שלך לקבלת הודעות מהבוט (תמצא ב-@userinfobot)
OWNER_CHAT_ID = os.getenv('OWNER_CHAT_ID')

# מספר וואטסאפ (החלף למספר שלך - בפורמט +972501234567)
WHATSAPP_NUMBER = os.getenv('WHATSAPP_NUMBER', '+972543978620')

# הגדרות כלליות
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
LOG_LEVEL = 'DEBUG' if DEBUG else 'INFO'

# זמן קצוב לפעולות (בשניות)
REQUEST_TIMEOUT = 30
MESSAGE_TIMEOUT = 10

# הגדרות בסיס נתונים (אם נרצה להוסיף בעתיד)
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///bot_data.db')

# בדיקת הגדרות חובה
def validate_config():
    """בודק שכל ההגדרות החובה מוגדרות"""
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN לא מוגדר! הגדר אותו במשתני הסביבה")
    
    if not OWNER_CHAT_ID:
        print("⚠️ אזהרה: OWNER_CHAT_ID לא מוגדר - לא תקבל הודעות מהבוט")
    
    return True

# רשימת פקודות לתפריט הבוט
BOT_COMMANDS = [
    ("start", "התחל שיחה עם הבוט"),
    ("help", "עזרה ומידע על הבוט"),
]

# הגדרות כפתורים
BUTTON_TEXTS = {
    'whatsapp': '💬 צור קשר בוואטסאפ',
    'info': 'ℹ️ מידע על השירות', 
    'callback': '⏳ בקשה שאחזור ללקוח',
    'back': '🔙 חזור לתפריט הראשי'
}
