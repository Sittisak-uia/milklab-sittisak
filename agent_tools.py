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


def send_telegram_report(message, confirm):
    if isinstance(confirm, str):
        confirm = confirm.lower() in ("true", "1", "yes", "confirm")
    else:
        confirm = bool(confirm)
    if not confirm:
        return {"ok": False, "error": "Not confirmed"}
    provider = morning_report.send_notification(message)
    return {"ok": True, "provider": provider, "message": message}


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
    "send_telegram_report": {
        "fn": send_telegram_report,
        "args": ("message", "confirm"),
        "coerce": {"message": str},
    },
}

