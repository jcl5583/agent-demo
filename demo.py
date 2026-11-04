import os
import json

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("LLM_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL"),
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
},{
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
def get_weather(city):
    fake = {"北京": "晴，18℃", "上海": "多云，22℃", "成都": "小雨，15℃"}
    return fake.get(city, "查不到这个城市")

question = "3 加 5 等于几？"

resp = client.chat.completions.create(
    model=os.getenv("LLM_MODEL"),
    messages=[{"role": "user", "content": question}],
    tools=tools,
)

msg = resp.choices[0].message
print(msg)

TOOLS_BY_NAME = {"add": add, "get_weather": get_weather}

messages = [{"role": "user", "content": question}, msg]

for call in msg.tool_calls:
    name = call.function.name
    args = json.loads(call.function.arguments)
    result = TOOLS_BY_NAME[name](**args)
    messages.append({
        "role": "tool",
        "tool_call_id": call.id,
        "content": str(result),
    })

resp2 = client.chat.completions.create(
    model=os.getenv("LLM_MODEL"),
    messages=messages,
    tools=tools,
)

print(resp2.choices[0].message.content)

print(get_weather("北京"))
print(get_weather("火星"))

tests = [
    "3 加 5 等于几？",
    "北京天气怎么样？",
    "3 加 5 等于几？顺便看看北京天气",
]