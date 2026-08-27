"""Pydantic 数据模型

定义任务、规则步骤、条件、动作等核心数据结构，
用于请求/响应校验与前后端 JSON 传递。
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


class Condition(BaseModel):
    """步骤触发条件。"""

    type: Literal["page_load", "element_visible", "text_appears", "always"] = "always"
    selector: Optional[str] = None
    text: Optional[str] = None
    timeout: int = 10000


class Action(BaseModel):
    """步骤执行动作。"""

    type: Literal[
        "open", "click", "input", "select", "upload",
        "scroll", "extract", "wait", "hover", "press_key",
        "goto", "if_text", "if_element", "if_var",
    ]
    url: Optional[str] = None
    selector: Optional[str] = None
    text: Optional[str] = None
    value: Optional[str] = None
    keys: Optional[str] = None
    timeout: int = 10000
    locator_strategy: str = "auto"
    extract_type: Optional[Literal["text", "attribute", "inner_html", "value", "count"]] = "text"
    attribute: Optional[str] = None
    save_as: Optional[str] = None
    amount: Optional[int] = None
    options: List[str] = Field(default_factory=list)
    files: List[str] = Field(default_factory=list)
    delay_after: Optional[float] = None
    # 控制流动作字段
    target: Optional[int] = None                # goto 跳转目标 step_id
    goto_if_found: Optional[int] = None         # if_* 条件命中跳转目标
    goto_if_not: Optional[int] = None           # if_* 条件未命中跳转目标（None=结束）
    var: Optional[str] = None                   # if_var 变量名
    op: Optional[Literal["equals", "contains", "not_equals", "not_contains"]] = None


class Step(BaseModel):
    """规则步骤：条件 + 动作。"""

    step_id: int
    condition: Condition = Field(default_factory=Condition)
    action: Action


class ScheduleConfig(BaseModel):
    """定时调度配置。"""

    type: Literal["cron", "interval", "date", "once"] = "once"
    expression: Optional[str] = None      # cron 表达式
    interval: Optional[Dict[str, int]] = None  # 如 {"hours": 2}
    run_date: Optional[str] = None        # 如 "2026-09-01 08:00"
    missed_run: bool = True               # 错过补执行


class TaskConfig(BaseModel):
    """完整任务规则。"""

    task_name: str = "未命名任务"
    description: str = ""
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)
    speed_mode: Literal["fast", "normal", "slow"] = "normal"
    steps: List[Step]


class TaskCreate(BaseModel):
    """创建任务请求体。"""

    name: str
    config: TaskConfig


class TaskUpdate(BaseModel):
    """更新任务请求体。"""

    name: Optional[str] = None
    config: Optional[TaskConfig] = None
    status: Optional[str] = None


class NLParseRequest(BaseModel):
    """自然语言解析请求。"""

    text: str


class NLParseResponse(BaseModel):
    """自然语言解析结果。"""

    config: TaskConfig
    raw: Optional[Dict[str, Any]] = None


class StepLog(BaseModel):
    """步骤执行日志。"""

    step_id: int
    action_type: str
    target_element: Optional[str] = None
    status: str
    duration_ms: Optional[int] = None
    screenshot_before: Optional[str] = None
    screenshot_after: Optional[str] = None
    healing_actions: List[str] = Field(default_factory=list)
    error_info: Optional[str] = None
    extracted: Optional[Any] = None


class ReportSummary(BaseModel):
    """报告概要。"""

    task_id: str
    task_name: str
    run_id: str
    status: str
    start_time: str
    end_time: Optional[str] = None
    duration_ms: Optional[int] = None
    error_msg: Optional[str] = None
    steps: List[StepLog] = Field(default_factory=list)


class RecordingStartRequest(BaseModel):
    """开始录制请求。"""

    start_url: Optional[str] = "https://www.baidu.com"


class SettingsUpdate(BaseModel):
    """设置更新请求。"""

    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    vl_model: Optional[str] = None
    screenshot_quality: Optional[int] = None
    report_retention_days: Optional[int] = None
    missed_run: Optional[bool] = None
    show_browser: Optional[bool] = None
    browser_mode: Optional[str] = None
    cdp_url: Optional[str] = None
    wechat_webhook: Optional[str] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_to: Optional[str] = None