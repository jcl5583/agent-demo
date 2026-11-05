import os
import json
import time
import uuid
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("LLM_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL"),
    timeout=30,
)

tools = [{
    "type": "function",
    "function": {
        "name": "add",
        "description": "计算两个数相加",
        "parameters": {
            "type": "object",
            "properties": {
                "a": {"type": "number", "description": "第一个数"},
                "b": {"type": "number", "description": "第二个数"},
            },
            "required": ["a", "b"],
        },
    },
}, {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "查询指定城市今天的天气",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "城市名，例如 北京"},
            },
            "required": ["city"],
        },
    },
}]


def add(a, b):
    return a + b


_attempts = {}        # 记录每个城市被调了几次

def get_weather(city):
    _attempts[city] = _attempts.get(city, 0) + 1

    if city == "火星":
        raise RuntimeError("网络超时：无法连接天气服务")

    if city == "天津" and _attempts[city] == 1:
        raise RuntimeError("接口超时（模拟网络抖动）")

    fake = {"北京": "晴，18℃", "上海": "多云，22℃", "成都": "小雨，15℃", "天津": "阴，12℃"}
    return fake.get(city, "查不到这个城市")

def call_tool(name, args, retries=2):
    if name not in TOOLS_BY_NAME:
        return f"工具调用失败：不存在名为 {name} 的工具"

    func = TOOLS_BY_NAME[name]
    for attempt in range(1, retries + 2):        # 1 次原始 + retries 次重试
        try:
            return func(**args)
        except Exception as e:
            print(f"    ⚠ 工具 {name} 第 {attempt} 次失败：{e}")
    return f"工具执行失败：{name} 连续 {retries + 1} 次都没成功，请换个方式回答用户"

TOOLS_BY_NAME = {"add": add, "get_weather": get_weather}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TRACE_DIR = os.path.join(BASE_DIR, "traces")
TRACE_FILE = os.path.join(TRACE_DIR, "traces.jsonl")


def save_trace(trace):
    os.makedirs(TRACE_DIR, exist_ok=True)
    with open(TRACE_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(trace, ensure_ascii=False) + "\n")
def run(question, max_steps=5):
    trace = {
        "id": uuid.uuid4().hex[:8],
        "question": question,
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "steps": [],
        "answer": None,
        "status": "running",
    }

    messages = [{"role": "user", "content": question}]

    try:
        for step in range(max_steps):
            resp = client.chat.completions.create(
                model=os.getenv("LLM_MODEL"),
                messages=messages,
                tools=tools,
            )
            msg = resp.choices[0].message
            messages.append(msg)

            names = [c.function.name for c in (msg.tool_calls or [])]
            print(f"  [第 {step + 1} 轮] {names or '无（直接回答）'}")

            if not msg.tool_calls:
                trace["answer"] = msg.content
                trace["status"] = "ok"
                return msg.content

            for call in msg.tool_calls:
                args = json.loads(call.function.arguments)
                t0 = time.perf_counter()
                result = call_tool(call.function.name, args)
                ms = round((time.perf_counter() - t0) * 1000)

                print(f"      → {call.function.name}({args}) = {result}  [{ms}ms]")

                trace["steps"].append({
                    "round": step + 1,
                    "tool": call.function.name,
                    "args": args,
                    "result": result,
                    "ms": ms,
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": str(result),
                })

        trace["answer"] = "超过最大步数，未完成"
        trace["status"] = "max_steps"
        return trace["answer"]

    except Exception as e:
        trace["status"] = "error"
        trace["answer"] = f"运行出错：{e}"
        print(f"  ✗ 出错：{e}")
        return trace["answer"]

    finally:
        save_trace(trace)

tests = [
    "北京天气怎么样？",
    "天津天气怎么样？",
    "火星天气怎么样？",
    "3 加 5 等于几？",
    "你是谁？",
]

if __name__ == "__main__":
    for q in tests:
        print(f"\n【问题】{q}")
        print(run(q))