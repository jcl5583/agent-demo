import contextlib
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from demo import run

HERE = os.path.dirname(os.path.abspath(__file__))
TRACE_FILE = os.path.join(ROOT, "traces", "traces.jsonl")


def last_trace():
    with open(TRACE_FILE, encoding="utf-8") as f:
        return json.loads(f.readlines()[-1])


def judge(case, answer, trace):
    used = [s["tool"] for s in trace["steps"]]
    expected = case["tools"]

    if expected:
        tools_ok = set(expected).issubset(set(used))
    else:
        tools_ok = len(used) == 0

    text_ok = all(k in answer for k in case.get("keywords", []))
    return tools_ok and text_ok and trace["status"] == "ok", used


def main():
    with open(os.path.join(HERE, "cases.json"), encoding="utf-8") as f:
        cases = json.load(f)

    passed = 0
    failures = []

    for case in cases:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            answer = run(case["question"]) or ""
        trace = last_trace()

        ok, used = judge(case, answer, trace)
        passed += ok

        mark = "✓" if ok else "✗"
        print(f"{mark} {case['id']}  {case['question'][:22]}  →  {used}")

        if not ok:
            failures.append((case, answer, used))

    total = len(cases)
    rate = round(passed / total * 100)
    print("\n" + "=" * 55)
    print(f"通过率：{passed}/{total}  ({rate}%)")

    if failures:
        print("\n未通过清单：")
        for case, answer, used in failures:
            print(f"  {case['id']}  {case['question']}")
            print(f"     实际工具 {used}，期望 {case['tools']}")
            print(f"     回答：{answer[:70]}")


if __name__ == "__main__":
    main()