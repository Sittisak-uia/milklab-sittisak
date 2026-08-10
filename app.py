"""MilkLab RAG Chatbot (S3).

Run locally: streamlit run app.py
Deploy: push to GitHub then Actions deploys to HuggingFace Space
"""

import os
# Set thread limits programmatically before importing numpy/torch to save RAM and avoid interop thread errors
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"

import sys
import uuid
import time
import json
from datetime import datetime

# Reconfigure stdout/stderr to handle UTF-8 printing safely on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import numpy as np
import streamlit as st
from dotenv import load_dotenv
from google import genai
import faiss

# Load environmental variables
load_dotenv()

class GeminiEmbeddingModel:
    """Wrapper to mimic SentenceTransformer using Google GenAI text-embedding-004 API."""
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)

    def encode(self, texts: list[str] | str) -> np.ndarray:
        if isinstance(texts, str):
            texts = [texts]
        
        all_embeddings = []
        batch_size = 250
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            response = self.client.models.embed_content(
                model="gemini-embedding-001",
                contents=batch
            )
            batch_embeddings = [emb.values for emb in response.embeddings]
            all_embeddings.extend(batch_embeddings)
            
        return np.array(all_embeddings).astype("float32")


def log_span(name: str, trace_id: str, start_time: float, end_time: float, input_data: dict, output_data: dict, error: str = None):
    """Log execution span to agent_tracelog.txt for observability."""
    duration_ms = (end_time - start_time) * 1000
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    span_data = {
        "trace_id": trace_id,
        "span_name": name,
        "duration_ms": round(duration_ms, 2),
        "status": "ERROR" if error else "OK",
        "input": input_data,
        "output": output_data
    }
    if error:
        span_data["error"] = error
        
    log_content = json.dumps(span_data, ensure_ascii=False)
    log_line = f"{timestamp} | SPAN | {log_content}\n"
    
    # Write to agent_tracelog.txt
    try:
        with open("agent_tracelog.txt", "a", encoding="utf-8") as f:
            f.write(log_line)
    except Exception as e:
        print(f"[ERROR] Failed to write to agent_tracelog.txt: {e}")
        
    # Print to stdout/terminal for real-time observability (safely handle encoding fallback)
    try:
        print(f"[TRACE:SPAN:{name.upper()}] {log_content}")
    except Exception:
        try:
            print(f"[TRACE:SPAN:{name.upper()}] {log_content.encode('utf-8', errors='replace').decode('ascii', errors='replace')}")
        except Exception:
            pass


@st.cache_resource
def load_index(filepath: str, mtime: float):
    """โหลดไฟล์ md, split เป็น chunk, encode ด้วย Gemini Embedding API,
    สร้าง faiss index. Cache จะถูกเคลียร์เมื่อไฟล์มีการอัปเดต (mtime เปลี่ยน)

    Returns: (model, index, chunks_list)
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found at: {filepath}")

    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()

    # Split by double newlines to segment by sections/paragraphs
    raw_chunks = text.split("\n\n")
    chunks = [c.strip() for c in raw_chunks if c.strip()]

    # Encode using Gemini gemini-embedding-001 API (saves significant memory/RAM)
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY not found in environment settings.")
        
    model = GeminiEmbeddingModel(api_key=api_key)
    embeddings = model.encode(chunks)

    # Create L2 Distance FAISS index
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings)

    return model, index, chunks


def retrieve_top_k(query: str, model, index, chunks: list[str], k: int = 3, trace_id: str = None) -> list[str]:
    """encode query, search index, return top-k chunks"""
    start_time = time.time()
    error = None
    retrieved_chunks = []
    try:
        # Encode query
        query_vector = model.encode([query]).astype("float32")
        # Search index
        distances, indices = index.search(query_vector, k)
        # Retrieve mapped chunks
        for idx in indices[0]:
            if 0 <= idx < len(chunks):
                retrieved_chunks.append(chunks[idx])
        return retrieved_chunks
    except Exception as e:
        error = str(e)
        raise e
    finally:
        end_time = time.time()
        if trace_id:
            log_span(
                name="retrieve_top_k",
                trace_id=trace_id,
                start_time=start_time,
                end_time=end_time,
                input_data={"query": query, "k": k},
                output_data={"retrieved_chunks": retrieved_chunks},
                error=error
            )


def generate_answer(query: str, context_chunks: list[str], trace_id: str = None) -> str:
    """ส่ง query + context ไป Gemini, return answer

    Hint: build prompt that says "ตอบจากข้อมูลต่อไปนี้เท่านั้น ถ้าไม่มีใน context ให้บอกว่าไม่รู้"
    """
    start_time = time.time()
    error = None
    answer = ""
    try:
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError("GOOGLE_API_KEY not found in environment settings.")

        client = genai.Client(api_key=api_key)

        # Build prompt enforcing context restrictions and adding menu listing flexibility
        context_text = "\n\n".join(context_chunks)
        prompt = f"""คุณคือผู้ช่วยตอบคำถามของร้าน MilkLab° โดยใช้ข้อมูลต่อไปนี้ในการตอบเท่านั้น:
