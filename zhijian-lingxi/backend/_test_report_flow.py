"""验证财务报表控制流规则（本地模拟页，无需 LLM）。

场景：列表含 A/B 类报表，每条有「个人/对公/个人对公」类型。
- 个人 → 点「确定」
- 对公 / 个人对公 → 点「跳过」
- 处理后条目消失、后面顺延；一页处理完点「下一页」；无下一页则结束。
"""
import asyncio
from pathlib import Path

from executor import TaskExecutor
from rule_engine import RuleEngine

FILE_URI = Path(__file__).with_name("_mock_report.html").resolve().as_uri()

RULE = {
    "task_name": "财务报表审批",
    "speed_mode": "fast",
    "steps": [
        {"step_id": 1, "action": {"type": "open", "url": FILE_URI}},
        {"step_id": 2, "action": {"type": "wait", "value": 1}},

        # 循环入口：还有未处理的报表条目吗？
        {"step_id": 3, "action": {"type": "if_element", "selector": ".report",
                                  "goto_if_found": 4, "goto_if_not": 10}},

        # 提取第一条目的类型
        {"step_id": 4, "action": {"type": "extract", "selector": ".report .kind",
                                  "extract_type": "text", "save_as": "kind"}},

        # 分支：含「对公」→ 跳过(8)；否则（个人）→ 确定(6)
        {"step_id": 5, "action": {"type": "if_var", "var": "kind", "op": "contains",
                                  "value": "对公", "goto_if_found": 8, "goto_if_not": 6}},

        {"step_id": 6, "action": {"type": "click", "selector": ".confirm-btn"}},
        {"step_id": 7, "action": {"type": "goto", "target": 3}},

        {"step_id": 8, "action": {"type": "click", "selector": ".skip-btn"}},
        {"step_id": 9, "action": {"type": "goto", "target": 3}},

        # 本页处理完：还有下一页吗？有 → 11；无 → 结束
        {"step_id": 10, "action": {"type": "if_element", "selector": "#next-btn",
                                   "goto_if_found": 11, "goto_if_not": None}},

        {"step_id": 11, "action": {"type": "click", "selector": "#next-btn"}},
        {"step_id": 12, "action": {"type": "goto", "target": 3}},
    ],
}


async def main():
    # 1) 规则是否通过 schema + 白名单校验
    RuleEngine.validate(RULE)
    print("规则校验通过（含控制流动作）\n")

    # 2) 实际执行
    executor = TaskExecutor()
    result = await executor.run(RULE, headless=True)

    print("状态:", result["status"])
    print("耗时(ms):", result["duration_ms"])
    print("总步数:", len(result["steps"]))
    print("步骤日志:")
    for log in result["steps"]:
        sid = log["step_id"]
        atype = log["action_type"]
        st = log["status"]
        ext = log.get("extracted")
        err = log.get("error_info")
        line = f"  step {sid:>2} [{atype:<11}] {st:<8}"
        if ext is not None:
            line += f"  extracted={ext!r}"
        if err:
            line += f"  err={err}"
        print(line)


if __name__ == "__main__":
    asyncio.run(main())