"""
ניהול בסיס נתונים פשוט לשמירת פניות לקוחות
משתמש ב-SQLite - לא דורש התקנה נוספת
"""

import sqlite3
import json
from datetime import datetime
from typing import Optional, List, Dict
import logging

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_path: str = "bot_data.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """יוצר את טבלאות בסיס הנתונים"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # טבלת פניות לקוחות
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS customer_requests (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        username TEXT,
                        full_name TEXT,
                        message_text TEXT NOT NULL,
                        phone_number TEXT,
                        email TEXT,
                        status TEXT DEFAULT 'pending',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # טבלת סטטיסטיקות
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS bot_stats (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        action TEXT NOT NULL,
                        data TEXT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                conn.commit()
                logger.info("בסיס הנתונים הותחל בהצלחה")
                
        except Exception as e:
            logger.error(f"שגיאה ביצירת בסיס הנתונים: {e}")
    
    def save_customer_request(self, user_id: int, username: str, full_name: str, 
                            message_text: str, phone_number: str = None, 
                            email: str = None) -> int:
        """שומר פנייה חדשה של לקוח"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO customer_requests 
                    (user_id, username, full_name, message_text, phone_number, email)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (user_id, username, full_name, message_text, phone_number, email))
                
                request_id = cursor.lastrowid
                conn.commit()
                
                logger.info(f"פנייה חדשה נשמרה: {request_id}")
                return request_id
                
        except Exception as e:
            logger.error(f"שגיאה בשמירת הפנייה: {e}")
            return -1
    
    def update_request_status(self, request_id: int, status: str) -> bool:
        """מעדכן את סטטוס הפנייה"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE customer_requests 
                    SET status = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (status, request_id))
                
                conn.commit()
                return cursor.rowcount > 0
                
        except Exception as e:
            logger.error(f"שגיאה בעדכון הסטטוס: {e}")
            return False
    
    def get_pending_requests(self) -> List[Dict]:
        """מחזיר את כל הפניות הממתינות"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM customer_requests 
                    WHERE status = 'pending'
                    ORDER BY created_at DESC
                ''')
                
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"שגיאה בקבלת פניות ממתינות: {e}")
            return []
    
    def get_request_by_id(self, request_id: int) -> Optional[Dict]:
        """מחזיר פנייה לפי מזהה"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM customer_requests WHERE id = ?', (request_id,))
                
                row = cursor.fetchone()
                return dict(row) if row else None
                
        except Exception as e:
            logger.error(f"שגיאה בקבלת הפנייה: {e}")
            return None
    
    def log_user_action(self, user_id: int, action: str, data: Dict = None):
        """רושם פעולה של משתמש לסטטיסטיקות"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                data_json = json.dumps(data, ensure_ascii=False) if data else None
                cursor.execute('''
                    INSERT INTO bot_stats (user_id, action, data)
                    VALUES (?, ?, ?)
                ''', (user_id, action, data_json))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"שגיאה בשמירת הסטטיסטיקה: {e}")
    
    def get_user_stats(self, days: int = 30) -> Dict:
        """מחזיר סטטיסטיקות של הבוט"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # סך הפניות
                cursor.execute('SELECT COUNT(*) FROM customer_requests')
                total_requests = cursor.fetchone()[0]
                
                # פניות ממתינות
                cursor.execute("SELECT COUNT(*) FROM customer_requests WHERE status = 'pending'")
                pending_requests = cursor.fetchone()[0]
                
                # פניות מהימים האחרונים
                cursor.execute('''
                    SELECT COUNT(*) FROM customer_requests 
                    WHERE created_at > datetime('now', '-{} days')
                '''.format(days))
                recent_requests = cursor.fetchone()[0]
                
                # משתמשים ייחודיים
                cursor.execute('SELECT COUNT(DISTINCT user_id) FROM customer_requests')
                unique_users = cursor.fetchone()[0]
                
                return {
                    'total_requests': total_requests,
                    'pending_requests': pending_requests,
                    'recent_requests': recent_requests,
                    'unique_users': unique_users
                }
                
        except Exception as e:
            logger.error(f"שגיאה בקבלת סטטיסטיקות: {e}")
            return {}
    
    def cleanup_old_data(self, days: int = 90):
        """מנקה נתונים ישנים"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # מחיקת סטטיסטיקות ישנות
                cursor.execute('''
                    DELETE FROM bot_stats 
                    WHERE timestamp < datetime('now', '-{} days')
                '''.format(days))
                
                deleted_stats = cursor.rowcount
                conn.commit()
                
                logger.info(f"נמחקו {deleted_stats} רשומות סטטיסטיקה ישנות")
                
        except Exception as e:
            logger.error(f"שגיאה בניקוי נתונים: {e}")

    def get_active_user_ids(self, days: int = 7) -> List[int]:
        """מחזיר רשימת מזהי משתמשים ייחודיים שהיו פעילים ב-X הימים האחרונים
        פעילות נמדדת לפי טבלת bot_stats ולפי פניות ב-customer_requests
        """
        try:
            since_expr = f"-" + str(int(days)) + " days"
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # משתמשים מטבלת הסטטיסטיקות
                cursor.execute(
                    """
                    SELECT DISTINCT user_id
                    FROM bot_stats
                    WHERE timestamp > datetime('now', ?)
                    """,
                    (since_expr,)
                )
                stats_users = {row[0] for row in cursor.fetchall()}

                # משתמשים מטבלת הפניות
                cursor.execute(
                    """
                    SELECT DISTINCT user_id
                    FROM customer_requests
                    WHERE created_at > datetime('now', ?)
                    """,
                    (since_expr,)
                )
                request_users = {row[0] for row in cursor.fetchall()}

                all_users = sorted(stats_users.union(request_users))
                return all_users
        except Exception as e:
            logger.error(f"שגיאה בקבלת משתמשים פעילים: {e}")
            return []

    def get_recent_users_with_details(self, days: int = 7) -> List[Dict]:
        """מחזיר משתמשים פעילים ב-X ימים אחרונים כולל פרטי תצוגה וזמן אחרון
        מחזיר רשומות במבנה: {user_id, username, full_name, last_seen}
        """
        try:
            user_ids = self.get_active_user_ids(days)
            if not user_ids:
                return []

            results: List[Dict] = []
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                for uid in user_ids:
                    # שליפת פרטי משתמש (username/full_name) מהבקשה האחרונה אם קיימת
                    cursor.execute(
                        """
                        SELECT username, full_name
                        FROM customer_requests
                        WHERE user_id = ?
                        ORDER BY created_at DESC
                        LIMIT 1
                        """,
                        (uid,)
                    )
                    row = cursor.fetchone()
                    username = row["username"] if row else None
                    full_name = row["full_name"] if row else None

                    # שליפת זמן אחרון מכל הטבלאות
                    cursor.execute(
                        """
                        SELECT MAX(ts) as last_seen
                        FROM (
                            SELECT timestamp as ts FROM bot_stats WHERE user_id = ?
                            UNION ALL
                            SELECT created_at as ts FROM customer_requests WHERE user_id = ?
                        )
                        """,
                        (uid, uid)
                    )
                    ts_row = cursor.fetchone()
                    last_seen = ts_row["last_seen"] if ts_row and ts_row["last_seen"] else None

                    results.append({
                        "user_id": uid,
                        "username": username,
                        "full_name": full_name,
                        "last_seen": last_seen,
                    })

            # מיין לפי זמן אחרון יורד (None בסוף)
            results.sort(key=lambda r: (r["last_seen"] is None, r["last_seen"]), reverse=True)
            return results
        except Exception as e:
            logger.error(f"שגיאה בקבלת פרטי משתמשים פעילים: {e}")
            return []

# אינסטנס גלובלי של מנהל בסיס הנתונים
db = DatabaseManager()

# פונקציות נוחות
def save_request(user_id: int, username: str, full_name: str, message: str) -> int:
    """פונקציה מקוצרת לשמירת פנייה"""
    return db.save_customer_request(user_id, username, full_name, message)

def log_action(user_id: int, action: str, data: Dict = None):
    """פונקציה מקוצרת לרישום פעולה"""
    db.log_user_action(user_id, action, data)

def get_stats() -> Dict:
    """פונקציה מקוצרת לקבלת סטטיסטיקות"""
    return db.get_user_stats()

def get_active_users(days: int = 7) -> List[Dict]:
    """פונקציה מקוצרת לקבלת משתמשים פעילים והפרטים שלהם"""
    return db.get_recent_users_with_details(days)
