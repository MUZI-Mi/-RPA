# 智简灵析 — Code Wiki

> 大学生大创项目 | 版本 v2.0 | 2026-08-26

---

## 目录

1. [项目概述](#1-项目概述)
2. [整体架构](#2-整体架构)
3. [技术栈](#3-技术栈)
4. [项目目录结构](#4-项目目录结构)
5. [核心模块说明](#5-核心模块说明)
   - [5.1 规则引擎](#51-规则引擎)
   - [5.2 浏览器自动化执行](#52-浏览器自动化执行)
   - [5.3 智能自愈机制](#53-智能自愈机制)
   - [5.4 自然语言解析](#54-自然语言解析)
   - [5.5 前端界面](#55-前端界面)
   - [5.6 执行报告](#56-执行报告)
   - [5.7 定时调度](#57-定时调度)
   - [5.8 操作录制](#58-操作录制)
   - [5.9 桌面应用封装](#59-桌面应用封装)
6. [API 接口](#6-api-接口)
7. [数据存储](#7-数据存储)
8. [运行方式](#8-运行方式)
9. [演示方案](#9-演示方案)
10. [免费模型接入](#10-免费模型接入)

---

## 1. 项目概述

"智简灵析"是一款面向普通办公人员的智能网页自动化助手。用户用自然语言描述需求（如"每天早上9点打开钉钉签到"），系统自动解析为浏览器操作并执行。最终以**桌面应用**形式交付，双击即用。

**核心亮点**：

| 亮点 | 说明 |
|------|------|
| 自然语言驱动 | 说人话就能创建自动化任务，零学习成本 |
| 四层智能自愈 | 页面改版也不怕，AI 自动重新定位元素 |
| 可视化配置 | 拖拽编排规则，不会写代码也能用 |
| 操作录制 | 录一遍操作自动生成规则，无需手动配置 |
| 桌面应用 | 一键安装，本地运行，数据不上云 |

---

## 2. 整体架构

```
┌──────────────────────────────────────────────────────────┐
│                  Tauri 桌面壳 (Rust)                       │
│         窗口管理 │ 系统托盘 │ 原生通知 │ 应用生命周期         │
├──────────────────────────────────────────────────────────┤
│              浏览器前端 (Vue 3 + TypeScript)               │
│   指令输入 │ 任务管理 │ 报告查看 │ 设置 │ 录制控制          │
├──────────────────────────────────────────────────────────┤
│                FastAPI 后端 (Python 异步)                   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐     │
│  │ 规则引擎  │ │Playwright│ │ LLM 解析 │ │ 智能自愈  │     │
│  │          │ │ 自动化    │ │ (Qwen)   │ │ (四层降级)│     │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐     │
│  │ 报告生成  │ │ 定时调度  │ │ 操作录制  │ │ 消息通知  │     │
│  │(Jinja2)  │ │(APS)     │ │ (CDP)    │ │          │     │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘     │
├──────────────────────────────────────────────────────────┤
│              SQLite + 本地文件系统                          │
└──────────────────────────────────────────────────────────┘
```

**四层架构**：桌面壳(Tauri) → 前端(Vue) → 后端(FastAPI) → 存储(SQLite)。Tauri 负责窗口管理和系统托盘，后端通过 `localhost:8710` 与前端通信。

---

## 3. 技术栈

| 层 | 技术 | 用途 |
|---|------|------|
| 桌面壳 | Tauri 2.x (Rust) | 窗口管理、系统托盘、原生通知、打包为 exe |
| 前端 | Vue 3 + TypeScript + Element Plus + Vite | 用户界面、可视化配置 |
| 后端 | Python 3.11+ + FastAPI | API服务、规则引擎、自动化调度 |
| 浏览器引擎 | Playwright (Python) | 页面操作、截图、Chromium 无头模式 |
| AI 能力 | 兼容 OpenAI 协议的大模型（默认硅基流动免费模型，可切换智谱/通义/自定义） | NL解析、DOM语义分析、视觉定位 |
| 定时调度 | APScheduler | cron/interval/date 三种触发模式 |
| 报告 | Jinja2 | HTML 报告模板渲染 |
| 存储 | SQLite + 本地文件 | 任务/日志持久化、截图/报告文件 |

---

## 4. 项目目录结构

```
zhijian-lingxi/
├── frontend/                      # Vue 3 前端
│   ├── public/
│   │   └── templates/             # 预置任务模板 JSON
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Instruction.vue    # 指令输入页（NL + 手动配置）
│   │   │   ├── Tasks.vue          # 任务管理页
│   │   │   ├── Report.vue         # 执行报告页
│   │   │   └── Settings.vue       # 设置页
│   │   ├── components/
│   │   │   ├── RuleCard.vue       # 规则卡片（展示+拖拽排序）
│   │   │   ├── RuleEditor.vue     # 规则编辑器（点选配置）
│   │   │   ├── StepTimeline.vue   # 步骤时间线
│   │   │   └── ScreenshotViewer.vue # 截图查看器
│   │   ├── api/                   # Axios 接口封装
│   │   ├── stores/                # Pinia 状态管理
│   │   ├── types/                 # TypeScript 类型定义
│   │   └── router/                # Vue Router
│   ├── package.json
│   └── vite.config.ts
│
├── backend/                       # Python 后端
│   ├── main.py                    # FastAPI 入口
│   ├── config.py                  # 配置管理
│   ├── rule_engine.py             # 规则引擎
│   ├── executor.py                # 任务执行器（核心调度）
│   ├── nl_parser.py               # 自然语言解析
│   ├── self_healing.py            # 智能自愈（四层降级）
│   ├── report.py                  # 报告生成
│   ├── scheduler.py               # 定时调度
│   ├── recorder.py                # 操作录制
│   ├── notifier.py                # 消息通知
│   ├── database.py                # SQLite 操作
│   ├── models.py                  # Pydantic 数据模型
│   ├── data/                      # 运行时数据
│   │   ├── screenshots/
│   │   ├── reports/
│   │   └── app.db
│   └── requirements.txt
│
├── src-tauri/                     # Tauri 桌面壳 (Rust)
│   ├── src/main.rs
│   ├── tauri.conf.json
│   └── icons/
│
└── README.md
```

---

## 5. 核心模块说明

### 5.1 规则引擎

**职责**：规则加载、JSON Schema 校验、按序执行调度。

**规则数据结构**：

```json
{
  "task_name": "钉钉签到",
  "schedule": { "type": "cron", "expression": "0 9 * * *" },
  "speed_mode": "normal",
  "steps": [
    {
      "step_id": 1,
      "condition": { "type": "page_load" },
      "action": { "type": "open", "url": "https://login.dingtalk.com" }
    },
    {
      "step_id": 2,
      "condition": { "type": "element_visible", "selector": ".sign-btn", "timeout": 10000 },
      "action": { "type": "click", "selector": ".sign-btn", "locator_strategy": "auto" }
    },
    {
      "step_id": 3,
      "action": { "type": "extract", "selector": ".result", "extract_type": "text", "save_as": "msg" }
    }
  ]
}
```

**动作类型**：`open` / `click` / `input` / `select` / `upload` / `scroll` / `extract` / `wait` / `hover` / `press_key`

**条件类型**：`page_load` / `element_visible` / `text_appears` / `always`

**关键函数**：

```python
class RuleEngine:
    def validate(rules: dict) -> bool              # JSON Schema 校验
    def execute_step(step, page, context) -> Result # 执行单步
    def resolve_variable(template: str, context) -> str  # 解析 {{ }} 变量引用
```

---

### 5.2 浏览器自动化执行

**职责**：Playwright 驱动浏览器，执行页面操作。

**核心类**：

```python
class TaskExecutor:
    async def run(task_config) -> Report
        # 1. 启动 Chromium (无头/有头)
        # 2. 注册弹窗拦截、新窗口监听
        # 3. 遍历 steps 逐条执行
        # 4. 每步前后截图
        # 5. 步骤间随机延迟 (模拟人类)
        # 6. 异常 → 自愈机制
        # 7. 生成报告 → 发送通知

class BrowserManager:
    async def start(headless=True) -> Browser
    async def close()

class PageOperator:
    async def click(selector, page, strategy) -> bool
    async def input_text(selector, value, page) -> bool
    async def extract_data(selector, extract_type, page) -> Any
    async def screenshot(page) -> bytes
```

**执行流程**：

```
初始化浏览器 → 逐条执行规则 → 截图记录 → 异常自愈 → 生成报告 → 发送通知
                                    ↓
                              四层降级恢复
```

---

### 5.3 智能自愈机制

**四层元素定位降级**（核心技术亮点）：

```
第1层: CSS选择器精确匹配 → 毫秒级, 免费
  ↓ 失败
第2层: 文本/aria-label模糊匹配 + 相邻元素推断 → 毫秒级, 免费
  ↓ 失败
第3层: 精简DOM(≤150节点) → Qwen-Plus分析 → 返回选择器 → ~5s, ¥0.002
  ↓ 失败 或 置信度<0.75
第4层: 页面截图 → Qwen-VL视觉定位 → 返回坐标 → ~10s, ¥0.01
  ↓ 失败
报错: 记录异常信息到报告
```

**辅助自愈能力**：

| 能力 | 实现 |
|------|------|
| 弹窗拦截 | `page.on("dialog")` 自动关闭 Cookie/广告弹窗 |
| 加载重试 | 白屏/超时自动刷新，最多3次 |
| 定位缓存 | 成功定位结果缓存，下次优先使用 |

**核心类**：

```python
class SelfHealing:
    async def locate(selector, intent, page) -> Element
        for layer in [layer1, layer2, layer3, layer4]:
            result = await layer(selector, intent, page)
            if result and result.confidence > 0.75:
                cache.set(key, result)  # 缓存结果
                return result
        raise ElementNotFoundError

class LocatorCache:
    def get(key: str) -> Optional[Result]
    def set(key: str, result: Result)
```

---

### 5.4 自然语言解析

**职责**：调用大模型（默认硅基流动免费模型 `Qwen2.5-7B`，可切换），将用户口语转为结构化规则。

**流程**：

```
用户输入 "每天早上9点打开钉钉签到"
  → 构造 System Prompt（约束输出格式+动作白名单）
  → 调用 LLM API（兼容 OpenAI 协议）
  → 解析 JSON + 校验 Schema
  → 前端可视化展示，用户确认/修改后执行
```

**System Prompt 设计要点**：

1. 角色定义："你是一个网页自动化操作生成器"
2. 严格输出 JSON，只包含 `task_name`、`schedule`、`steps`
3. 限定动作白名单（open/click/input/extract/wait）
4. 识别时间意图（"每天/每周/定时"→自动生成 cron）
5. 每个步骤输出置信度

**核心类**：

```python
class NLParser:
    async def parse(user_input: str) -> dict
        prompt = build_system_prompt()
        messages = [{"role": "system", "content": prompt},
                    {"role": "user", "content": user_input}]
        response = await LLMClient.chat_json(messages)
        return validate_and_return(response)
```

---

### 5.5 前端界面

**4个核心页面**：

| 页面 | 路由 | 功能 |
|------|------|------|
| 指令输入 | `/` | 自然语言输入 + 解析结果展示 + 手动配置入口 |
| 任务管理 | `/tasks` | 任务列表(状态/操作) + 执行历史 + 导入导出 |
| 执行报告 | `/report/:id` | 步骤时间线 + 截图查看 + 异常日志 + 耗时统计 |
| 设置 | `/settings` | 模型来源/API Key/Base URL + 截图质量 + 通知配置 |

**核心组件**：

| 组件 | 功能 |
|------|------|
| `RuleCard.vue` | 规则卡片展示，支持拖拽排序 |
| `RuleEditor.vue` | 点选配置条件/动作/参数 |
| `StepTimeline.vue` | 步骤回放时间线 |
| `ScreenshotViewer.vue` | 截图放大/切换 |

---

### 5.6 执行报告

**职责**：生成可视化 HTML 报告。

**报告内容**：任务概要 + 步骤回放(操作类型/目标/耗时) + 每步截图 + 自愈记录 + 最终结果

**核心类**：

```python
class ReportGenerator:
    def generate(task_config, step_logs, screenshots) -> str
        html = jinja2_template.render(
            task=task_config,
            logs=step_logs,
            screenshots=screenshots
        )
        save_to_file(html)
        return html_path
```

**清理策略**：超过30天的旧报告自动清理。

---

### 5.7 定时调度

**职责**：支持 cron/interval/date 三种触发模式，错过补执行。

**实现**：

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

class Scheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
    
    def add_job(self, task_id, schedule_config):
        # cron: "0 9 * * 1-5"  interval: {"hours": 2}  date: "2026-09-01 08:00"
        self.scheduler.add_job(execute_task, schedule_config.type, 
                               args=[task_id], **schedule_config.params)
    
    def check_missed(self):  # 开机后检查是否有错过的任务
        ...
```

配置持久化到 SQLite，应用重启后自动恢复。

---

### 5.8 操作录制

**职责**：录制用户浏览器操作，自动生成规则。

**流程**：

```
点击"开始录制" → 打开有头浏览器 → CDP监听(click/input/change)
→ 智能过滤(去重/去噪) → 实时转JSON → 点击"停止录制" → 回放验证
```

**智能过滤规则**：
- 1秒内同一元素重复点击 → 只保留1次
- 无输入内容的 focus/blur → 忽略
- 鼠标移动距离 < 10px → 忽略

**核心类**：

```python
class ActionRecorder:
    async def start(start_url) -> str              # 返回 session_id
    async def stop(session_id) -> List[RuleStep]   # 返回规则列表
    def _filter_noise(events) -> List[ActionEvent]  # 智能过滤
```

---

### 5.9 桌面应用封装

**技术选型**：Tauri 2.x，相比 Electron 打包体积小（~10MB vs 150MB+），内存占用低。

**Tauri 职责**：

1. **生命周期管理**：启动时拉起 FastAPI 后端子进程，关闭时清理
2. **系统托盘**：最小化到托盘，右键菜单（打开/退出），后台静默运行
3. **原生通知**：任务完成/失败时调用系统通知 API
4. **首次引导**：首次启动引导配置 API Key

**启动流程**：

```
双击应用 → Tauri启动 → 检查首次运行 → 引导配置API Key
    → 启动 FastAPI 子进程 (localhost:8710)
    → 等待后端就绪 (health check)
    → 加载前端页面
    → 用户正常使用
```

---

## 6. API 接口

**Base URL**: `http://localhost:8710/api`

### 任务管理

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/tasks` | 任务列表 |
| `POST` | `/tasks` | 创建任务 |
| `GET` | `/tasks/{id}` | 任务详情 |
| `PUT` | `/tasks/{id}` | 更新任务 |
| `DELETE` | `/tasks/{id}` | 删除任务 |
| `POST` | `/tasks/{id}/run` | 执行任务 |
| `POST` | `/tasks/{id}/stop` | 停止任务 |
| `GET` | `/tasks/{id}/history` | 执行历史 |

### 自然语言解析

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/nl/parse` | 解析自然语言为规则 |

### 执行报告

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/reports/{task_id}` | 最新报告 |
| `GET` | `/reports/{task_id}/{run_id}` | 某次报告详情 |
| `GET` | `/reports/{task_id}/{run_id}/screenshots/{step}` | 步骤截图 |

### 操作录制

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/recording/start` | 开始录制 |
| `POST` | `/recording/stop` | 停止录制 |
| `GET` | `/recording/status` | 录制状态 |

### 设置管理

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/settings` | 获取设置 |
| `PUT` | `/settings` | 更新设置 |
| `GET` | `/settings/providers` | 获取 LLM 服务商预设（免费/付费/自定义） |
| `POST` | `/settings/test-llm` | 测试 LLM 连接 |

### 系统

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/health` | 健康检查 |

---

## 7. 数据存储

### SQLite 表结构

```sql
-- 任务表
CREATE TABLE tasks (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    config      TEXT NOT NULL,       -- JSON 规则
    schedule    TEXT,                 -- JSON 定时配置
    speed_mode  TEXT DEFAULT 'normal',
    status      TEXT DEFAULT 'idle',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

-- 执行记录表
CREATE TABLE executions (
    id          TEXT PRIMARY KEY,
    task_id     TEXT NOT NULL,
    status      TEXT NOT NULL,       -- running/success/failed
    start_time  TEXT NOT NULL,
    end_time    TEXT,
    duration_ms INTEGER,
    report_path TEXT,
    error_msg   TEXT,
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);

-- 步骤日志表
CREATE TABLE step_logs (
    id              TEXT PRIMARY KEY,
    execution_id    TEXT NOT NULL,
    step_id         INTEGER NOT NULL,
    action_type     TEXT NOT NULL,
    target_element  TEXT,
    status          TEXT NOT NULL,
    duration_ms     INTEGER,
    screenshot_before TEXT,
    screenshot_after  TEXT,
    healing_actions TEXT,             -- JSON: 自愈过程
    error_info      TEXT,
    FOREIGN KEY (execution_id) REFERENCES executions(id)
);

-- 定位缓存表
CREATE TABLE locator_cache (
    id              TEXT PRIMARY KEY,
    cache_key       TEXT NOT NULL UNIQUE,
    url_pattern     TEXT NOT NULL,
    element_desc    TEXT NOT NULL,
    cached_selector TEXT,
    source_layer    INTEGER,          -- 1-4
    last_used_at    TEXT NOT NULL
);

-- 设置表
CREATE TABLE settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

### 文件存储

```
data/
├── app.db                    # SQLite
├── screenshots/{task_id}/{exec_id}/  # 截图
└── reports/{task_id}/{exec_id}/      # HTML 报告
```

---

## 8. 运行方式

### 环境要求

- Python 3.10+
- Node.js 18+
- Tauri 开发环境：Rust 1.75+（可选，纯前端开发时可跳过）

### 开发模式

```bash
# 后端
cd backend
pip install -r requirements.txt
playwright install chromium
uvicorn main:app --host 127.0.0.1 --port 8710 --reload

# 前端
cd frontend
npm install
npm run dev
# 浏览器打开 http://localhost:5173
```

### 打包为桌面应用

```bash
# 前端构建
cd frontend && npm run build

# 后端打包为 exe
cd backend && pyinstaller --onefile main.py

# Tauri 打包
npm run tauri build
# 输出安装包 → src-tauri/target/release/
```

---

## 9. 演示方案

### 答辩演示流程（建议 5-8 分钟）

**场景一：自然语言驱动（1分钟）**
输入"打开百度搜索大创项目"，系统自动解析为规则并执行。

**场景二：可视化配置（1分钟）**
手动拖拽配置一条签到任务，展示 RuleEditor。

**场景三：智能自愈演示（2分钟）** 
故意把选择器写错，展示系统从第1层降级到第3/4层，调用 LLM 视觉定位后自动恢复。

**场景四：操作录制（1分钟）**
点击"开始录制"，手动操作一遍网页，停止后自动生成规则，回放验证。

**场景五：执行报告（1分钟）**
展示刚执行完的报告：步骤时间线 + 截图 + 自愈记录 + 耗时统计。

**场景六：桌面应用（1分钟）**
展示 Tauri 打包的 exe，双击启动，系统托盘最小化，任务完成弹出系统通知。

> **演示建议**：重点突出自愈机制和创新性，这是区别于市面上同类工具的核心差异点。准备一个改版前后的网页对比 Demo，直观展示四层降级效果。

---

## 10. 免费模型接入

### 设计理念

项目 AI 能力采用**兼容 OpenAI 协议**的统一接口，不绑定任何单一服务商。通过切换 `base_url` + 模型名即可接入不同平台，**默认使用免费模型，无需付费 API Key**。

### 支持的服务商

| 服务商 | 费用 | 文本模型 | 视觉模型 | 说明 |
|--------|------|---------|---------|------|
| 硅基流动 SiliconFlow（默认） | 免费 | `Qwen/Qwen2.5-7B-Instruct` | `Qwen/Qwen2.5-VL-7B-Instruct` | 国内直连，注册送免费额度，文本+视觉均免费 |
| 智谱 AI | 免费 | `glm-4-flash` | `glm-4v-flash` | GLM-4-Flash 永久免费，中文能力强 |
| 通义千问 DashScope | 付费 | `qwen-plus` | `qwen-vl-plus` | 原默认服务商 |
| 自定义 | — | 任意 | 任意 | 任意 OpenAI 兼容服务 |

### 架构说明

```python
# config.py —— 服务商预设（供前端下拉选择）
LLM_PROVIDERS = [
    { "id": "siliconflow", "base_url": "https://api.siliconflow.cn/v1",
      "model": "Qwen/Qwen2.5-7B-Instruct", "vl_model": "Qwen/Qwen2.5-VL-7B-Instruct",
      "register_url": "https://cloud.siliconflow.cn/account/ak" },
    # ...
]

# llm_client.py —— 统一调用，base_url/model/key 均可从设置动态读取
class LLMClient:
    async def chat(messages, model=None)        # 文本对话（决定 base_url + model）
    async def chat_json(messages, ...) -> dict  # 文本 + 强制 JSON 输出
    async def vision(image, prompt) -> str      # 视觉定位（使用 vl_model）
```

关键实现要点：

1. **配置优先级**：设置页保存的 key/base_url/model > 环境变量 > 默认免费模型
2. **base_url 持久化**：`SettingsUpdate` 含 `base_url` 字段，保存到 SQLite `settings` 表
3. **前端引导**：设置页「API Key」下方提供「获取免费 Key」链接，随所选服务商自动切换跳转地址

### 使用步骤

1. 打开「设置」页 → 「模型来源」选择 **硅基流动（免费·推荐）**
2. 点击输入框下方「获取免费 Key」链接，注册并复制 API Key
3. 粘贴 Key → 保存 → 点击「测试连接」验证
4. 回到「指令输入」页即可用自然语言创建任务

### 打包分发时的 Key 处理

打包为 exe 后，`config.py` 会在 `sys.frozen` 时自动把数据目录切换到 **exe 同级目录**，用户填写的 Key 与任务数据可持久化保存（避免 onefile 模式下写临时目录导致数据丢失）。

> **推荐做法**：分发时让用户自行注册免费 Key 填写，额度独立、互不影响。不推荐把个人 Key 预置进安装包（会泄露且免费额度被多人共用耗尽）。

---

> **文档维护**：随开发进度持续更新，代码实现后补充实际函数签名和 API 响应示例。