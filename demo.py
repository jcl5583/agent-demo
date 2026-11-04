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
}]


def add(a, b):
    return a + b


question = "3 加 5 等于几？"

resp = client.chat.completions.create(
    model=os.getenv("LLM_MODEL"),
    messages=[{"role": "user", "content": question}],
    tools=tools,
)

msg = resp.choices[0].message
print(msg)

call = msg.tool_calls[0]
args = json.loads(call.function.arguments)
result = add(args["a"], args["b"])

messages = [
    {"role": "user", "content": question},
    msg,
    {"role": "tool", "tool_call_id": call.id, "content": str(result)},
]

resp2 = client.chat.completions.create(
    model=os.getenv("LLM_MODEL"),
    messages=messages,
    tools=tools,
)

print(resp2.choices[0].message.content)