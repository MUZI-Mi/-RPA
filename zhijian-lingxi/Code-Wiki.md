# Code-Wiki —— 智简灵析 架构与实现说明

本文档面向开发者/维护者，深入讲解系统架构、核心机制与关键设计决策。配套入门指南见 `README.md`。

---

## 1. 总体架构

```
┌─────────────────────────────────────────────────────────────┐
│                     桌面壳 src-tauri (Tauri 2 / Rust)        │
└───────────────────────────────┬─────────────────────────────┘
                                │ (Tauri 内嵌加载 dist)
┌───────────────────────────────▼─────────────────────────────┐
│                      前端 frontend (Vue3+TS)                 │
│  指令 Instruction │ 任务 Tasks │ 审核 Review │ 审计 AuditLog  │
│  模板 Templates │ 报告 Report │ 设置 Settings                │
└───────────────────────────────┬─────────────────────────────┘
                                │ HTTP/JSON  (http://127.0.0.1:8710)
┌───────────────────────────────▼─────────────────────────────┐
│                      后端 backend (FastAPI)                  │
│  ├─ nl_parser      自然语言 → 规则 JSON（多轮精炼）          │
│  ├─ recorder       操作录制（CDP 监听）                      │
│  ├─ executor       任务执行器（26 种动作 + 数据流水线）      │
│  │   ├─ self_healing  四层自愈元素定位                       │
│  │   └─ template_engine 报表模板与导出                      │
│  ├─ pii / review / audit    合规三件套                       │
│  ├─ scheduler(APScheduler) / notifier / report              │
│  └─ database (SQLite)                                       │
└───────────────────────────────┬─────────────────────────────┘
                                │ CDP(9222) / Playwright
                    ┌───────────▼───────────┐
                    │  浏览器(内置/接管)    │
                    └───────────────────────┘
```

- **通信**：前端是纯 Web 应用，后端是独立 FastAPI 服务。前端 → 后端走 HTTP；`src-tauri` 只是把构建好的前端包成桌面壳。
- **数据存储**：单文件 SQLite（`backend/data/app.db`），存任务规则、执行记录与步骤日志、执行报告、设置、审核队列、审计日志、模板元数据。

---

## 2. 规则数据模型

一条任务 = 若干按序执行的**步骤（step）**，每步含 `action`（动作）与 `condition`（触发条件）。见 [models.py](backend/models.py) 的 `Action` / `Condition`。

**26 种动作**，按能力分五组：

| 分组 | 动作 |
|---|---|
| 浏览器操作 | open、click、input、select、upload、scroll、hover、press_key、reload、back、forward、close_tab |
| 提取与变量 | extract、set_var |
| 流程控制 | goto、if_text、if_element、if_var、foreach、foreach_if |
| 本地数据读取 | read_excel、read_csv、read_pdf |
| AI 与加工 | ocr、ocr_to_json、llm_extract、data_clean、llm_summarize、export |

**变量贯穿**：`extract`/`read_*` 可写 `__变量`；`set_var`/`{{变量}}` 语法在规则中动态引用；数据加工动作通过 `__table` 变量在步骤间传递表格数据，形成「读取 → 清洗 → AI → 导出」的闭环。

---

## 3. 四层智能自愈（元素定位降级链）

核心文件：[self_healing.py](backend/self_healing.py)。当动作需要定位一个元素时，从最可靠到最兜底逐层尝试，**任一命中即返回**。

> 实际降级顺序以代码为准（与早期文档注释略异）。关键在「把意识放在意图上，而不是一上来就信 CSS」。

完整定位尝试顺序：

```
0. 文本精确定位（get_by_text）   ← 录制时的元素文字最稳，优先级最高
1. 第1层：CSS 选择器唯一匹配（多匹配时按意图文字 :has-text 精确定位）
2. 位置序号定位（"第N个"直接数真实可见链接，不靠模型猜）
3. 定位缓存（复用历史第1~4层成功结果，需重新验证通过才用）
4. 第2层：属性/文字语义模糊匹配（data-testid/aria-label/placeholder/id/name/title）
5. 第3层：精简 DOM(≤150 节点) → 文本模型返回选择器（置信度≥0.75 且验证通过）
6. 第4层：截图 → 视觉模型返回坐标（经 elementFromPoint + 锚点文字跨层验证）
```

### 3.1 各层要点

