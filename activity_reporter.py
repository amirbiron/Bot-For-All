import pymongo
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class ActivityReporter:
    def __init__(self, mongodb_uri, service_id, service_name):
        """
        אתחול activity reporter
        
        Args:
            mongodb_uri: כתובת חיבור למונגו DB
            service_id: מזהה השירות
            service_name: שם השירות
        """
        self.mongodb_uri = mongodb_uri
        self.service_id = service_id
        self.service_name = service_name
        self.client = None
        self.db = None
        self.collection = None
        
        try:
            self.client = pymongo.MongoClient(mongodb_uri)
            self.db = self.client.activity_tracking
            self.collection = self.db.user_activities
            logger.info(f"התחברנו בהצלחה למונגו DB עבור {service_name}")
        except Exception as e:
            logger.error(f"שגיאה בחיבור למונגו DB: {e}")
    
    def report_activity(self, user_id):
        """
        דיווח על פעילות משתמש
        
        Args:
            user_id: מזהה המשתמש
        """
        if not self.collection:
            logger.warning("לא ניתן לדווח על פעילות - אין חיבור למונגו DB")
            return
            
        try:
            activity_record = {
                "user_id": str(user_id),
                "service_id": self.service_id,
                "service_name": self.service_name,
                "timestamp": datetime.utcnow(),
                "date": datetime.utcnow().date().isoformat()
            }
            
            self.collection.insert_one(activity_record)
            logger.debug(f"דווח על פעילות עבור משתמש {user_id}")
            
        except Exception as e:
            logger.error(f"שגיאה בדיווח פעילות: {e}")
    
    def get_weekly_stats(self):
        """
        מחזיר סטטיסטיקות שימוש לשבוע האחרון
        
        Returns:
            dict: מידע על משתמשים פעילים בשבוע האחרון
        """
        if not self.collection:
            return {"error": "אין חיבור למונגו DB"}
            
        try:
            week_ago = datetime.utcnow() - timedelta(days=7)
            
            # ספירת משתמשים ייחודיים בשבוע האחרון
            unique_users = self.collection.distinct(
                "user_id",
                {
                    "service_id": self.service_id,
                    "timestamp": {"$gte": week_ago}
                }
            )
            
            # ספירת כל הפעילויות בשבוע האחרון
            total_activities = self.collection.count_documents({
                "service_id": self.service_id,
                "timestamp": {"$gte": week_ago}
            })
            
            # פעילות לפי יום בשבוע האחרון
            pipeline = [
                {
                    "$match": {
                        "service_id": self.service_id,
                        "timestamp": {"$gte": week_ago}
                    }
                },
                {
                    "$group": {
                        "_id": "$date",
                        "unique_users": {"$addToSet": "$user_id"},
                        "total_activities": {"$sum": 1}
                    }
                },
                {
                    "$project": {
                        "date": "$_id",
                        "unique_users_count": {"$size": "$unique_users"},
                        "total_activities": 1,
                        "_id": 0
                    }
                },
                {"$sort": {"date": -1}}
            ]
            
            daily_stats = list(self.collection.aggregate(pipeline))
            
            return {
                "period": "שבוע אחרון",
                "unique_users": len(unique_users),
                "total_activities": total_activities,
                "daily_breakdown": daily_stats
            }
            
        except Exception as e:
            logger.error(f"שגיאה בקבלת סטטיסטיקות שבועיות: {e}")
            return {"error": str(e)}
    
    def get_monthly_stats(self):
        """
        מחזיר סטטיסטיקות שימוש לחודש האחרון
        
        Returns:
            dict: מידע על משתמשים פעילים בחודש האחרון
        """
        if not self.collection:
            return {"error": "אין חיבור למונגו DB"}
            
        try:
            month_ago = datetime.utcnow() - timedelta(days=30)
            
            # ספירת משתמשים ייחודיים בחודש האחרון
            unique_users = self.collection.distinct(
                "user_id",
                {
                    "service_id": self.service_id,
                    "timestamp": {"$gte": month_ago}
                }
            )
            
            # ספירת כל הפעילויות בחודש האחרון
            total_activities = self.collection.count_documents({
                "service_id": self.service_id,
                "timestamp": {"$gte": month_ago}
            })
            
            # פעילות לפי יום בחודש האחרון
            pipeline = [
                {
                    "$match": {
                        "service_id": self.service_id,
                        "timestamp": {"$gte": month_ago}
                    }
                },
                {
                    "$group": {
                        "_id": "$date",
                        "unique_users": {"$addToSet": "$user_id"},
                        "total_activities": {"$sum": 1}
                    }
                },
                {
                    "$project": {
                        "date": "$_id",
                        "unique_users_count": {"$size": "$unique_users"},
                        "total_activities": 1,
                        "_id": 0
                    }
                },
                {"$sort": {"date": -1}}
            ]
            
            daily_stats = list(self.collection.aggregate(pipeline))
            
            return {
                "period": "חודש אחרון",
                "unique_users": len(unique_users),
                "total_activities": total_activities,
                "daily_breakdown": daily_stats
            }
            
        except Exception as e:
            logger.error(f"שגיאה בקבלת סטטיסטיקות חודשיות: {e}")
            return {"error": str(e)}
    
    def get_user_activity_history(self, user_id, days=30):
        """
        מחזיר היסטוריית פעילות של משתמש ספציפי
        
        Args:
            user_id: מזהה המשתמש
            days: כמה ימים אחורה לחפש (ברירת מחדל 30)
            
        Returns:
            list: רשימת פעילויות המשתמש
        """
        if not self.collection:
            return {"error": "אין חיבור למונגו DB"}
            
        try:
            days_ago = datetime.utcnow() - timedelta(days=days)
            
            activities = self.collection.find({
                "user_id": str(user_id),
                "service_id": self.service_id,
                "timestamp": {"$gte": days_ago}
            }).sort("timestamp", -1)
            
            return list(activities)
            
        except Exception as e:
            logger.error(f"שגיאה בקבלת היסטוריית משתמש: {e}")
            return {"error": str(e)}

def create_reporter(mongodb_uri, service_id, service_name):
    """
    פונקציה ליצירת activity reporter
    
    Args:
        mongodb_uri: כתובת חיבור למונגו DB
        service_id: מזהה השירות
        service_name: שם השירות
        
    Returns:
        ActivityReporter: מופע של activity reporter
    """
    return ActivityReporter(mongodb_uri, service_id, service_name)