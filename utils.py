"""
פונקציות עזר כלליות לבוט טלגרם
כולל טיפול בזמן, וולידציה, פורמטים וכו'
"""

import re
import json
import asyncio
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List, Union
from functools import wraps
import logging

logger = logging.getLogger(__name__)

# ============== פונקציות זמן ==============

def get_israel_time() -> datetime:
    """מחזיר זמן ישראל נוכחי"""
    israel_tz = timezone(timedelta(hours=3))
    return datetime.now(israel_tz)

def format_timestamp(dt: datetime = None, format_type: str = "full") -> str:
    """מעצב חותמת זמן לתצוגה יפה"""
    if dt is None:
        dt = get_israel_time()
    
    formats = {
        "full": "%d/%m/%Y %H:%M:%S",
        "date": "%d/%m/%Y", 
        "time": "%H:%M",
        "datetime": "%d/%m/%Y %H:%M",
        "iso": "%Y-%m-%dT%H:%M:%S"
    }
    
    return dt.strftime(formats.get(format_type, formats["full"]))

def time_ago(dt: datetime) -> str:
    """מחזיר 'לפני כמה זמן' בעברית"""
    now = get_israel_time()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    diff = now - dt
    seconds = diff.total_seconds()
    
    if seconds < 60:
        return "זה עתה"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        return f"לפני {minutes} דקות" if minutes > 1 else "לפני דקה"
    elif seconds < 86400:
        hours = int(seconds // 3600)
        return f"לפני {hours} שעות" if hours > 1 else "לפני שעה"
    else:
        days = int(seconds // 86400)
        return f"לפני {days} ימים" if days > 1 else "אתמול"

# ============== וולידציה ==============

def is_valid_phone(phone: str) -> bool:
    """בודק אם מספר טלפון תקין"""
    if not phone:
        return False
    
    # ניקוי המספר מתווים מיותרים
    clean_phone = re.sub(r'[^\d+]', '', phone)
    
    # בדיקת פורמטים נפוצים
    patterns = [
        r'^\+972[1-9]\d{8}$',  # ישראל: +972501234567
        r'^05[0-9]\d{7}$',     # ישראל ללא קידומת: 0501234567
        r'^\+1[2-9]\d{9}$',    # ארה"ב: +12345678900
        r'^\+[1-9]\d{7,14}$'   # בינלאומי כללי
    ]
    
    return any(re.match(pattern, clean_phone) for pattern in patterns)

def is_valid_email(email: str) -> bool:
    """בודק אם כתובת אימייל תקינה"""
    if not email:
        return False
        
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email.strip()) is not None

def validate_user_input(text: str, input_type: str = "general") -> Dict[str, Any]:
    """מאמת קלט משתמש ומחזיר תוצאות"""
    result = {"valid": True, "issues": [], "cleaned": text.strip()}
    
    if not text or not text.strip():
        result["valid"] = False
        result["issues"].append("הקלט ריק")
        return result
    
    # בדיקות לפי סוג קלט
    if input_type == "phone":
        if not is_valid_phone(text):
            result["valid"] = False
            result["issues"].append("מספר טלפון לא תקין")
    
    elif input_type == "email":
        if not is_valid_email(text):
            result["valid"] = False
            result["issues"].append("כתובת אימייל לא תקינה")
    
    elif input_type == "name":
        if len(text.strip()) < 2:
            result["valid"] = False
            result["issues"].append("שם קצר מדי")
        elif len(text.strip()) > 50:
            result["valid"] = False
            result["issues"].append("שם ארוך מדי")
    
    # בדיקת תוכן חשוד
    suspicious_patterns = [
        r'http[s]?://',  # קישורים
        r'@[a-zA-Z0-9_]+',  # מנשיינים
        r'\b(?:spam|scam|free money)\b',  # מילות ספאם
    ]
    
    for pattern in suspicious_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            result["issues"].append("תוכן חשוד זוהה")
            break
    
    return result

# ============== עיבוד טקסט ==============

def extract_contact_info(text: str) -> Dict[str, str]:
    """מחלץ מידע ליצירת קשר מטקסט חופשי"""
    info = {"phone": "", "email": "", "name": ""}
    
    # חיפוש טלפון
    phone_patterns = [
        r'(?:\+972|0)(?:[1-9])(?:\d{1,2}[-\s]?)?\d{6,7}',
        r'\+\d{1,3}[\s-]?\d{6,14}'
    ]
    
    for pattern in phone_patterns:
        match = re.search(pattern, text)
        if match:
            info["phone"] = match.group(0)
            break
    
    # חיפוש אימייל
    email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
    if email_match:
        info["email"] = email_match.group(0)
    
    # ניסיון לחלץ שם (מילים ראשונות)
    lines = text.strip().split('\n')
    first_line = lines[0].strip() if lines else ""
    
    # אם השורה הראשונה לא מכילה טלפון או אימייל, כנראה שזה שם
    if first_line and not re.search(r'[@\d+]', first_line[:20]):
        words = first_line.split()[:3]  # עד 3 מילים ראשונות
        if words and all(len(word) > 1 for word in words):
            info["name"] = " ".join(words)
    
    return info

def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """קיצור טקסט עם סיומת"""
    if len(text) <= max_length:
        return text
    return text[:max_length-len(suffix)] + suffix

def clean_text(text: str) -> str:
    """ניקוי טקסט מתווים מיותרים"""
    # הסרת רווחים כפולים
    text = re.sub(r'\s+', ' ', text)
    # הסרת תווים מיוחדים מסוכנים
    text = re.sub(r'[<>&"]', '', text)
    return text.strip()

# ============== דקורטורים ==============

def rate_limit(calls_per_minute: int = 10):
    """דקורטור להגבלת קצב קריאות"""
    def decorator(func):
        calls = []
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            now = datetime.now()
            # ניקוי קריאות ישנות
            calls[:] = [call_time for call_time in calls if now - call_time < timedelta(minutes=1)]
            
            if len(calls) >= calls_per_minute:
                logger.warning(f"Rate limit exceeded for {func.__name__}")
                return None
            
            calls.append(now)
            return await func(*args, **kwargs)
        return wrapper
    return decorator

def retry_on_error(max_retries: int = 3, delay: float = 1.0):
    """דקורטור לניסיון חוזר במקרה של שגיאה"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries:
                        logger.error(f"Failed after {max_retries} attempts: {e}")
                        raise
                    logger.warning(f"Attempt {attempt + 1} failed: {e}, retrying in {delay}s")
                    await asyncio.sleep(delay * (attempt + 1))
        return wrapper
    return decorator

# ============== פורמטים ונתונים ==============

def format_user_info(user) -> str:
    """מעצב מידע על משתמש לתצוגה יפה"""
    parts = []
    
    if hasattr(user, 'full_name') and user.full_name:
        parts.append(f"שם: {user.full_name}")
    
    if hasattr(user, 'username') and user.username:
        parts.append(f"משתמש: @{user.username}")
    
    if hasattr(user, 'id'):
        parts.append(f"מזהה: {user.id}")
    
    return " | ".join(parts)

def safe_json_loads(json_str: str, default: Any = None) -> Any:
    """טעינת JSON בטוחה עם ברירת מחדל"""
    try:
        return json.loads(json_str) if json_str else default
    except (json.JSONDecodeError, TypeError):
        return default

def generate_request_id() -> str:
    """יוצר מזהה ייחודי לבקשה"""
    timestamp = str(int(datetime.now().timestamp()))
    random_data = f"{timestamp}{id(object())}"
    return hashlib.md5(random_data.encode()).hexdigest()[:8]

# ============== בדיקות מערכת ==============

def check_environment() -> Dict[str, bool]:
    """בודק שמשתני הסביבה מוגדרים נכון"""
    import os
    
    checks = {
        "bot_token": bool(os.getenv('BOT_TOKEN')),
        "owner_chat_id": bool(os.getenv('OWNER_CHAT_ID')),
        "python_version": True,  # תמיד True אם הקוד רץ
    }
    
    # בדיקות נוספות
    try:
        import telegram
        checks["telegram_library"] = True
    except ImportError:
        checks["telegram_library"] = False
    
    return checks

async def health_check() -> Dict[str, Any]:
    """בדיקת בריאות המערכת"""
    health = {
        "status": "healthy",
        "timestamp": format_timestamp(),
        "checks": {}
    }
    
    try:
        # בדיקת משתני סביבה
        env_checks = check_environment()
        health["checks"]["environment"] = env_checks
        
        # בדיקת זיכרון (פשוט)
        import psutil
        memory = psutil.virtual_memory()
        health["checks"]["memory"] = {
            "available_mb": round(memory.available / 1024 / 1024, 2),
            "percent_used": memory.percent
        }
        
    except ImportError:
        # psutil לא מותקן
        health["checks"]["memory"] = "unavailable"
    except Exception as e:
        health["status"] = "degraded"
        health["error"] = str(e)
    
    return health

# ============== עזרים כלליים ==============

def get_file_size_mb(file_path: str) -> float:
    """מחזיר גודל קובץ במגהבייטים"""
    try:
        import os
        size_bytes = os.path.getsize(file_path)
        return round(size_bytes / 1024 / 1024, 2)
    except (OSError, FileNotFoundError):
        return 0.0

def create_backup_filename(prefix: str = "backup") -> str:
    """יוצר שם קובץ גיבוי עם זמן"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{timestamp}.db"

async def safe_send_message(bot, chat_id: int, text: str, **kwargs) -> bool:
    """שליחת הודעה בטוחה עם טיפול בשגיאות"""
    try:
        await bot.send_message(chat_id=chat_id, text=text, **kwargs)
        return True
    except Exception as e:
        logger.error(f"Failed to send message to {chat_id}: {e}")
        return False

# ============== קבועים שימושיים ==============

# אמוג'ים נפוצים
EMOJIS = {
    'success': '✅',
    'error': '❌', 
    'warning': '⚠️',
    'info': 'ℹ️',
    'phone': '📱',
    'email': '📧',
    'time': '🕐',
    'user': '👤',
    'message': '💬',
    'whatsapp': '💬',
    'telegram': '🤖'
}

# הודעות מערכת קצרות
SYSTEM_MESSAGES = {
    'processing': 'מעבד... ⏳',
    'done': 'הושלם בהצלחה! ✅',
    'error': 'משהו השתבש ❌',
    'try_again': 'נסה שוב מאוחר יותר',
}