---
{context_text}
---

เงื่อนไข:
- ตอบคำถามโดยใช้ข้อมูลจาก Context ข้างต้นเท่านั้น
- หากลูกค้าขอให้แนะนำเมนู หรือถามเกี่ยวกับรายการเมนูทั้งหมด ให้แนะนำหรือระบุรายการเมนูที่มีอยู่ใน Context ได้เลย
- ถ้าไม่มีข้อมูลเกี่ยวกับเรื่องที่ถามใน Context เลย ให้บอกตรงๆ ว่า "ขออภัยด้วยครับ ฉันไม่มีข้อมูลเรื่องนี้" หรือ "ไม่ทราบครับ" ห้ามเดาหรือจินตนาการคำตอบเองนอกเหนือจากข้อมูลใน Context เด็ดขาด
- ตอบอย่างเป็นกันเองและสุภาพในภาษาไทย

คำถาม: {query}
"""
        response = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=prompt,
        )
        answer = response.text or "ขออภัยด้วยครับ ไม่สามารถสร้างคำตอบได้"
        return answer
    except Exception as e:
        error = str(e)
        raise e
    finally:
        end_time = time.time()
        if trace_id:
            log_span(
                name="generate_answer",
                trace_id=trace_id,
                start_time=start_time,
                end_time=end_time,
                input_data={"query": query, "context_chunks": context_chunks},
                output_data={"answer": answer},
                error=error
            )


def main():
    st.set_page_config(page_title="MilkLab° RAG-Chatbot", page_icon="🥛")
    
    # Inject Cyberpunk CSS Styling with High Contrast Readability
    st.markdown("""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Sarabun:wght@300;400;600;700&display=swap');
            
            html, body, [class*="css"], .stApp {
                font-family: 'Orbitron', 'Sarabun', sans-serif;
                background-color: #0c0f17 !important;
                color: #e2e8f0 !important;
            }
            
            .main-title {
                font-family: 'Orbitron', sans-serif;
                font-weight: 900;
                font-size: 3rem !important;
                text-align: center;
                text-transform: uppercase;
                letter-spacing: 3px;
                background: linear-gradient(90deg, #ff007f 0%, #00f3ff 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                text-shadow: 0 0 10px rgba(255, 0, 127, 0.4), 0 0 20px rgba(0, 243, 255, 0.2);
                margin-top: 1.5rem !important;
                margin-bottom: 0.2rem !important;
            }
            
            .caption-text {
                color: #00f3ff !important;
                text-align: center;
                font-size: 1.1rem !important;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 1px;
                text-shadow: 0 0 8px rgba(0, 243, 255, 0.3);
                margin-bottom: 2.5rem !important;
            }
            
            /* Chat message design */
            div[data-testid="stChatMessage"] {
                background-color: #121824 !important;
                border-radius: 14px !important;
                padding: 1.2rem !important;
                margin-bottom: 1.2rem !important;
                transition: all 0.3s ease !important;
            }
            
            /* User message: Dark blue background, neon cyan border and text */
            div[data-testid="stChatMessage"][data-testid*="user"] {
                background-color: #0b1a29 !important;
                border: 2px solid #00f3ff !important;
                box-shadow: 0 0 12px rgba(0, 243, 255, 0.2) !important;
            }
            div[data-testid="stChatMessage"][data-testid*="user"] * {
                color: #e2f5ff !important;
            }
            
            /* Assistant message: Dark violet/magenta background, neon pink border and text */
            div[data-testid="stChatMessage"][data-testid*="assistant"] {
                background-color: #1a0f21 !important;
                border: 2px solid #ff007f !important;
                box-shadow: 0 0 12px rgba(255, 0, 127, 0.2) !important;
            }
            div[data-testid="stChatMessage"][data-testid*="assistant"] * {
                color: #ffe6f2 !important;
            }
            
            /* Expander styling */
            .stExpander {
                background-color: #161c28 !important;
                border: 1px solid #323d52 !important;
                border-radius: 10px !important;
                box-shadow: none !important;
            }
            
            .stExpander div[role="button"] {
                color: #00f3ff !important;
                font-weight: 600 !important;
                font-family: 'Orbitron', 'Sarabun', sans-serif !important;
            }
            
            .stExpander div[role="button"]:hover {
                color: #ff007f !important;
            }
            
            .stExpander p, .stExpander span, .stExpander li {
                color: #cbd5e0 !important;
            }
            
            /* Spinner customization */
            div[data-testid="stSpinner"] i {
                border-color: #00f3ff transparent transparent !important;
            }
            
            /* Chat Input container */
            div[data-testid="stChatInput"] {
                background-color: transparent !important;
            }
            
            div[data-testid="stChatInput"] textarea {
                background-color: #121824 !important;
                color: #ffffff !important;
                border: 1.5px solid #00f3ff !important;
                box-shadow: 0 0 8px rgba(0, 243, 255, 0.15) !important;
                border-radius: 10px !important;
            }
            
            div[data-testid="stChatInput"] textarea:focus {
                border: 1.5px solid #ff007f !important;
                box-shadow: 0 0 12px rgba(255, 0, 127, 0.3) !important;
            }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("<h1 class='main-title'>MilkLab° RAG-Chatbot</h1>", unsafe_allow_html=True)
    st.markdown("<p class='caption-text'>ร้าน MilkLab° ยินดีให้บริการ</p>", unsafe_allow_html=True)

    # Resolve path relative to this script's directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Try menu_kd.md first, fall back to menu_kb.md
    filepath = os.path.join(current_dir, "menu_kd.md")
    if not os.path.exists(filepath):
        filepath = os.path.join(current_dir, "menu_kb.md")
        
    if not os.path.exists(filepath):
        st.error(f"Neither menu_kd.md nor menu_kb.md was found in: {current_dir}")
        st.stop()
        
    # Get last modification time of the file to invalidate cache if updated
    mtime = os.path.getmtime(filepath)

    try:
        model, index, chunks = load_index(filepath, mtime)
    except NotImplementedError as exc:
        st.error(f"TODO not implemented: {exc}")
        st.stop()
    except Exception as exc:
        st.error(f"Error loading index: {exc}")
        st.stop()

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    if prompt := st.chat_input("ถามอะไรเกี่ยวกับ MilkLab"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)

        with st.chat_message("assistant"):
            with st.spinner("กำลังค้นข้อมูล..."):
                # Generate unique trace ID for this request flow
                trace_id = uuid.uuid4().hex
                
                try:
                    context = retrieve_top_k(prompt, model, index, chunks, trace_id=trace_id)
                    answer = generate_answer(prompt, context, trace_id=trace_id)
                    
                    st.write(answer)
                    st.session_state.messages.append({"role": "assistant", "content": answer, "context": context})
                except Exception as exc:
                    if "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc):
                        friendly_error = "⚠️ ขออภัยด้วยครับ โควตาการใช้งานชั่วคราวเต็มแล้ว (Gemini API 429 Rate Limit) รบกวนคุณลูกค้ารอประมาณ 30 วินาทีแล้วลองส่งคำถามใหม่อีกครั้งนะครับ"
                    else:
                        friendly_error = f"💥 เกิดข้อผิดพลาดของระบบ: {exc}"
                    st.error(friendly_error)
                    st.session_state.messages.append({"role": "assistant", "content": friendly_error})


if __name__ == "__main__":
    main()
