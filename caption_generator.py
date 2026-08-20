"""MilkLab Caption Generator (S1).

Usage:
    python caption_generator.py

Reads GOOGLE_API_KEY from env. Generates a Thai caption for a milk menu item.
"""

import os
import sys

# Reconfigure stdout/stderr to handle UTF-8 printing safely on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from dotenv import load_dotenv
from google import genai


PROMPT_TEMPLATE = """\
คุณคือ social media manager ของร้าน GameLab° ร้านขายบัตรเติมเกมและโค้ดเติมเงินออนไลน์ 24 ชั่วโมง

จงเขียนแคปชั่นภาษาไทย 2 ถึง 3 ประโยคโปรโมตสินค้า: {menu}

เงื่อนไข:
- โทนสนุก ใช้คำง่าย ใส่ emoji ได้ เอาใจวัยรุ่นและสายเกมเมอร์
- ต้องมี call-to-action ปิดท้าย เช่น สั่งเลย เติมด่วน หรือ ทักแชทได้เลย
- ห้ามใช้ em dash
"""


def generate_caption(menu: str, api_key: str | None = None) -> str:
    """Generate a Thai caption for the given game top-up item."""
    key = api_key or os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError("GOOGLE_API_KEY not set in env or argument")
    client = genai.Client(api_key=key)
    response = client.models.generate_content(
        model="gemini-3.5-flash",
        contents=PROMPT_TEMPLATE.format(menu=menu),
    )
    return response.text or ""


def main() -> int:
    load_dotenv()
    menu = input("บัตรเติมเกมที่จะโปรโมต: ").strip()
    if not menu:
        print("กรุณาใส่ชื่อสินค้า")
        return 1
    caption = generate_caption(menu)
    print()
    print(caption)
    return 0


if __name__ == "__main__":
    sys.exit(main())
