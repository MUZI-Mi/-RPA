import asyncio, json
from nl_parser import NLParser

STEPS = [
    {"step_id": 1, "condition": {"type": "always"}, "action": {"type": "click", "selector": "#login", "text": "登录", "value": ""}},
    {"step_id": 2, "condition": {"type": "always"}, "action": {"type": "input", "selector": "#acc", "text": "", "value": "zhangsan"}},
    {"step_id": 3, "condition": {"type": "always"}, "action": {"type": "close_tab", "selector": "", "text": "", "value": ""}},
]


async def main():
    steps = await NLParser.add_notes(STEPS)
    for s in steps:
        print("STEP", s["step_id"], "note=", repr(s.get("note")))


asyncio.run(main())
