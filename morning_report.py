"""MilkLab Morning Report.

Reads sales data from Google Sheets and sends a morning summary report
via Telegram or LINE bot.
"""

import base64
import json
import os
import sys
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


import gspread
import requests
from dotenv import load_dotenv

load_dotenv()


def get_gspread_client() -> gspread.Client:
    """Get authenticated gspread client from environment variables.

    Supports both raw JSON in GOOGLE_SHEETS_CREDENTIALS and
    base64-encoded JSON in GOOGLE_SERVICE_ACCOUNT_JSON_B64.
    """
    creds_b64 = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON_B64")
    creds_json = os.environ.get("GOOGLE_SHEETS_CREDENTIALS")

    raw_json = None
    if creds_b64:
        try:
            raw_json = base64.b64decode(creds_b64).decode("utf-8")
        except Exception:
            raw_json = creds_b64
    elif creds_json:
        if not creds_json.strip().startswith("{"):
            try:
                raw_json = base64.b64decode(creds_json).decode("utf-8")
            except Exception:
                raw_json = creds_json
        else:
            raw_json = creds_json

    if not raw_json:
        raise RuntimeError("No Google Sheets credentials found in environment (GOOGLE_SHEETS_CREDENTIALS or GOOGLE_SERVICE_ACCOUNT_JSON_B64)")

    try:
        creds_dict = json.loads(raw_json)
        return gspread.service_account_from_dict(creds_dict)
    except Exception as exc:
        raise RuntimeError(f"Failed to load Google Sheets credentials: {exc}")


def fetch_sales_data() -> list[dict]:
    """Fetch sales records from Google Sheet."""
    gc = get_gspread_client()

    sheet_id = os.environ.get("GOOGLE_SHEETS_ID") or os.environ.get("SPREADSHEET_ID")
    sheet_name = os.environ.get("SPREADSHEET_NAME") or "MilkLab"

    try:
        if sheet_id:
            sh = gc.open_by_key(sheet_id)
        else:
            try:
                sh = gc.open(sheet_name)
            except gspread.exceptions.SpreadsheetNotFound:
                sh = gc.open("MilkLab Sales")
        worksheet = sh.sheet1
        return worksheet.get_all_records()
    except Exception as exc:
        raise RuntimeError(f"Cannot access Google Sheet: {exc}")


def generate_report(records: list[dict]) -> str:
    """Generate human-readable morning report text from sales records."""
    if not records:
        return (
            "☀️ Morning Report - MilkLab° ☀️\n"
            "📅 รายงานสรุปยอดขาย\n\n"
            "⚠️ ยังไม่มีข้อมูลการขายในระบบ"
        )

    total_revenue = 0.0
    total_qty = 0
    menu_sales = {}

    for row in records:
        try:
            menu = str(row.get("menu") or row.get("Menu") or "ไม่ระบุเมนู")
            qty = int(row.get("qty") or row.get("Qty") or 0)
            total = float(row.get("total") or row.get("Total") or (qty * float(row.get("price", 0))))

            total_revenue += total
            total_qty += qty
            menu_sales[menu] = menu_sales.get(menu, 0) + qty
        except (ValueError, TypeError):
            continue

    top_menu = max(menu_sales.items(), key=lambda x: x[1]) if menu_sales else ("-", 0)

    menu_summary_lines = []
    for menu, qty in sorted(menu_sales.items(), key=lambda x: x[1], reverse=True):
        menu_summary_lines.append(f"  • {menu}: {qty} ขวด")

    summary_text = "\n".join(menu_summary_lines)

    report = (
        f"☀️ Morning Report - MilkLab° ☀️\n"
        f"📅 รายงานสรุปยอดขายประจำเช้า\n"
        f"-----------------------------------\n"
        f"📊 ยอดขายรวม: {total_revenue:,.2f} บาท\n"
        f"🥤 จำนวนรวม: {total_qty} ขวด ({len(records)} รายการ)\n"
        f"🏆 เมนูขายดีที่สุด: {top_menu[0]} ({top_menu[1]} ขวด)\n\n"
        f"📋 สรุปยอดตามเมนู:\n"
        f"{summary_text}\n"
        f"-----------------------------------\n"
        f"ขอให้วันนี้เป็นวันที่ดีในการขายครับ! 🥛✨"
    )

    return report


def send_notification(message: str) -> str:
    """Send report notification via Telegram or LINE bot."""
    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    telegram_chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    line_token = os.environ.get("LINE_CHANNEL_TOKEN")

    if telegram_token and telegram_chat_id:
        url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
        payload = {"chat_id": telegram_chat_id, "text": message}
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200 and resp.json().get("ok"):
            return "telegram"
        raise RuntimeError(f"Telegram notification failed ({resp.status_code}): {resp.text}")

    elif line_token:
        url = "https://api.line.me/v2/bot/message/broadcast"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {line_token}",
        }
        payload = {"messages": [{"type": "text", "text": message}]}
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        if resp.status_code == 200:
            return "line"
        raise RuntimeError(f"LINE notification failed ({resp.status_code}): {resp.text}")

    else:
        raise RuntimeError("No Telegram or LINE credentials provided in environment")


def main() -> int:
    try:
        records = fetch_sales_data()
        report_text = generate_report(records)
        print("[INFO] Morning Report content:")
        print(report_text)

        provider = send_notification(report_text)
        print(f"[OK] Morning Report sent successfully via {provider}")
        return 0
    except Exception as exc:
        print(f"[ERROR] Morning Report failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
