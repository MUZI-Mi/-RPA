# 智简灵析

**面向基层政务的 AI 智能自动化系统**：专为街道办、社区等基层单位打造的「数字员工」，集**自动执行 + 智能风控 + 隐私合规**于一体。用自然语言描述需求，系统自动解析为浏览器操作并执行，以桌面应用形式交付。

> 支持：自然语言建任务 · 录制一遍生成规则 · 页面改版自动重定位（四层智能自愈）· 读取/清洗/总结多格式数据 · 导出报表 · 合规脱敏与人工审核。

### 对待 AI 风险的原则

为避免 AI 黑盒决策带来的风险，系统采用**严格权限隔离 + 人工兜底机制**：AI 负责执行与初判，但**最终拦截、通过需经人工二次确认**，做到「AI 辅助、人来把关」，让基层既有办事效率，又守住合规底线。

## 核心特性

- **自然语言驱动**：说人话就能创建自动化任务，支持多轮修改
- **操作录制**：录一遍真实操作，自动生成带中文备注的规则
- **四层智能自愈**：页面改版也能自动重新定位元素，点不错、不擅停
- **数据加工闭环**：`read_excel/read_csv/read_pdf` 读本地文件 → `data_clean` 清洗 → `llm_summarize` AI 总结 → `export` 导出报表
- **PDF 解析（含扫描件 OCR）**：`read_pdf` 一键读取本地 PDF——文本型直接抽文字/表格（无需联网），扫描件自动渲染成图走大模型 OCR 识别文字或结构化表格
- **合规三件套**：PII 脱敏网关、人工审核队列、操作审计日志
- **权限隔离 + 人工兜底**：AI 只做执行与初判，高危动作/敏感数据经人工二次确认才放行，全程留痕可追溯
- **报表模板中心**：Excel/Word 模板占位符填充，导出 csv/json/xlsx/docx/pdf 五种格式
- **桌面应用**：Tauri 封装，本地运行；默认接管用户已开的浏览器（保留登录态），也支持内置浏览器（源码环境）

### 文档报表的自动总结与导出（告别表海与数据孤岛）

基层最常见的是「表海」和「数据孤岛」：海量报表散落在各系统/Excel/PDF/扫描件里，格式不一、互不相通。本系统的数据处理链路把散落数据汇聚成**一条可复用的流水线**：

```
read_pdf/read_excel/read_csv  →  统一成表格(__table)
        ↓  data_clean                去重/补空/统一格式
        ↓  llm_summarize             AI 自动总结 + 异常预警（如金额越界）
        ↓  export                    按模板填充 / 直接导出
                                    csv | json | xlsx | docx | pdf
```

- **能读各种「孤岛」**：Excel(.xlsx/.xls)、CSV、PDF（含扫描件 OCR），把分散数据拉进同一张表。
- **能自动总结**：AI 按数据生成要点小结，并自动标出异常项，替代人肉逐行看表。
- **能一键导出**：Excel/Word 模板占位符填充，或直接导出五种格式；报表结果还支持人工二次确认后再下发。
- **解决什么**：一条流水线把「读-洗-析-出」串成自动链路，基层不用再手工复制粘贴、不再各自为政，报表从「散落的表海」变成「统一可复用的基座」。

## 技术栈

| 层 | 技术 |
|---|---|
| 桌面壳 | Tauri 2 (Rust) |
| 前端 | Vue 3 + TypeScript + Element Plus + Vite |
| 后端 | Python 3.13 + FastAPI + uvicorn + Pydantic 2 |
| 浏览器自动化 | Playwright（异步），支持 CDP 接管调试浏览器 |
| 调度 | APScheduler |
| 存储 | SQLite（任务 / 执行记录 / 执行报告 / 设置 / 审核 / 审计） |
| 文件解析 | openpyxl(.xlsm) + xlrd(.xls) 读 Excel；pdfplumber + pymupdf 读 PDF；python-docx / reportlab 生成 Word/PDF |
| LLM | 统一 OpenAI 兼容协议，双模型（文本 + 视觉），4 家服务商预设 |

