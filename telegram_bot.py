import os
import time
import requests
from dotenv import load_dotenv
from agent_harness import run

def main():
    load_dotenv()
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    allowed_chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token:
        print("[ERROR] TELEGRAM_BOT_TOKEN not found in environment.")
        return 1

    print("Telegram Bot Listener starting up...")
    print(f"Authorized Chat ID: {allowed_chat_id or 'ANY'}")
    
    # Clear queue on startup by requesting the latest update only
    offset = 0
    try:
        url = f"https://api.telegram.org/bot{token}/getUpdates"
        resp = requests.get(url, params={"offset": -1, "timeout": 1}, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("ok") and data.get("result"):
                offset = data["result"][-1]["update_id"] + 1
                print(f"[INFO] Cleared message queue. Starting offset: {offset}")
    except Exception as e:
        print(f"[WARN] Failed to clear update queue: {e}")
        
    while True:
        try:
            # Long polling: request updates
            url = f"https://api.telegram.org/bot{token}/getUpdates"
            params = {
                "offset": offset,
                "timeout": 30
            }
            # Timeout is slightly longer than the polling timeout
            response = requests.get(url, params=params, timeout=35)
            
            if response.status_code != 200:
                print(f"[WARN] Telegram API error: {response.status_code} - {response.text}")
                time.sleep(5)
                continue
                
            data = response.json()
            if not data.get("ok"):
                print(f"[WARN] Telegram API returned error: {data}")
                time.sleep(5)
                continue
                
            for update in data.get("result", []):
                update_id = update["update_id"]
                offset = update_id + 1
                
                message = update.get("message")
                if not message:
                    continue
                    
                chat = message.get("chat")
                if not chat:
                    continue
                
                chat_id = str(chat.get("id"))
                text = message.get("text")
                if not text:
                    continue
                    
                print(f"[RECV] Message from {chat_id}: {text}")
                
                # Check authorization if allowed_chat_id is specified
                if allowed_chat_id and chat_id != str(allowed_chat_id):
                    print(f"[SECURITY] Unauthorized access attempt from chat ID {chat_id}")
                    # Optionally reply with authorization error
                    reply_url = f"https://api.telegram.org/bot{token}/sendMessage"
                    reply_payload = {
                        "chat_id": chat_id,
                        "text": f"❌ ขออภัยครับ บัญชีนี้ (Chat ID: {chat_id}) ไม่มีสิทธิ์ใช้งานบอทนี้"
                    }
                    try:
                        requests.post(reply_url, json=reply_payload, timeout=10)
                    except Exception as e:
                        print(f"[WARN] Failed to send auth rejection reply: {e}")
                    continue
                
                # Execute agent pipeline
                try:
                    res = run(text)
                    if res.get("ok"):
                        action = res.get("action")
                        output = res.get("output")
                        
                        # Formulate reply
                        if action == "log_sale":
                            reply_text = (
                                f"✅ บันทึกยอดขายสำเร็จ!\n"
                                f"📋 เมนู: {output.get('menu')}\n"
                                f"🥤 จำนวน: {output.get('qty')} ขวด\n"
                                f"💵 ราคา: {output.get('price')} บาท\n"
                                f"💰 ยอดรวม: {output.get('total')} บาท\n"
                                f"🕒 เวลา: {output.get('timestamp')}"
                            )
                        elif action in ("get_today_summary", "get_yesterday_summary", "get_tracelog"):
                            reply_text = output
                        elif action == "send_telegram_report":
                            reply_text = f"📤 ส่งรายงานเรียบร้อย: {output.get('message')}"
                        else:
                            reply_text = f"🤖 ทำการสั่งงานเรียบร้อย: {output}"
                    else:
                        reply_text = f"❌ ไม่สามารถดำเนินการได้: {res.get('error')}"
                except Exception as exc:
                    reply_text = f"💥 เกิดข้อผิดพลาดขณะทำงาน: {exc}"
                
                # Send response back to the user
                send_url = f"https://api.telegram.org/bot{token}/sendMessage"
                send_payload = {
                    "chat_id": chat_id,
                    "text": reply_text
                }
                try:
                    send_resp = requests.post(send_url, json=send_payload, timeout=10)
                    if send_resp.status_code == 200:
                        print(f"[SENT] Reply sent to {chat_id}")
                    else:
                        print(f"[WARN] Failed to send message ({send_resp.status_code}): {send_resp.text}")
                except Exception as exc:
                    print(f"[WARN] Send request failed: {exc}")
                    
        except requests.exceptions.RequestException as e:
            print(f"[WARN] Network connection issue: {e}")
            time.sleep(5)
        except Exception as e:
            print(f"[ERROR] Unexpected error in loop: {e}")
            time.sleep(5)

if __name__ == "__main__":
    import sys
    sys.exit(main())
