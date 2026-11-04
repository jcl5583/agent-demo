# agent-demo

跟着项目实战路线做的 Agent 工具调用练习：用 function calling 让模型自己决定调用哪个工具。

## 当前支持的工具

| 工具 | 作用 | 参数 |
|---|---|---|
| `add` | 两个数相加 | `a`、`b` |
| `get_weather` | 查询城市天气（目前是假数据） | `city` |

## 跑起来

1. 复制 `.env.example` 为 `.env`，填入自己的 API Key
2. `pip install -r requirements.txt`
3. `python demo.py`

## 能看到什么

问「3 加 5 等于几」，模型会调用 `add`；
问「北京天气怎么样」，模型会调用 `get_weather`；
问「3 加 5 顺便看北京天气」，模型可能一次调用两个工具。

## 当前能力

- 单工具调用、多工具并行调用
- ReAct 循环：模型可连续多轮调用工具（最多 5 步），例如「先查北京、再查上海、算温差」会自己走 3 轮