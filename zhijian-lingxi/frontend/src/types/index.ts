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
    | "goto"
    | "if_text"
    | "if_element"
    | "if_var";
  url?: string;
  selector?: string;
  text?: string;
  value?: string;
  keys?: string;
  timeout?: number;
  locator_strategy?: string;
  extract_type?: "text" | "attribute" | "inner_html" | "value" | "count";
  attribute?: string;
  save_as?: string;
  amount?: number;
  options?: string[];
  files?: string[];
  delay_after?: number;
  // 控制流动作字段
  target?: number | null;
  goto_if_found?: number | null;
  goto_if_not?: number | null;
  var?: string;
  op?: "equals" | "contains" | "not_equals" | "not_contains";
}

export interface Step {
  step_id: number;
  condition: Condition;
  action: Action;
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