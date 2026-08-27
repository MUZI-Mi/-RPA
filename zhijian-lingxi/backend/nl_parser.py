"""自然语言解析

调用通义千问，将用户口语转为结构化规则（TaskConfig JSON）。
"""

from __future__ import annotations

from typing import Any, Dict

from llm_client import LLMClient, LLMError
from rule_engine import RuleEngine, RuleValidationError

SYSTEM_PROMPT = """你是一个网页自动化操作生成器。用户会用自然语言描述需求，你要把它转换为可执行的规则 JSON。

要求：
1. 严格输出 JSON 对象，只包含以下字段：task_name、description、schedule、speed_mode、steps
2. schedule 识别时间意图：
   - "每天早上9点" → {"type": "cron", "expression": "0 9 * * *"}
   - "每个工作日8点半" → {"type": "cron", "expression": "30 8 * * 1-5"}
   - "每隔2小时" → {"type": "interval", "interval": {"hours": 2}}
   - 无时间意图 → {"type": "once"}
3. steps 是数组，每个步骤含 step_id（从1递增）和 action。action.type 只能是白名单：
   open / click / input / select / extract / wait / scroll / hover / press_key / upload /
   goto / if_text / if_element / if_var
4. 普通 action 字段说明：
   - open: {"url": "..."}
   - click: {"selector": "...", "text": "描述"}
   - input: {"selector": "...", "value": "..."}
   - extract: {"selector": "...", "extract_type": "text", "save_as": "..."}
   - wait: {"value": 秒数}
5. 控制流 action（用于条件分支、循环、翻页等复杂流程）：
   - goto: {"target": 目标step_id}，无条件跳转到某个步骤
   - if_text: {"text": "关键词", "goto_if_found": step_id, "goto_if_not": step_id}
     页面文本包含关键词 → 跳 goto_if_found，否则 → 跳 goto_if_not
   - if_element: {"selector": "...", "goto_if_found": step_id, "goto_if_not": step_id}
     元素存在 → 跳 goto_if_found，否则 → 跳 goto_if_not
   - if_var: {"var": "变量名", "op": "contains", "value": "期望值", "goto_if_found": step_id, "goto_if_not": step_id}
     对 extract 保存的变量做判断后分支；op ∈ equals / contains / not_equals / not_contains
   - goto_if_found / goto_if_not 可为 null，表示结束执行
   - 循环：用 goto 跳回前面的 step_id（配合 if_element/if_var 判断退出条件）
   - 重要：若用户描述了"对每个条目/每条记录/翻页直到处理完"这类需求，必须用
     extract 提取当前条目 → if_var 判断 → click → goto 循环的写法，不要只生成线性步骤
6. 每个 action 额外输出 confidence（0~1 置信度）字段。
7. 不确定的元素选择器可以先用合理的 CSS 选择器或文本描述，系统会自愈定位。

只输出 JSON，不要任何解释文字。"""


class NLParser:
    @staticmethod
    async def parse(user_input: str) -> Dict[str, Any]:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_input},
        ]
        data = await LLMClient.chat_json(messages, temperature=0.1)

        # 清理 action 中的 confidence 字段（不在规则模型内）
        steps = data.get("steps", [])
        cleaned_steps = []
        for i, s in enumerate(steps):
            step = dict(s)
            step.setdefault("step_id", i + 1)
            step.setdefault("condition", {"type": "always"})
            action = dict(step.get("action", {}))
            action.pop("confidence", None)
            # 控制流跳转目标统一转 int（LLM 可能输出字符串），null 保持 None
            for key in ("target", "goto_if_found", "goto_if_not"):
                if action.get(key) is not None:
                    try:
                        action[key] = int(action[key])
                    except (TypeError, ValueError):
                        action[key] = None
            step["action"] = action
            cleaned_steps.append(step)
        data["steps"] = cleaned_steps
        data.setdefault("task_name", user_input[:20])
        data.setdefault("schedule", {"type": "once"})
        data.setdefault("speed_mode", "normal")

        # Schema 校验
        try:
            RuleEngine.validate(data)
        except RuleValidationError as e:
            raise LLMError(f"解析结果未通过校验：{e}")

        return data