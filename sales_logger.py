"""MilkLab Sales Logger (S2).

Usage:
    python sales_logger.py --menu "นมหมีฮอกไกโด" --qty 2 --price 65

Reads GOOGLE_SHEETS_CREDENTIALS and TELEGRAM_BOT_TOKEN (or LINE_CHANNEL_TOKEN) from env.
Appends row [timestamp, menu, qty, price, total] to a Google Sheet,
then sends a notification via Telegram or LINE bot.

นักศึกษาต้องเติม TODO ใน 4 จุดด้านล่างใน Session 2 Lab 1.3
"""

import argparse
import json
import os
import sys
from datetime import datetime

import gspread
import requests
from dotenv import load_dotenv

load_dotenv()


def append_to_sheet(menu: str, qty: int, price: float) -> dict:
    """TODO 1: ใช้ gspread เปิด Sheet ของตัวเอง แล้ว append_row ด้วย [timestamp, menu, qty, price, total]

    Returns dict {timestamp, menu, qty, price, total} ที่ append แล้ว
    Raises RuntimeError ถ้า credentials ไม่มี หรือ Sheet ไม่ accessible
    """
    creds_json = os.environ.get("GOOGLE_SHEETS_CREDENTIALS")
    if not creds_json:
        raise RuntimeError("GOOGLE_SHEETS_CREDENTIALS missing from environment")

    try:
        creds_dict = json.loads(creds_json)
        gc = gspread.service_account_from_dict(creds_dict)
    except Exception as exc:
        raise RuntimeError(f"Failed to load Google Sheets credentials: {exc}")

    client_email = creds_dict.get("client_email", "")
    sheet_id = os.environ.get("SPREADSHEET_ID") or os.environ.get("GOOGLE_SHEETS_ID")
    sheet_url = os.environ.get("SPREADSHEET_URL")
    sheet_name = os.environ.get("SPREADSHEET_NAME") or os.environ.get("GOOGLE_SHEETS_NAME") or "MilkLab"

    try:
        if sheet_id:
            sh = gc.open_by_key(sheet_id)
        elif sheet_url:
            sh = gc.open_by_url(sheet_url)
        else:
            sh = gc.open(sheet_name)
        worksheet = sh.sheet1
    except gspread.exceptions.SpreadsheetNotFound:
        raise RuntimeError(
            f"Sheet '{sheet_name}' not found. Please create a Google Sheet named '{sheet_name}' and share it with '{client_email}'"
        )
    except Exception as exc:
        raise RuntimeError(f"Cannot open Google Sheet: {exc}")

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total = qty * price
    row_data = [timestamp, menu, qty, price, total]

    try:
        worksheet.append_row(row_data)
    except Exception as exc:
        raise RuntimeError(f"Failed to append row to Google Sheet: {exc}")

    return {
        "timestamp": timestamp,
        "menu": menu,
        "qty": qty,
        "price": price,
        "total": total,
    }



def send_notification(message: str) -> str:
    """TODO 2: ส่ง message ไปยัง Telegram bot (ใช้ TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID)
    หรือ LINE bot (ใช้ LINE_CHANNEL_TOKEN) เลือกตัวใดตัวหนึ่ง

    Returns: provider name ที่ใช้ ("telegram" หรือ "line")
    Raises RuntimeError ถ้า no credentials
    """
    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    telegram_chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    line_token = os.environ.get("LINE_CHANNEL_TOKEN")

    if telegram_token and telegram_chat_id:
        url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
        payload = {"chat_id": telegram_chat_id, "text": message}
        try:
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code == 200 and resp.json().get("ok"):
                return "telegram"
            raise RuntimeError(f"Telegram API response error ({resp.status_code}): {resp.text}")
        except Exception as exc:
            raise RuntimeError(f"Telegram request failed: {exc}")

    elif line_token:
        url = "https://api.line.me/v2/bot/message/broadcast"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {line_token}",
        }
        payload = {"messages": [{"type": "text", "text": message}]}
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=10)
            if resp.status_code == 200:
                return "line"
            raise RuntimeError(f"LINE API response error ({resp.status_code}): {resp.text}")
        except Exception as exc:
            raise RuntimeError(f"LINE request failed: {exc}")

    else:
        raise RuntimeError("No TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID or LINE_CHANNEL_TOKEN in environment")



def main() -> int:
    parser = argparse.ArgumentParser(description="MilkLab Sales Logger")
    parser.add_argument("--menu", required=True, help="ชื่อเมนู")
    parser.add_argument("--qty", type=int, required=True, help="จำนวนขวด")
    parser.add_argument("--price", type=float, required=True, help="ราคาต่อขวด")
    args = parser.parse_args()

    try:
        # TODO 3: เรียก append_to_sheet แล้ว extract total
        row = append_to_sheet(args.menu, args.qty, args.price)
        total = row["total"]
    except Exception as exc:
        print(f"[ERROR] บันทึก Sheet ล้มเหลว: {exc}", file=sys.stderr)
        print("[HINT] ตรวจ GOOGLE_SHEETS_CREDENTIALS และ share Sheet กับ service account email", file=sys.stderr)
        return 1

    try:
        # TODO 4: เรียก send_notification ด้วย message ที่บอกยอดที่บันทึก
        provider = send_notification(f"บันทึก {args.menu} x{args.qty} = {total} บาท")
    except Exception as exc:
        print(f"[WARN] บันทึก Sheet สำเร็จแต่ส่งแจ้งเตือนล้มเหลว: {exc}", file=sys.stderr)
        return 0

    print(f"[OK] บันทึกและแจ้งเตือนผ่าน {provider} เรียบร้อย ยอด {total} บาท")
    return 0


if __name__ == "__main__":
    sys.exit(main())