- **文本精确定位**（[`_text_locate`](backend/self_healing.py#L190)）：从意图里提取 `「」` 中的文字，先精确后模糊；模糊只接受**短标签**（长度 ≤ 目标 2 倍 + 4），避免「原创」误点中长标题视频卡片。返回带 `nth=` 的选择器，精确锁定验证通过的那**一个**元素。
- **第1层 CSS**（[`_layer1`](backend/self_healing.py#L149)）：计数唯一直接命中；匹配多个时用意图文字 `:has-text` 过滤；仍无法区分则降级。
- **位置序号定位**（[`_ordinal_locate`](backend/self_healing.py#L248)）：识别「第N个」（中文/阿拉伯数字都支持，`_cn_to_int`），按目标类型（视频链接/通用链接按钮）从页面可见元素取第 N 个，杜绝模型编造假选择器。
- **第2层模糊**（[`_layer2`](backend/self_healing.py#L298)）：按属性优先级链生成 `[attr*='关键词']` 候选逐个尝试，需可见。
- **第3层 DOM 分析**（[`_layer3`](backend/self_healing.py#L333)）：仅保留可见可交互元素的骨架快照（≤ `DOM_MAX_NODES=150`）发给文本模型，要求返回 `{selector, confidence}`；意图是「第N个」时提示模型按列表序号挑，降低自由发挥。异常一律 return None 继续降级。
- **第4层视觉定位**（[`_layer4`](backend/self_healing.py#L369)）：
  - 若意图是**纯 CSS 选择器**（录制器存的精确选择器）直接跳过——视觉模型看不懂 CSS，会瞎猜坐标导致误点。
  - 截图发给视觉模型返回 `{x, y}`（相对比例）。
  - 点击前用 `elementFromPoint` 验证该坐标处确有可交互元素（a/button/input/select/textarea 或其可交互祖先）。
  - **跨层锚点验证**：坐标处元素文字须与意图标签互相包含（`_anchor_match`），否则拒绝，防点错相邻元素。
- **缓存**：`locate` 定位成功会写 SQLite 定位缓存（key=`url::intent::selector`），后续命中且重新验证通过即可复用，避免反复走 LLM。

### 3.2 低信任点击的主动视觉复核

[`is_low_trust`](backend/self_healing.py#L442) 判定「此点击是否可信」：

- 意图**无真实标签**（只有 CSS）→ 低信任；
- 意图是`第N个`位置描述 / 含选择器语法（录制器存的精确 CSS）/ 短真实标签 → 高信任，无需复核；
- 低信任时触发 [`visual_confirm`](backend/self_healing.py#L466)：截取命中元素截图问视觉模型「是不是用户想点的目标」，返回 yes/no，防止误点相邻元素。

---

## 4. 自然语言建任务

核心：[nl_parser.py](backend/nl_parser.py)。把口语描述解析成规则 JSON：

- **零样本解析**：配置里没有样板规则时，用带示例的提示词让文本模型直接输出规则 JSON（`steps` 必须是对象数组，禁止字符串数组）。
- **多轮精炼**：用户追加新要求时，把「当前规则 JSON + 修改要求」给模型，输出**完整新的规则 JSON**（仅改指定部分、保留其余、重新编号 `step_ids`、更新 `notes`），前端记录「已更新（第 N 次）」。
- **健壮性清洗**（`rule_engine.py` / 解析后处理）：
  - 丢弃空 `action` 对象（无 `type`）；
  - 兜底空对象；
  - 空规则/空步骤数组自动重试；
  - 「逐个打开/看完关闭/翻页」类意图被强制合并为单个 `foreach`，防止生成几十个线性 `click`；
  - 超长/注入式选择器（>10 层或 >300 字符）自动截断或改文字定位；
  - 模型一旦输出字符串步骤数组即判定失败并重试。

**经验教训**：Qwen2.5-7B 等小模型处理嵌套 JSON 会缺字符/死循环，统一用 **14B 或更强**的文本模型。

---

## 5. OCR 链路（大模型 OCR）

不是 PaddleOCR/Tesseract，而是**多模态大模型直接读图**，统一入口为 [llm_client.py](backend/llm_client.py#L119) 的 `LLMClient.ocr`。三个入口共用同一条链路：

```
入口：ocr 动作(截图) / ocr_to_json 动作(截图→字段) / read_pdf 扫描件(pymupdf渲染成图)
  └→ 前端截图/图片字节
      └→ 视觉模型 OCR 读图
          ├→ ocr            直接返回全部文字
          └→ ocr_to_json   按指定字段结构化 → 表格行(__table)
```

- `ocr_to_json`：让模型按字段描述整理成结构化数据（如"姓名,金额"），供后续 data_clean/export 复用。
- `read_pdf` 扫描件路径：`pymupdf` 把每页渲染成 PNG → 走同一 OCR 链路（需视觉模型）；纯文本/表格 PDF 用 `pdfplumber` 直接抽文字/表格，**无需联网**。
- 所有进 AI 的数据先过 **PII 脱敏网关**（见 §7），防止身份证等明文泄漏。

---

## 6. 数据流水线（加工闭环）

任务里常这样编排数据加工步骤，变量 `__table` 串联：

```
read_excel/read_csv/read_pdf  →  __table（本地文件 → 表格行，[ {列:值} ... ]）
        ↓
data_clean                    →  清洗后的 __table（去重/补空/日期统一等）
        ↓
llm_summarize                 →  AI 总结 + 异常预警（附到每行 + 汇总段）
        ↓
export                        →  模板填充 / 直接导出  csv|json|xlsx|docx|pdf
```

- 读取动作未显式指定 `save_as` 时自动写入 `__table`，保证链路通畅。
- `read_excel`：`.xlsx/.xlsm` 用 openpyxl，老式 `.xls` 用 xlrd（openpyxl 不支持 `.xls`），按扩展名自动分派；无表头按 A/B/C 列名。
- `read_pdf`：`pdf_extract ∈ {auto,text,table,ocr}`，`auto` 逐页判断（扫描件自动转 OCR），`pdf_page` 只解析指定页。
- `export` + [template_engine.py](backend/template_engine.py)：`{{占位符}}` 替换、`{{__rows__}}` 处展开表格行；无模板则直接由数据表生成文件。导出 PDF 用 reportlab，需注册中文字体避免乱码。

---

## 7. 合规三件套

### 7.1 PII 脱敏网关 —— [pii.py](backend/pii.py)

数据进 AI 前的「过滤闸门」：AI 是黑盒，无法保证不泄漏敏感信息，故在**所有送 AI 的边界**统一拦截。

**方案：可逆掩码（规避正则 + 占位符还原）**

```
明文 →（正则识别）→ 占位符 @MASK_1@ → 送 LLM → 结果 →（映射还原）→ 明文
```

- 不用「替换成 `***`」这种不可逆脱敏：AI 总结后结果还要存回业务数据。
- 占位符 `@MASK_{n}@` 刻意不用 `{{}}`，避免与规则 `{{变量}}`、模板 `{{占位符}}` 冲突。
- `mask`/`unmask` **只在单次 LLM 调用局部**成对出现，外部永远存明文；缺占位符绝不静默丢弃（记入 missing）。

**内置正则规则**（边界限定，见 `_RULES`）：

| 规则 | 内容 | 细节 |
|---|---|---|
| id_card / id_card15 | 18 / 15 位身份证 | 前后 `(?<!\d)(?!\d)` 边界限定，避免匹配到更长数字串的一部分；15 位规则放在银行卡前，兜底 60/62 开头的 15 位卡 |
| phone | 手机号 | 1[3-9] 开头 11 位 |
| bank_card | 银行卡 | 62/60 开头 14~18 位 |
| email | 邮箱 | 标准电邮正则 |
| plate | 车牌 | 省份简称 + 字母 + 5~6 位 |
| landline | 座机 | 0 + 区号 + 号码 |

**占位符编号（塌缩 bug 修复）**：`_placeholder_for`（[L62](backend/pii.py#L62)）用共享 mapping + state——**相同值复用同一占位符**（保持上下文简短、还原一致），**不同值分配不同占位符**。早期每个字符串独立编号导致全部塌缩成 `@MASK_1@`，还原串值；现「张三→@MASK_1@、李四→@MASK_2@」一一对应。

**姓名处理：不做全文正则**（2~4 个纯中文的全文正则灾难性误伤「北京」「工作」等普通词），只对两类**整值占位**：
- `name_fields` 指定列（如「姓名」列）值若为 2~4 个纯中文（`_NAME_RE`）则整体掩码；
- `extra_terms` 显式名单（手动传入的姓名列表）。
- 支持 `dict` 与 **`list[dict]`** 递归（表格行场景），修复过「只处理顶层 dict、行列表姓名明文泄漏」的 bug。

**对外方法**

| 方法 | 参数 | 用途 |
|---|---|---|
| `mask(text, extra_terms)` | 文本 + 可选名单 | 文本级掩码 → `(掩码文本, mapping)` |
| `unmask(text, mapping)` | 掩码文本 + 映射 | 还原；缺失占位符原样保留并计入 missing |
| `mask_dict(d, name_fields)` | dict/list + 姓名列 | 递归掩码整个结构 |
| `unmask_dict(d, mapping)` | 掩码结构 + 映射 | 递归还原 |
| `mask_json_rows(rows, name_fields)` | 表格行 | `json.dumps` 后整体掩码，供整表送 LLM |

**接入点与风险闭环**：在 `llm_extract` / `llm_summarize` / `ocr_to_json` 送 AI 前 `mask`、返回后 `unmask`，落库永远是明文。`is_enabled()` 读设置 `pii_masking_enabled`（默认开启）。脱敏 = 防「AI 把敏感信息带进上下文/输出」的第一道防线，与「人工二次确认」构成双重兜底：AI 只见脱敏数据，产出经人工把关，最后落库才还原。

### 7.2 人工审核队列 —— [review.py](backend/review.py)

- 数据清洗/AI 总结等步骤判定异常（如金额越界）、或需人工确认时，把记录写入审核队列（pending）。
- 前端「审核」页可逐条 `通过 / 驳回 / 修改后通过`；审核结论回流到任务结果。

### 7.3 操作审计日志 —— [audit.py](backend/audit.py)

对敏感操作（任务创建/编辑/执行/导出/审核等）记录：时间、操作人、动作类型、对象、前后摘要，不可篡改地追加日志，供「审计」页追溯。

---

## 8. 执行调度与报告

- **调度**：[scheduler.py](backend/scheduler.py) 基于 APScheduler，支持立即/定时/周期运行任务；到点把任务放入后台异步执行（`_schedule_dispatch` → `asyncio`）。
- **执行**：[main.py](backend/main.py#L75) `_run_task_by_id`：标记任务运行中 → 建执行记录 → 调 `executor.run` → 写步骤日志与执行记录 → 生成报告 → 通知。幂等地清 `_running_tasks`，确保状态一致四库。
- **报告**：[report.py](backend/report.py) 汇总步骤状态/耗时/每步自愈动作链/错误信息，前端「报告」页可视化；30 天自动清理。
- **通知**：[notifier.py](backend/notifier.py) 执行成败可选推送通知（桌面/邮件等）。

---

## 9. 浏览器接管（attach / CDP）

关于内置浏览器与接管模式，关键细节：

- **内置浏览器**：设置页选「内置浏览器」，`executor.run` 里 headless 由设置控制，自动拉起 Chromium。开发环境（源码跑）可用；**打包版不捆绑浏览器内核，内置模式不可用**。
- **接管模式**（**默认**，`browser_mode=attach`）：设置页选「接管我的浏览器」+ 填 CDP 地址（默认 `http://127.0.0.1:9222`），`executor` 用 Playwright `connect_over_cdp` 接管**已用调试端口启动**的浏览器，复用其登录态。执行完**不关浏览器、不断连接**，保留状态供任务复用。
- **录制器跟随同一设置**：`recorder.start` 不再硬编码 `chromium.launch`，同样读 `browser_mode`——`attach` 时 `connect_over_cdp` 接管调试浏览器，并在**独立新 context** 录制（不干扰用户已有标签页）；仅 `builtin` 才用内置 Chromium。打包版录制因此必须依赖接管模式，且录制前需先启动调试浏览器。
- **硬性约束**：
  - Chromium `--user-data-dir` 必须是**纯英文路径**，中文路径启动即崩溃。
  - 按键监听、关闭标签、前进后退等浏览器级操作由录制器通过 CDP 捕获/执行。

---

## 10. 关键设计决策与经验教训

1. **uvicorn 不带 `--reload`**（Windows）：`--reload` → SelectorEventLoop → 不支持子进程 → Playwright 驱动启动报 `NotImplementedError`，任务 steps=0 失败。
2. **`closed` 事件循环/残留会话**：录制会话未正常停止会让全局标记卡在 `True`，必须在任务开始时强制清理。
3. **选择器过度嵌套**：LLM 可能生成上百层 div 选择器，强制长度/层级上限，优先文字定位。
4. **LLM 输出不可信**：字符串步骤数组、空 action、截断 JSON 都要在清洗阶段兜底重试。
5. **freeze 打包数据目录**：单文件 exe 下 `__file__` 指向临时目录，`BASE_DIR` 须改为 exe 同级目录，防用户数据重启丢失。
6. **OCR/视觉定位需视觉模型 + API Key**；纯文本/表格处理（read_excel/csv/pdf-text、data_clean、export、foreach、录制器）不依赖 LLM。
7. **打包版无内置浏览器**：方案 A 不捆绑 Chromium 内核，`browser_mode` 默认 `attach`，录制/执行都须接管用户已调试启动的浏览器；录制器须与执行器一致地读 `browser_mode`（不能硬编码 `chromium.launch`），否则打包版录制必失败。