# agent_tools.py
from datetime import datetime
import morning_report
import sales_logger


def _validate_sale(menu, qty, price):
    if qty <= 0:
        return "qty > 0"
    if price < 0:
        return "price >= 0"
    if qty > 500:
        return "qty too large"
    return None


def log_sale(menu, quantity, price):
    err = _validate_sale(menu, quantity, price)
    if err:
        return {"ok": False, "tool": "log_sale", "error": err}
    return sales_logger.append_sale(menu, quantity, price)


def query_sales(date=None):
    records = morning_report.fetch_sales_data()
    if date:
        records = [
            r for r in records
            if str(r.get("timestamp") or r.get("Timestamp") or "").startswith(date)
        ]
    return records


def send_alert(message):
    provider = sales_logger.send_notification(message)
    return {"ok": True, "provider": provider, "message": message}


def get_yesterday_summary():
    from datetime import datetime, timedelta
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    records = query_sales(yesterday)
    return morning_report.generate_report(records)


def get_today_summary():
    today = datetime.now().strftime("%Y-%m-%d")
    records = query_sales(today)
    return morning_report.generate_report(records)


def send_telegram_report(message, confirm):
    if isinstance(confirm, str):
        confirm = confirm.lower() in ("true", "1", "yes", "confirm")
    else:
        confirm = bool(confirm)
    if not confirm:
        return {"ok": False, "error": "Not confirmed"}
    provider = morning_report.send_notification(message)
    return {"ok": True, "provider": provider, "message": message}


def get_tracelog(lines=10):
    try:
        lines = int(lines)
    except (ValueError, TypeError):
        lines = 10
        
    try:
        import os
        if not os.path.exists("agent_tracelog.txt"):
            return "ยังไม่มีข้อมูลใน Log"
            
        with open("agent_tracelog.txt", "r", encoding="utf-8") as f:
            all_lines = f.readlines()
            
        last_lines = all_lines[-lines:]
        return "".join(last_lines).strip()
    except Exception as e:
        return f"เกิดข้อผิดพลาดในการอ่าน Log: {e}"


TOOL_REGISTRY = {
    "log_sale": {
        "fn": log_sale,
        "args": ("menu", "quantity", "price"),
        "coerce": {"menu": str, "quantity": int, "price": float},
    },
    "query_sales": {
        "fn": query_sales,
        "args": ("date",),
        "coerce": {"date": str},
    },
    "send_alert": {
        "fn": send_alert,
        "args": ("message",),
        "coerce": {"message": str},
    },
    "get_yesterday_summary": {
        "fn": get_yesterday_summary,
        "args": (),
        "coerce": {},
    },
    "get_today_summary": {
        "fn": get_today_summary,
        "args": (),
        "coerce": {},
    },
    "send_telegram_report": {
        "fn": send_telegram_report,
        "args": ("message", "confirm"),
        "coerce": {"message": str},
    },
    "get_tracelog": {
        "fn": get_tracelog,
        "args": ("lines",),
        "coerce": {"lines": int},
    },
}

