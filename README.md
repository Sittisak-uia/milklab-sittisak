---
title: GameLab Solopreneur
emoji: 🎮
colorFrom: purple
colorTo: indigo
sdk: streamlit
sdk_version: 1.35.0
app_file: app.py
pinned: false
---

# GameLab° Solopreneur Starter (Course 69-1)

Template repo สำหรับวิชา 31-407-106-406 : AI for Solopreneurs (พัฒนาต่อยอดสู่ระบบจัดการร้านขายบัตรเติมเกม **GameLab°**)

## เริ่มต้น

1. **Use this template** then Create a new repository (ตั้งชื่อ `milklab-<ชื่อ>`)
2. เปิด **Codespaces** จาก repo ใหม่
3. ตั้ง user-level Codespaces secret `GOOGLE_API_KEY` (ดู Quickstart)
4. รัน `python scripts/verify_setup.py` ใน terminal

## ไฟล์หลัก

| ไฟล์ | Session | คำอธิบาย |
|---|---|---|
| `caption_generator.py` | S1 | สร้างแคปชั่นให้โพสต์โปรโมตสินค้า/บัตรเติมเกม GameLab |
| `sales_logger.py` | S2 | บันทึกยอดขายบัตรเติมเกมลง Google Sheets |
| `agent_harness.py` | S2 | รับคำสั่งภาษาไทย เรียก tool จัดการการขายและแสดง Log |
| `app.py` | S3 | Streamlit RAG chatbot (ผู้ช่วยแชทบอทของร้าน GameLab°) |
| `gamelab_kb.md` | S4 | ฐานข้อมูลความรู้และสินค้าของร้าน GameLab° |
| `PIVOT.md` | S4 | เอกสารวิเคราะห์การ Pivot ธุรกิจจาก MilkLab° สู่ GameLab° |

## เครื่องมือ

- Python 3.11+
- Gemini API (google-genai)
- Streamlit (S3)
- gspread (S2)

## ดูคอร์ส

[course-691-stsw](https://github.com/<owner>/course-691-stsw) (link จะ update ตอนสร้าง public repo)
