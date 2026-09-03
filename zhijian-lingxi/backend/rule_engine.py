"""规则引擎

负责规则加载、JSON Schema 校验、变量解析与按序执行调度。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from jsonschema import ValidationError, validate

# JSON Schema 用于规则结构校验
RULE_SCHEMA = {
    "type": "object",
    "required": ["task_name", "steps"],
    "properties": {
        "task_name": {"type": "string"},
        "description": {"type": "string"},
        "speed_mode": {"enum": ["fast", "normal", "slow"]},
        "schedule": {
            "type": "object",
            "properties": {
                "type": {"enum": ["cron", "interval", "date", "once"]},
                "expression": {"type": "string"},
                "interval": {"type": "object"},
                "run_date": {"type": "string"},
                "missed_run": {"type": "boolean"},
            },
        },
        "steps": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["action"],
                "properties": {
                    "step_id": {"type": "integer"},
                    "condition": {"type": "object"},
                    "action": {
                        "type": "object",
                        "required": ["type"],
                        "properties": {
                            "type": {
                                "enum": [
                                    "open", "click", "input", "select", "upload",
                                    "scroll", "extract", "wait", "hover", "press_key",
                                    "reload", "back", "forward", "close_tab", "set_var",
                                    "goto", "if_text", "if_element", "if_var", "foreach",
                                    "foreach_if", "ocr", "llm_extract", "export",
                                    "read_excel", "read_csv", "ocr_to_json", "data_clean",
                                    "llm_summarize",
                                ]
                            }
                        },
                    },
                },
            },
        },
    },
}

ACTION_TYPES = {
    "open", "click", "input", "select", "upload",
    "scroll", "extract", "wait", "hover", "press_key",
    "reload", "back", "forward", "close_tab", "set_var",
    "goto", "if_text", "if_element", "if_var", "foreach", "foreach_if",
    "ocr", "llm_extract", "export",
    "read_excel", "read_csv", "ocr_to_json", "data_clean", "llm_summarize",
}
CONDITION_TYPES = {"page_load", "element_visible", "text_appears", "always"}
# 控制流动作：只改变执行指针，不操作页面
CONTROL_FLOW_TYPES = {"goto", "if_text", "if_element", "if_var"}

_VAR_RE = re.compile(r"\{\{\s*([\w.]+)\s*\}\}")


class RuleValidationError(Exception):
    pass


def _dot_get(obj: Any, path: str) -> Optional[Any]:
    """按点号路径取变量，如 a.b.c。"""
    cur = obj
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list) and part.isdigit():
            idx = int(part)
            cur = cur[idx] if idx < len(cur) else None
        else:
            return None
    return cur


class RuleEngine:
    """规则引擎：校验 + 变量解析。"""

    @staticmethod
    def validate(rules: Dict[str, Any]) -> bool:
        """使用 JSON Schema 校验规则，失败抛 RuleValidationError。"""
        try:
            validate(instance=rules, schema=RULE_SCHEMA)
        except ValidationError as e:
            raise RuleValidationError(f"规则校验失败: {e.message}") from e
        # 补充白名单校验
        for i, step in enumerate(rules.get("steps", [])):
            action = step.get("action", {})
            if action.get("type") not in ACTION_TYPES:
                raise RuleValidationError(f"步骤 {i + 1} 动作类型非法: {action.get('type')}")
            cond = step.get("condition", {}) or {}
            if cond.get("type", "always") not in CONDITION_TYPES:
                raise RuleValidationError(f"步骤 {i + 1} 条件类型非法: {cond.get('type')}")
        return True

    @staticmethod
    def resolve_variable(template: str, context: Dict[str, Any]) -> str:
        """解析字符串中的 {{ variable }} 引用。

        若整体为单个变量引用且值为非字符串，则返回原值。
        """
        if not isinstance(template, str):
            return template
        full_match = _VAR_RE.fullmatch(template.strip())
        if full_match:
            return _dot_get(context, full_match.group(1))
        return _VAR_RE.sub(
            lambda m: str(_dot_get(context, m.group(1)) or ""), template
        )

    @staticmethod
    def resolve_params(obj: Any, context: Dict[str, Any]) -> Any:
        """递归解析对象中所有字符串字段的变量引用。"""
        if isinstance(obj, str):
            return RuleEngine.resolve_variable(obj, context)
        if isinstance(obj, list):
            return [RuleEngine.resolve_params(x, context) for x in obj]
        if isinstance(obj, dict):
            return {k: RuleEngine.resolve_params(v, context) for k, v in obj.items()}
        return obj

    @staticmethod
    def normalize_steps(steps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """补全 step_id 等默认字段。"""
        out = []
        for i, s in enumerate(steps):
            step = dict(s)
            step.setdefault("step_id", i + 1)
            step.setdefault("condition", {"type": "always"})
            step.setdefault("action", {})
            out.append(step)
        return out