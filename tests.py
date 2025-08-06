"""
בדיקות אוטומטיות לבוט טלגרם
להרצה: python -m pytest tests.py -v
או: python tests.py
"""

import pytest
import asyncio
import os
import tempfile
import sqlite3
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

# ייבוא המודולים שלנו
import config
import messages
import database
import utils
from bot import create_main_keyboard

class TestConfig:
    """בדיקות הגדרות הבוט"""
    
    def test_config_validation_with_valid_token(self):
        """בדיקה שvalidation עובד עם טוכן תקין"""
        with patch.dict(os.environ, {'BOT_TOKEN': 'test_token', 'OWNER_CHAT_ID': '123'}):
            # טען מחדש את הconfig
            import importlib
            importlib.reload(config)
            assert config.validate_config() == True
    
    def test_config_validation_without_token(self):
        """בדיקה שvalidation נכשל ללא טוכן"""
        with patch.dict(os.environ, {}, clear=True):
            import importlib
            importlib.reload(config)
            with pytest.raises(ValueError, match="BOT_TOKEN לא מוגדר"):
                config.validate_config()
    
    def test_button_texts_exist(self):
        """בדיקה שכל הכפתורים מוגדרים"""
        required_buttons = ['whatsapp', 'info', 'callback']
        for button in required_buttons:
            assert button in config.BUTTON_TEXTS
            assert len(config.BUTTON_TEXTS[button]) > 0

class TestMessages:
    """בדיקות הודעות הבוט"""
    
    def test_welcome_message_not_empty(self):
        """בדיקה שהודעת הברכה לא ריקה"""
        assert len(messages.WELCOME_MESSAGE.strip()) > 0
    
    def test_service_info_contains_key_elements(self):
        """בדיקה שמידע השירות מכיל אלמנטים חיוניים"""
        service_info = messages.SERVICE_INFO
        key_elements = ['בוט', 'שירות', 'לקוח']
        
        for element in key_elements:
            assert element in service_info, f"חסר אלמנט: {element}"
    
    def test_notification_message_formatting(self):
        """בדיקה שעיצוב הודעת ההתראה עובד"""
        result = messages.get_notification_message(
            user_name="דני",
            username="danny123", 
            user_id=12345,
            message_text="שלום, רוצה מידע",
            timestamp="01/01/2025 10:00"
        )
        
        assert "דני" in result
        assert "danny123" in result
        assert "12345" in result
        assert "שלום, רוצה מידע" in result
    
    def test_whatsapp_message_formatting(self):
        """בדיקה שהודעת וואטסאפ מעוצבת נכון"""
        phone = "+972501234567"
        result = messages.get_whatsapp_message(phone)
        
        assert "wa.me" in result
        assert "972501234567" in result