## 项目结构

```
zhijian-lingxi/
├── frontend/          # Vue 3 + TypeScript + Element Plus
│   └── src/pages/     # Instruction 指令 / Tasks 任务 / Review 审核 /
│                      # AuditLog 审计 / Templates 模板 / Report 报告 / Settings 设置
├── backend/           # FastAPI + Playwright + APScheduler
│   ├── main.py        # FastAPI 入口与 API 路由
│   ├── executor.py    # 任务执行器（26 种动作分发与数据流水线）
│   ├── self_healing.py# 四层智能自愈元素定位
│   ├── nl_parser.py   # 自然语言 → 规则 JSON 解析与多轮精炼
│   ├── recorder.py    # 操作录制器
│   ├── llm_client.py  # LLM 统一调用（文本/视觉/OCR）
│   ├── template_engine.py # 报表模板引擎
│   ├── pii.py / review.py / audit.py   # 合规三件套
│   ├── scheduler.py / notifier.py / report.py
│   └── config.py / models.py / database.py / rule_engine.py
└── src-tauri/         # Tauri 2.x 桌面壳 (Rust)
```

## 项目文档

- **[README.md](.)**：本项目。快速上手、环境搭建、使用与打包指南。面向用户与开发者。
- **[Code-Wiki.md](./Code-Wiki.md)**：架构与实现详解——技术栈、四层自愈、OCR 链路、数据流水线、合规三件套（脱敏网关等）、关键设计决策。面向开发者与维护者。
- 文档随代码维护：README 讲「怎么用」，Code-Wiki 讲「怎么运转」。

## 环境要求与搭建（交接/协同开发用）

本仓库的开发环境不绑定任何特定 IDE。以下任一组合均可用：**VS Code / JetBrains（PyCharm、WebStorm）/ Vim / Trae** 等，后端本质是标准 Python 工程、前端是标准 npm 工程、桌面壳是标准 Rust 工程。下表给出已开发验证的版本与最低要求：

| 组件 | 用途 | 已用版本（建议） | 说明 |
|---|---|---|---|
| Python | 后端 | **3.13.15**（≥3.10） | 依赖基于 3.10+ 语法 |
| Node.js | 前端 | **v24.14.1**（≥18） | Vite 6 要求较高 Node |
| npm | 前端包管理 | **11.11.0** | 随 Node 附带 |
| Rust 工具链 | Tauri 桌面壳 | **rustc/cargo 1.98.0** | **仅改桌面壳/打包时需要**；纯前后端开发可跳过 |
| Edge/Chrome | 浏览器自动化 | 任意新版 | 接管模式用（CDP 9222） |

