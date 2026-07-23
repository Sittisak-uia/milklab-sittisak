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

from dotenv import load_dotenv
from google import genai
from google.genai import types

import agent_tools

SYSTEM_INSTRUCTION = '''
You are MilkLab Agent Router.
Convert one Thai user message into ONE JSON action.

Allowed actions:
- log_sale(menu, quantity, price)
- get_yesterday_summary()
- send_telegram_report(message, confirm)
- unknown

Return JSON only. No markdown. Numbers numeric.
Schema:
{ "action":..., "arguments":{}, "confidence":0.0, "reason":"<short Thai>" }
'''



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
            model="gemini-2.5-flash",
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
    plan = classify_message(message, api_key)
    write_trace({"stage": "plan", "plan": plan})
    result = dispatch(plan)
    write_trace({"stage": "result", "result": result})
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
