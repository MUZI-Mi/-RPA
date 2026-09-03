// TypeScript 类型定义，与后端 models.py 对应

export interface Condition {
  type: "page_load" | "element_visible" | "text_appears" | "always";
  selector?: string;
  text?: string;
  timeout?: number;
}

export interface Action {
  type:
    | "open"
    | "click"
    | "input"
    | "select"
    | "upload"
    | "scroll"
    | "extract"
    | "wait"
    | "hover"
    | "press_key"
    | "reload"
    | "back"
    | "forward"
    | "close_tab"
    | "set_var"
    | "goto"
    | "if_text"
    | "if_element"
    | "if_var"
    | "foreach"
    | "foreach_if"
    | "ocr"
    | "llm_extract"
    | "export"
    | "read_excel"
    | "read_csv"
    | "ocr_to_json"
    | "data_clean"
    | "llm_summarize";
  url?: string;
  selector?: string;
  next_selector?: string;
  // 逐条检查（foreach_if）：命中关键词 + 命中的项里要点的按钮/链接
  match_text?: string;
  click_selector?: string;
  // foreach/foreach_if：每个详情页依次执行的提取步骤，汇总成报表行
  extract_steps?: Step["action"][];
  text?: string;
  value?: string;
  keys?: string;
  timeout?: number;
  locator_strategy?: string;
  extract_type?: "text" | "attribute" | "inner_html" | "value" | "count";
  attribute?: string;
  save_as?: string;
  // ocr / llm_extract / export
  fields?: string;                 // llm_extract：要抽取的字段，逗号分隔
  ocr_source?: string;             // ocr：page / element
  export_format?: "csv" | "json" | "xlsx" | "docx" | "pdf";  // export 导出格式
  export_filename?: string;        // export 导出文件名（不含扩展名）
  template_file?: string;          // export 引用的模板名（模板中心）
  _src?: string;                   // 编辑器 UI 用：llm_extract 抽取来源显示
  // read_excel / read_csv / ocr_to_json / data_clean / llm_summarize
  file_path?: string;              // read_excel/read_csv 本地文件路径
  sheet_name?: string;             // read_excel 工作表名
  has_header?: boolean;            // read_excel/read_csv 是否有表头
  encoding?: string;               // read_csv 编码
  delimiter?: string;              // read_csv 分隔符
  source?: string;                 // data_clean/llm_summarize 输入变量名（空=__table）
  rules?: Record<string, any>;     // data_clean 清洗规则
  batch_size?: number;             // llm_summarize 分批大小
  threshold?: number | null;       // llm_summarize 审核阈值（空=用设置）
  append_columns?: boolean;        // llm_summarize 结果列回写 __table
  append_to_table?: boolean;       // read_*/ocr_to_json 结果并入 __table
  amount?: number;
  options?: string[];
  files?: string[];
  delay_after?: number;
  // 关闭指定网页：预留要关闭标签页的标识（标题/网址关键词），留空则关闭当前页
  close_target?: string;
  // 控制流动作字段
  target?: number | null;
  goto_if_found?: number | null;
  goto_if_not?: number | null;
  var?: string;
  op?:
    | "equals"
    | "contains"
    | "not_equals"
    | "not_contains"
    | "less"
    | "less_equals"
    | "greater"
    | "greater_equals"
    | "set"
    | "inc"
    | "dec";
}

export interface Step {
  step_id: number;
  condition: Condition;
  action: Action;
  // 自然语言说明：AI 解析时用大白话描述该步骤做什么，供非技术用户确认
  note?: string;
}

export interface ScheduleConfig {
  type: "cron" | "interval" | "date" | "once";
  expression?: string;
  interval?: Record<string, number>;
  run_date?: string;
  missed_run?: boolean;
}

export interface TaskConfig {
  task_name: string;
  description: string;
  schedule: ScheduleConfig;
  speed_mode: "fast" | "normal" | "slow";
  steps: Step[];
}

export interface Task {
  id: string;
  name: string;
  config: TaskConfig;
  schedule: ScheduleConfig;
  speed_mode: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface StepLog {
  step_id: number;
  action_type: string;
  target_element: string;
  status: "success" | "failed";
  duration_ms: number;
  screenshot_before?: string;
  screenshot_after?: string;
  healing_actions: string[];
  error_info?: string;
  extracted?: any;
  page_url?: string;
  // 真实点击内容：{text: 被点元素可见文字, href: 被点链接真实地址}
  clicked_info?: { text?: string; href?: string | null };
}

export interface Execution {
  id: string;
  task_id: string;
  status: string;
  start_time: string;
  end_time?: string;
  duration_ms?: number;
  report_path?: string;
  error_msg?: string;
}

export interface LLMProvider {
  id: string;
  name: string;
  base_url: string;
  model: string;
  vl_model: string;
  note: string;
  register_url?: string;
}

// === 合规三件套 ===
export interface ReviewItem {
  id: string;
  task_id?: string;
  execution_id?: string;
  step_id?: number;
  source?: string;
  raw_data?: any;
  ai_result?: any;
  confidence?: number;
  compliance_issues: string[];
  status: "pending" | "approved" | "rejected";
  operator?: string;
  review_note?: string;
  corrected_data?: any;
  created_at: string;
  reviewed_at?: string;
}

export interface AuditItem {
  id: string;
  operator: string;
  action: string;
  target_type: string;
  target_id?: string;
  detail?: any;
  created_at: string;
}

export interface TemplateItem {
  id: string;
  name: string;
  description?: string;
  category: string;
  filename: string;
  original_name: string;
  size?: number;
  uploader?: string;
  created_at: string;
  updated_at: string;
}