> Rust 仅在你需要改 `src-tauri/` 或执行 `npm run tauri build/i` 时才必需。日常只改前后端逻辑不需要装 Rust。安装指引见[官网](https://www.rust-lang.org/tools/install)。

### 一、拉取与初始化依赖

```bash
git clone <仓库地址>
cd zhijian-lingxi
```

### 二、后端环境（Python 虚拟环境）

```bash
cd backend
python -m venv .venv                # 创建虚拟环境（隔离依赖，强烈建议）
# Windows:
.venv\Scripts\activate
# macOS / Linux:
# source .venv/bin/activate

# 国内加速（可选，本机一直用清华源）
python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# 未加速时的常规安装
pip install -r requirements.txt

# 安装 Playwright 浏览器（仅内置浏览器模式需要）
playwright install chromium
```

> 依赖清单见 `backend/requirements.txt`（fastapi / uvicorn / playwright / pydantic / APScheduler / openpyxl / xlrd / pdfplumber / pymupdf / python-docx / reportlab 等）。新增依赖后请同步更新该文件：`pip freeze > requirements.txt`（或手动登记）。

### 三、前端环境（Node 依赖）

```bash
cd frontend
# 国内加速（可选）
npm config set registry https://registry.npmmirror.com
npm install
```

### 四、运行（后端 + 前端）

**后端**（端口 8710）：
```bash
cd backend
python -m uvicorn main:app --host 127.0.0.1 --port 8710
```
> ⚠️ **Windows 下严禁加 `--reload`**，见「常见问题」。

**前端**（端口 5173）：
```bash
cd frontend
npm run dev
# 浏览器打开 http://localhost:5173
```

### 五、目录隔离与数据

- 运行时数据（SQLite、截图、报告、导出文件）全部落在 `backend/data/`，已被 `.gitignore` 忽略，**不上传 Git**，各开发者本地自建。
- 模板中心上传的模板文件落在 `backend/templates/`，其中以中文命名/含元数据的内容以数据库 `templates` 表为准。
- API Key 等用户设置存于 SQLite 的 `settings` 表，不写进代码；也可用环境变量覆盖 `config.py` 的默认值：`LLM_BASE_URL`（默认硅基流动）/ `LLM_API_KEY`。可参考 `backend/.env.example`（注意后端未用 dotenv，`.env` 需自行加载或直接改 `config.py`）。

### 六、打包（仅发布/桌面分发时需要）

见下文「打包桌面应用」。打包需 Rust 工具链，且首次需准备 `src-tauri/icons/app-icon.png` 后执行 `npm run tauri icon`。

### 七、跨 IDE / 协同开发注意事项

- 三个子工程相互独立：可分别用不同工具打开 `backend/`、`frontend/`、`src-tauri/`。
- 前端路径别名 `@/*` 在 `tsconfig.json` 与 `vite.config.ts` 两处配置，新增导入若报找不到类型，检查这两处。
- 类型检查：`cd frontend && npm run build`（内含 `vue-tsc --noEmit`）。
- 后端新增动作/字段时，需同步更新：`backend/models.py` 的 `Literal` 联合、`backend/rule_engine.py` 的校验白名单、`frontend/src/types/index.ts` 的动作联合类型，以及前端动作中文标签映射（RuleCard / StepTimeline / Instruction）。

## 快速开始

### 1) 启动后端

```bash
cd backend
pip install -r requirements.txt
playwright install chromium   # 仅内置浏览器模式需要
python -m uvicorn main:app --host 127.0.0.1 --port 8710
```

> **Windows 下不要加 `--reload`**：`--reload` 会让 uvicorn 改用 SelectorEventLoop，它不支持子进程，Playwright 启动浏览器驱动会直接抛 `NotImplementedError`，表现为任务执行 steps=0 失败。改代码后手动重启后端。

### 2) 启动前端

```bash
cd frontend
npm install
npm run dev
# 打开 http://localhost:5173
```

### 3) 配置 API Key

在「设置」页选择一个模型来源（推荐 **智谱 AI**，GLM-4-Flash 永久免费；或**硅基流动**，注册送免费额度、国内直连），填入对应平台的 API Key 并保存。自然语言解析、AI 总结、OCR、自愈第 3/4 层视觉定位均依赖它。

不配置也可使用：录制器、规则手动编排、read_excel/read_csv/read_pdf（文本/表格模式）、data_clean、export、foreach 等不依赖 LLM 的功能。

## 第一次使用

1. 「指令」页用一句话描述任务（如「逐个打开公告列表，提炼每条要点，导出 Excel」），AI 解析成规则；或在规则编辑器手动编排 / 用录制器录一遍。
2. 「任务」页可以看到每条规则的步骤树，可二次编辑后手动执行。
3. 执行过程有实时日志，结束后在「报告」页查看执行报告与导出的文件。
4. 涉及脱敏/需人工确认的数据会进入「审核」页队列，「审计」页留痕每次操作。

## 浏览器模式

- **接管浏览器**（**默认**，推荐用于登录态/内网）：设置页默认选「接管我的浏览器」，先在系统里用调试参数打开浏览器：

```bash
# 用调试端口 9222 启动 Edge/Chrome（用户数据目录务必用纯英文路径）
msedge.exe --remote-debugging-port=9222 --user-data-dir="C:\edge-profile"
```

任务执行与**操作录制**都会接管这个已登录的浏览器实例，执行完保留登录态，可连续复用。
- **内置浏览器**：设置页选「内置浏览器」，任务执行时自动拉起 Chromium，无痕运行。仅源码开发环境可用——**打包版不捆绑浏览器内核，内置模式不可用**，录制/执行均须走接管模式。

## 打包桌面应用

桌面应用由两部分组成，需分别打包后按固定布局组合：

```bash
# 1) 构建前端静态资源
cd frontend
npm install
npm run build

# 2) 打包后端 exe（--noconsole 隐藏黑窗口，后台静默运行）
cd ../backend
pyinstaller --onefile --noconsole --name 智简灵析后端 --clean main.py

# 3) 生成图标（首次需准备 src-tauri/icons/app-icon.png）
cd ../frontend
npm run tauri icon

# 4) 打包 Tauri 桌面壳（自动启用 custom-protocol，前端资源内嵌进 exe）
npm run tauri build
# 若需手动 cargo 编译，务必带 feature：
# cd ../src-tauri && cargo build --release --features custom-protocol
```

### 分发布局（必须按此结构）

```
publish/
├── zhijian-lingxi.exe        # 桌面壳（双击即启动，自动拉起后端）
└── backend/
    └── 智简灵析后端.exe         # 后端（无窗口静默运行）
```

壳启动时会按以下顺序查找后端并拉起（找到即停）：`backend/智简灵析后端.exe` → 同级 `智简灵析后端.exe` → `backend/main.exe`（旧约定）。退出壳时自动结束后端进程。

### 无窗口后端的日志排障

`--noconsole` 打包下 `sys.stdout/stderr` 为 None，uvicorn 写日志会直接崩溃。后端入口 [main.py](backend/main.py) 已在引导期将输出重定向到 `data/logs/backend.log`（路径先 `mkdir` 再打开，否则引导阶段抛 `FileNotFoundError`）。隐藏模式下排查问题请查看该日志文件。

### 已知打包坑（勿踩）

- **`tauri` 无 `notification-all` feature**：`Cargo.toml` 里写该 feature 会编译失败，消息通知由 `tauri-plugin-notification` 提供，无需声明。
- **`tauri.conf.json` 的 `plugins.notification` 必须为 `null`**：写成 `{}` 会在启动时 panic（exit 101）。
- **手动 `cargo build` 必须带 `--features custom-protocol`**：否则壳回退加载 `devUrl`（localhost:5173），运行时显示「无法访问此页面」。

> 打包后用户数据（API Key、任务、历史、导出文件）会存放在 exe 同级目录的 `data/` 下，避免静默丢失。浏览器内核不随包分发：用户端通过「接管浏览器」模式使用系统自带的 Edge/Chrome。

## 常见问题

- **执行 steps=0 直接失败**：后端启动带了 `--reload`？重启为不带 reload 的标准启动方式。
- **接管模式浏览器打不开/崩溃**：`--user-data-dir` 用了中文路径？改用纯英文目录。
- **自然语言解析结果很差**：当前用的免费模型较弱。换更强的模型（如 GLM-4-Flash / 通义付费模型），且描述尽量口语化、明确步骤。
- **PDF 扫描件识别为空白**：扫描件无文字层会走 OCR，需要已配置视觉 API Key；纯文本/表格 PDF 无需联网。
- 更完整的架构与设计说明见随项目附带的 **`Code-Wiki.md`**。

## 许可

本项目为自主开发，用于教学与办公自动化场景。