class TestDatabase:
    """בדיקות מסד הנתונים"""
    
    @pytest.fixture
    def temp_db(self):
        """יוצר מסד נתונים זמני לבדיקות"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            db_path = tmp.name
        
        db = database.DatabaseManager(db_path)
        yield db
        
        # ניקוי
        os.unlink(db_path)
    
    def test_database_initialization(self, temp_db):
        """בדיקה שמסד הנתונים נוצר נכון"""
        # בדיקה שהטבלאות קיימות
        with sqlite3.connect(temp_db.db_path) as conn:
            cursor = conn.cursor()
            
            # בדיקת טבלת בקשות
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='customer_requests'")
            assert cursor.fetchone() is not None
            
            # בדיקת טבלת סטטיסטיקות
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='bot_stats'")
            assert cursor.fetchone() is not None
    
    def test_save_customer_request(self, temp_db):
        """בדיקה ששמירת בקשה עובדת"""
        request_id = temp_db.save_customer_request(
            user_id=123,
            username="test_user",
            full_name="בדיקה משתמש",
            message_text="הודעת בדיקה"
        )
        
        assert request_id > 0
        
        # בדיקה שנשמר במסד הנתונים
        request = temp_db.get_request_by_id(request_id)
        assert request is not None
        assert request['user_id'] == 123
        assert request['full_name'] == "בדיקה משתמש"
    
    def test_update_request_status(self, temp_db):
        """בדיקה שעדכון סטטוס עובד"""
        # יצירת בקשה
        request_id = temp_db.save_customer_request(
            user_id=123,
            username="test_user", 
            full_name="בדיקה משתמש",
            message_text="הודעת בדיקה"
        )
        
        # עדכון הסטטוס
        success = temp_db.update_request_status(request_id, "completed")
        assert success == True
        
        # בדיקה שהסטטוס עודכן
        request = temp_db.get_request_by_id(request_id)
        assert request['status'] == 'completed'
    
    def test_get_pending_requests(self, temp_db):
        """בדיקה שקבלת בקשות ממתינות עובדת"""
        # יצירת כמה בקשות
        temp_db.save_customer_request(123, "user1", "משתמש 1", "הודעה 1")
        temp_db.save_customer_request(456, "user2", "משתמש 2", "הודעה 2")
        
        # קבלת בקשות ממתינות
        pending = temp_db.get_pending_requests()
        assert len(pending) == 2
        assert all(req['status'] == 'pending' for req in pending)

class TestUtils:
    """בדיקות פונקציות העזר"""
    
    def test_phone_validation(self):
        """בדיקת וולידציה של מספרי טלפון"""
        valid_phones = [
            "+972501234567",
            "0501234567",
            "+1234567890"
        ]
        
        invalid_phones = [
            "123",
            "abc123",
            "",
            "+972"
        ]
        
        for phone in valid_phones:
            assert utils.is_valid_phone(phone), f"טלפון {phone} צריך להיות תקין"
        
        for phone in invalid_phones:
            assert not utils.is_valid_phone(phone), f"טלפון {phone} צריך להיות לא תקין"
    
    def test_email_validation(self):
        """בדיקת וולידציה של אימיילים"""
        valid_emails = [
            "test@example.com",
            "user.name@domain.co.il",
            "123@test.org"
        ]
        
        invalid_emails = [
            "test@",
            "@example.com",
            "notanemail",
            "",
            "test@"
        ]
        
        for email in valid_emails:
            assert utils.is_valid_email(email), f"אימייל {email} צריך להיות תקין"
        
        for email in invalid_emails:
            assert not utils.is_valid_email(email), f"אימייל {email} צריך להיות לא תקין"
    
    def test_extract_contact_info(self):
        """בדיקת חילוץ מידע ליצירת קשר"""
        text = """
        שלום, השם שלי דני כהן
        הטלפון שלי: 0501234567
        האימייל: danny@example.com
        מעוניין במידע על בוטים
        """
        
        info = utils.extract_contact_info(text)
        
        assert "0501234567" in info["phone"]
        assert "danny@example.com" in info["email"]
        assert len(info["name"]) > 0
    
    def test_truncate_text(self):
        """בדיקת קיצור טקסט"""
        long_text = "זה טקסט ארוך מאוד" * 20
        truncated = utils.truncate_text(long_text, max_length=50)
        
        assert len(truncated) <= 50
        assert truncated.endswith("...")
    
    def test_time_formatting(self):
        """בדיקת עיצוב זמן"""
        now = datetime.now()
        formatted = utils.format_timestamp(now, "datetime")
        
        assert "/" in formatted  # יש תאריך
        assert ":" in formatted  # יש שעה
        assert len(formatted) > 10  # לא ריק
    
    def test_user_input_validation(self):
        """בדיקת וולידציה כללית של קלט"""
        # קלט תקין
        result = utils.validate_user_input("שם תקין", "name")
        assert result["valid"] == True
        
        # קלט ריק
        result = utils.validate_user_input("", "general")
        assert result["valid"] == False
        assert "ריק" in result["issues"][0]
        
        # שם קצר מדי
        result = utils.validate_user_input("א", "name")
        assert result["valid"] == False

class TestBotKeyboard:
    """בדיקות מקלדת הבוט"""
    
    def test_main_keyboard_creation(self):
        """בדיקה שיצירת המקלדת הראשית עובדת"""
        keyboard = create_main_keyboard()
        
        assert keyboard is not None
        assert hasattr(keyboard, 'keyboard')
        assert len(keyboard.keyboard) > 0
        
        # בדיקה שכל הכפתורים החיוניים קיימים
        all_buttons = []
        for row in keyboard.keyboard:
            for button in row:
                all_buttons.append(button.text)
        
        required_buttons = ["וואטסאפ", "מידע", "חזור"]
        for req_button in required_buttons:
            assert any(req_button in button for button in all_buttons), f"חסר כפתור: {req_button}"

class TestIntegration:
    """בדיקות אינטגרציה בין רכיבים"""
    
    def test_full_request_flow(self):
        """בדיקה של זרימה מלאה של בקשה"""
        # יצירת מסד נתונים זמני
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            db_path = tmp.name
        
        try:
            db = database.DatabaseManager(db_path)
            
            # שמירת בקשה
            request_id = db.save_customer_request(
                user_id=123,
                username="integration_test",
                full_name="משתמש בדיקה",
                message_text="בדיקת אינטגרציה"
            )
            
            assert request_id > 0
            
            # יצירת הודעת התראה
            notification = messages.get_notification_message(
                user_name="משתמש בדיקה",
                username="integration_test",
                user_id=123,
                message_text="בדיקת אינטגרציה", 
                timestamp=utils.format_timestamp()
            )
            
            assert "משתמש בדיקה" in notification
            assert "בדיקת אינטגרציה" in notification
            
            # עדכון סטטוס
            success = db.update_request_status(request_id, "handled")
            assert success == True
            
        finally:
            os.unlink(db_path)

# פונקציות עזר לבדיקות ידניות

def manual_test_phone_extraction():
    """בדיקה ידנית של חילוץ טלפונים"""
    test_texts = [
        "שלום, הטלפון שלי 050-1234567",
        "צור קשר: +972-50-123-4567", 
        "דני, 0501234567, רוצה מידע",
        "אימייל: test@example.com טל: 052-9876543"
    ]
    
    print("בדיקת חילוץ מידע ליצירת קשר:")
    print("-" * 40)
    
    for text in test_texts:
        info = utils.extract_contact_info(text)
        print(f"טקסט: {text}")
        print(f"טלפון: {info['phone']}")
        print(f"אימייל: {info['email']}")
        print(f"שם: {info['name']}")
        print("-" * 40)

def manual_test_database():
    """בדיקה ידנית של מסד הנתונים"""
    print("בדיקת מסד נתונים:")
    print("-" * 30)
    
    # יצירת מסד זמני
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    
    try:
        db = database.DatabaseManager(db_path)
        
        # שמירת בקשות לדוגמה
        req1 = db.save_customer_request(123, "user1", "דני כהן", "מעוניין בבוט")
        req2 = db.save_customer_request(456, "user2", "שרה לוי", "רוצה מידע על מחירים")
        
        print(f"נשמרו בקשות: {req1}, {req2}")
        
        # קבלת סטטיסטיקות
        stats = db.get_user_stats()
        print(f"סטטיסטיקות: {stats}")
        
        # קבלת בקשות ממתינות
        pending = db.get_pending_requests()
        print(f"בקשות ממתינות: {len(pending)}")
        
        for req in pending:
            print(f"  - {req['full_name']}: {req['message_text'][:30]}...")
    
    finally:
        os.unlink(db_path)
    
    print("בדיקת מסד נתונים הושלמה ✅")

if __name__ == "__main__":
    """הרצה ידנית של הבדיקות"""
    print("🧪 מריץ בדיקות ידניות לבוט")
    print("=" * 50)
    
    try:
        # בדיקות ידניות
        manual_test_phone_extraction()
        manual_test_database()
        
        print("\n✅ כל הבדיקות הידניות עברו בהצלחה!")
        print("\nלהרצת בדיקות אוטומטיות מלאות:")
        print("pip install pytest")
        print("python -m pytest tests.py -v")
        
    except Exception as e:
        print(f"\n❌ שגיאה בבדיקות: {e}")
        import traceback
        traceback.print_exc()
