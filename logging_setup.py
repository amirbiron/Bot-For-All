import logging
import os
import sys
import json
from datetime import datetime, timezone
from typing import Optional, Dict


class _ContextFilter(logging.Filter):
    """מוסיף שדות קונטקסט לכל רשומת לוג כדי להקל על פילטור וניתוח."""

    def __init__(self, context: Optional[Dict[str, str]] = None) -> None:
        super().__init__()
        self.context = context or {}

    def filter(self, record: logging.LogRecord) -> bool:
        # זהות השירות/האינסנטס
        service_id = self.context.get("service_id") or os.getenv("SERVICE_ID", "unknown-service")
        instance_id = self.context.get("instance_id") or os.getenv("RENDER_INSTANCE_ID", f"pid-{os.getpid()}")
        render_service = self.context.get("render_service") or os.getenv("RENDER_SERVICE_NAME", "unknown")

        # הזרקת קונטקסט לתוך הרשומה
        record.service_id = service_id
        record.instance_id = instance_id
        record.render_service = render_service
        return True


class JsonFormatter(logging.Formatter):
    """מעצב לוגים בפורמט JSON ידידותי ל-Log Viewers."""

    def format(self, record: logging.LogRecord) -> str:
        base: Dict[str, object] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "service_id": getattr(record, "service_id", None),
            "instance_id": getattr(record, "instance_id", None),
            "render_service": getattr(record, "render_service", None),
            "pid": record.process,
            "file": record.pathname,
            "line": record.lineno,
            "func": record.funcName,
        }

        if record.exc_info:
            base["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(base, ensure_ascii=False)


def _parse_level(level_str: str) -> int:
    mapping = {
        "CRITICAL": logging.CRITICAL,
        "FATAL": logging.FATAL,
        "ERROR": logging.ERROR,
        "WARNING": logging.WARNING,
        "WARN": logging.WARNING,
        "INFO": logging.INFO,
        "DEBUG": logging.DEBUG,
        "NOTSET": logging.NOTSET,
    }
    return mapping.get((level_str or "").upper(), logging.INFO)


def setup_logging(context: Optional[Dict[str, str]] = None) -> None:
    """אתחול לוגים גלובלי לפי ENV: LOG_LEVEL, LOG_FORMAT=json|text.

    context: מילון עם מזהי service/instance להוספת קונטקסט קבוע.
    """
    log_level = _parse_level(os.getenv("LOG_LEVEL", os.getenv("PY_LOG_LEVEL", "INFO")))
    log_format = (os.getenv("LOG_FORMAT") or ("json" if os.getenv("LOG_JSON", "false").lower() == "true" else "text")).lower()

    root = logging.getLogger()

    # ניקוי handlers קודמים כדי למנוע שיכפול שורות
    for h in list(root.handlers):
        root.removeHandler(h)

    root.setLevel(log_level)

    handler = logging.StreamHandler(stream=sys.stdout)

    # פילטר קונטקסט לכל הרשומות
    handler.addFilter(_ContextFilter(context=context))

    if log_format == "json":
        formatter = JsonFormatter()
    else:
        # פורמט טקסט נוח, כולל קונטקסט בסוף
        fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s [svc=%(service_id)s inst=%(instance_id)s host=%(render_service)s pid=%(process)d]"
        formatter = logging.Formatter(fmt=fmt, datefmt="%Y-%m-%d %H:%M:%S")

    handler.setFormatter(formatter)
    root.addHandler(handler)


def update_log_level(level: str) -> str:
    """עדכון רמת הלוג בזמן ריצה עבור ה-root והלוגרים הפעילים."""
    new_level = _parse_level(level)
    logging.getLogger().setLevel(new_level)
    return logging.getLevelName(new_level)

