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
        "reload", "back", "forward", "close_tab", "set_var",
        "goto", "if_text", "if_element", "if_var", "foreach", "foreach_if",
        "ocr", "llm_extract", "export",
        "read_excel", "read_csv", "ocr_to_json", "data_clean", "llm_summarize",
    ]
    url: Optional[str] = None
    selector: Optional[str] = None
    next_selector: Optional[str] = None  # foreach/foreach_if 分页"下一页"按钮
    match_text: Optional[str] = None     # foreach_if 命中关键词（该项文字包含才算命中）
    click_selector: Optional[str] = None  # foreach_if 命中后要点击的子元素（留空=打开该项链接）
    text: Optional[str] = None
    value: Optional[str] = None
    keys: Optional[str] = None
    timeout: int = 10000
    locator_strategy: str = "auto"
    extract_type: Optional[Literal["text", "attribute", "inner_html", "value", "count"]] = "text"
    attribute: Optional[str] = None
    save_as: Optional[str] = None
    # foreach/foreach_if：每个链接打开后，在详情页依次执行的提取步骤
    # （extract / llm_extract / ocr），结果按 save_as 命名、每轮迭代汇总成一行报表
    extract_steps: List[Dict[str, Any]] = Field(default_factory=list)
    # ocr / llm_extract / export 相关字段
    fields: Optional[str] = None        # llm_extract：要抽取的字段，逗号分隔（如 "标题,日期,金额"）
    ocr_source: Optional[str] = None    # ocr："page" 整页截图 / "element" 元素截图（默认 element）
    export_format: Optional[Literal["csv", "json", "xlsx", "docx", "pdf"]] = "csv"  # export 导出格式
    export_filename: Optional[str] = None  # export 导出文件名（不含扩展名）
    template_file: Optional[str] = None    # export 引用的模板名（模板中心）
    file_path: Optional[str] = None        # read_excel/read_csv 本地文件路径
    sheet_name: Optional[str] = None       # read_excel 工作表名
    has_header: bool = True                # read_excel/read_csv 是否有表头
    encoding: Optional[str] = None         # read_csv 编码
    delimiter: Optional[str] = None        # read_csv 分隔符
    source: Optional[str] = None           # data_clean/llm_summarize 输入变量名（空=__table）
    rules: Optional[Dict[str, Any]] = None  # data_clean 清洗规则
    batch_size: int = 10                   # llm_summarize 分批大小
    threshold: Optional[float] = None      # llm_summarize 审核阈值（默认读设置）
    append_columns: bool = True            # llm_summarize 结果列回写 __table
    append_to_table: bool = False          # read_*/ocr_to_json 结果并入 __table
    amount: Optional[int] = None
    options: List[str] = Field(default_factory=list)
    files: List[str] = Field(default_factory=list)
    delay_after: Optional[float] = None
    # 控制流动作字段
    target: Optional[int] = None                # goto 跳转目标 step_id
    goto_if_found: Optional[int] = None         # if_* 条件命中跳转目标
    goto_if_not: Optional[int] = None           # if_* 条件未命中跳转目标（None=结束）
    var: Optional[str] = None                   # if_var/set_var 变量名
    op: Optional[Literal[
        "equals", "contains", "not_equals", "not_contains",
        "less", "less_equals", "greater", "greater_equals",
        "set", "inc", "dec",
    ]] = None


class Step(BaseModel):
    """规则步骤：条件 + 动作。"""

    step_id: int
    condition: Condition = Field(default_factory=Condition)
    action: Action
    # 自然语言说明：AI 解析时用大白话描述该步骤做什么，供非技术用户确认
    note: Optional[str] = None


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


class NLRefineRequest(BaseModel):
    """自然语言修改请求：已有方案 + 用户的修改要求。"""

    text: str
    config: Dict[str, Any]


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
    clicked_info: Optional[Any] = None


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
    # 合规相关
    operator_name: Optional[str] = None        # 操作人姓名（审计日志用）
    pii_masking_enabled: Optional[bool] = None  # PII 脱敏开关
    review_threshold: Optional[float] = None   # AI 结果进入审核队列的置信度阈值


class ReviewItem(BaseModel):
    """审核队列条目。"""

    id: str
    task_id: Optional[str] = None
    execution_id: Optional[str] = None
    step_id: Optional[int] = None
    source: Optional[str] = None
    raw_data: Any = None
    ai_result: Any = None
    confidence: Optional[float] = None
    compliance_issues: List[str] = Field(default_factory=list)
    status: str = "pending"
    operator: Optional[str] = None
    review_note: Optional[str] = None
    corrected_data: Any = None
    created_at: str
    reviewed_at: Optional[str] = None


class ReviewDecision(BaseModel):
    """审核处理请求：通过/驳回/修改。"""

    operator: Optional[str] = None
    note: Optional[str] = None
    corrected_data: Any = None  # update 时人工修改后的数据


class AuditItem(BaseModel):
    """审计日志条目。"""

    id: str
    operator: str
    action: str
    target_type: str
    target_id: Optional[str] = None
    detail: Any = None
    created_at: str