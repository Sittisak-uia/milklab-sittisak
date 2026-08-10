"""MilkLab Agent Harness (S2.5 STEP 2).

Usage:
    python agent_harness.py --cmd "บันทึกขายนมหมี 2 ขวด ขวดละ 65"

System Prompt Router + Dispatcher:
1. Schema in prompt - ให้ LLM ตอบ JSON ตามฟอร์ม
2. Confidence threshold - หาก confidence < 0.7 จะปรับเป็น action 'unknown'
3. Trace ทุก stage - user_input -> plan -> result
"""

import argparse
import json
import os
import sys
from datetime import datetime

from dotenv import load_dotenv
from google import genai
from google.genai import types

import agent_tools

SYSTEM_INSTRUCTION = '''
You are MilkLab Agent Router.
Convert one Thai user message into ONE JSON action.

Allowed actions:
- log_sale(menu, quantity, price)
- get_today_summary()
- get_yesterday_summary()
- send_telegram_report(message, confirm)
- get_tracelog(lines)
- unknown

Return JSON only. No markdown. Numbers numeric.
Schema:
{ "action":..., "arguments":{}, "confidence":0.0, "reason":"<short Thai>" }
'''



def write_tracelog(stage: str, content: str) -> None:
    """Write agent trace log to agent_tracelog.txt in format:
    YYYY-MM-DD HH:MM | stage | content
    """
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        log_line = f"{timestamp} | {stage} | {content}\n"
        with open("agent_tracelog.txt", "a", encoding="utf-8") as f:
            f.write(log_line)
    except Exception as e:
        print(f"[ERROR] Failed to write to agent_tracelog.txt: {e}", file=sys.stderr)


def format_tracelog_result(result: dict) -> str:
    """Format the result of the tool run for the trace log."""
    if not result.get("ok"):
        return f"เกิดข้อผิดพลาด: {result.get('error')}"
    
    action = result.get("action")
    output = result.get("output")
    
    if action == "log_sale":
        if isinstance(output, dict):
            menu = output.get("menu", "")
            qty = output.get("qty", 0)
            total = output.get("total", 0)
            return f"บันทึก {menu} จำนวน {qty} รายการ (รวม {int(total)} บาท) เรียบร้อยแล้ว"
        return str(output)
    elif action == "get_today_summary":
        return "สรุปยอดขายประจำวัน เรียบร้อยแล้ว"
    elif action == "get_yesterday_summary":
        return "สรุปยอดขายประจำวันเมื่อวาน เรียบร้อยแล้ว"
    elif action == "get_tracelog":
        return "แสดง log การทำงาน เรียบร้อยแล้ว"
    elif action == "send_telegram_report":
        if isinstance(output, dict):
            return f"ส่งรายงาน '{output.get('message')}' สำเร็จ"
        return "ส่งรายงานสำเร็จ"
    else:
        return str(output).split('\n')[0] if output else "ดำเนินการเรียบร้อย"


def write_trace(data: dict) -> None:
    """Print trace log for debugging."""
    stage = data.get("stage", "")
    print(f"[TRACE:{stage}] {json.dumps(data, ensure_ascii=False)}")


def classify_message(cmd: str, api_key: str | None = None) -> dict:
    """Classify Thai user message using Gemini with System Prompt Router."""
    key = api_key or os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError("GOOGLE_API_KEY not set in env or argument")

    client = genai.Client(api_key=key)

    try:
        response = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=cmd,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
            ),
        )
        text = response.text.strip() if response.text else "{}"
    except Exception as exc:
        text = json.dumps({
            "action": "unknown",
            "arguments": {},
            "confidence": 0.0,
            "reason": f"API error: {exc}",
        })

    # Parse JSON
    try:
        if text.startswith("```"):
            lines = text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        plan = json.loads(text)
    except Exception:
        plan = {
            "action": "unknown",
            "arguments": {},
            "confidence": 0.0,
            "reason": "ไม่สามารถแปลงผลลัพธ์เป็น JSON ได้",
        }

    # Confidence threshold: < 0.7 -> unknown
    confidence = float(plan.get("confidence", 0.0))
    if confidence < 0.7:
        plan["action"] = "unknown"
        if not plan.get("reason"):
            plan["reason"] = f"Confidence ต่ำเกินไป ({confidence} < 0.7)"

    return plan


def parse_command(cmd: str, api_key: str | None = None) -> dict:
    """Parse command wrapper for backward compatibility."""
    plan = classify_message(cmd, api_key)
    return {
        "tool": plan.get("action", "unknown"),
        "args": plan.get("arguments", {}),
        "confidence": plan.get("confidence", 0.0),
        "reason": plan.get("reason", ""),
    }


def dispatch(plan: dict) -> dict:
    """Dispatch action plan to appropriate tool in TOOL_REGISTRY."""
    action = plan.get("action", "unknown")
    args = plan.get("arguments", {})

    if action == "unknown" or action not in agent_tools.TOOL_REGISTRY:
        reason = plan.get("reason", "ไม่เข้าใจคำสั่ง")
        return {
            "ok": False,
            "action": action,
            "error": f"Unknown action or low confidence: {reason}",
        }

    tool_info = agent_tools.TOOL_REGISTRY[action]
    fn = tool_info["fn"]
    expected_args = tool_info.get("args", ())
    coercions = tool_info.get("coerce", {})

    call_args = {}
    for arg_name in expected_args:
        val = args.get(arg_name)
        if val is not None and arg_name in coercions:
            try:
                val = coercions[arg_name](val)
            except (ValueError, TypeError):
                pass
        call_args[arg_name] = val

    try:
        res = fn(**call_args)
        return {"ok": True, "action": action, "output": res}
    except Exception as exc:
        return {"ok": False, "action": action, "error": str(exc)}


def dispatch_tool(tool_call: dict) -> str:
    """Dispatch wrapper for backward compatibility."""
    plan = {
        "action": tool_call.get("tool", "unknown"),
        "arguments": tool_call.get("args", {}),
    }
    res = dispatch(plan)
    if res.get("ok"):
        return str(res.get("output"))
    return f"Error: {res.get('error')}"


def run(message: str, api_key: str | None = None) -> dict:
    """Run full pipeline with stage tracing: user_input -> plan -> result."""
    write_trace({"stage": "user_input", "input": message})
    write_tracelog("user_input", message)

    plan = classify_message(message, api_key)
    write_trace({"stage": "plan", "plan": plan})

    llm_content = json.dumps({
        "tool": plan.get("action", "unknown"),
        "args": plan.get("arguments", {})
    }, ensure_ascii=False)
    write_tracelog("llm_response", llm_content)

    result = dispatch(plan)
    write_trace({"stage": "result", "result": result})

    result_content = format_tracelog_result(result)
    write_tracelog("tool_result", result_content)

    return result


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="MilkLab Agent Harness")
    parser.add_argument("--cmd", required=True, help="คำสั่งภาษาไทย")
    args = parser.parse_args()

    print(f"[USER] {args.cmd}")
    res = run(args.cmd)

    action = res.get("action", "unknown")
    if res.get("ok"):
        print(f"[TOOL] {action} -> {res.get('output')}")
    else:
        print(f"[ERROR] {action} -> {res.get('error')}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
