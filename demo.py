import json
import os
import sqlite3
import time
import urllib.parse
import urllib.request
import uuid
from datetime import datetime

from dotenv import load_dotenv
from openai import OpenAI

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "company.db")
TRACE_DIR = os.path.join(BASE_DIR, "traces")
TRACE_FILE = os.path.join(TRACE_DIR, "traces.jsonl")

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
        "description": "查询指定城市当前的实时天气（温度和天气状况）",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "城市名，例如 北京"},
            },
            "required": ["city"],
        },
    },
}, {
    "type": "function",
    "function": {
        "name": "get_employee",
        "description": "查询公司员工的部门和月薪，参数是员工姓名",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "员工姓名，例如 张伟"},
            },
            "required": ["name"],
        },
    },
}]


def add(a, b):
    return a + b


WMO = {
    0: "晴", 1: "晴间多云", 2: "多云", 3: "阴",
    45: "雾", 48: "雾凇",
    51: "小毛毛雨", 53: "毛毛雨", 55: "大毛毛雨",
    61: "小雨", 63: "中雨", 65: "大雨",
    71: "小雪", 73: "中雪", 75: "大雪",
    80: "阵雨", 81: "强阵雨", 82: "暴雨",
    95: "雷暴", 96: "雷暴伴冰雹", 99: "强雷暴伴冰雹",
}


def get_weather(city):
    q = urllib.parse.quote(city)

    geo_url = (
        "https://geocoding-api.open-meteo.com/v1/search"
        f"?name={q}&count=1&language=zh&format=json"
    )
    with urllib.request.urlopen(geo_url, timeout=10) as r:
        geo = json.loads(r.read().decode("utf-8"))

    results = geo.get("results") or []
    if not results:
        return f"查不到这个城市：{city}"

    lat = results[0]["latitude"]
    lon = results[0]["longitude"]
    name = results[0].get("name", city)

    wx_url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&current=temperature_2m,weather_code&timezone=auto"
    )
    with urllib.request.urlopen(wx_url, timeout=10) as r:
        wx = json.loads(r.read().decode("utf-8"))

    cur = wx["current"]
    temp = cur["temperature_2m"]
    desc = WMO.get(cur["weather_code"], "未知天气")

    return f"{name}：{desc}，{temp}℃"


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS employees (
                name TEXT PRIMARY KEY,
                dept TEXT NOT NULL,
                salary INTEGER NOT NULL
            )
        """)
        rows = [
            ("张伟", "技术部", 18000),
            ("李娜", "产品部", 16500),
            ("王强", "技术部", 21000),
            ("刘洋", "市场部", 14000),
            ("陈静", "财务部", 15500),
        ]
        conn.executemany(
            "INSERT OR IGNORE INTO employees (name, dept, salary) VALUES (?, ?, ?)",
            rows,
        )
        conn.commit()
    finally:
        conn.close()


def get_employee(name):
    init_db()
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute(
            "SELECT dept, salary FROM employees WHERE name = ?", (name,)
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return f"查无此人：{name}"
    dept, salary = row
    return f"{name}：{dept}，月薪 {salary} 元"


TOOLS_BY_NAME = {
    "add": add,
    "get_weather": get_weather,
    "get_employee": get_employee,
}


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
    "火星天气怎么样？",
    "3 加 5 等于几？",
    "张伟的月薪是多少？",
    "王五的工资是多少？",
    "你是谁？",
]

if __name__ == "__main__":
    for q in tests:
        print(f"\n【问题】{q}")
        print(run(q))
