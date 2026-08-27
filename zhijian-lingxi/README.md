# 智简灵析

面向普通办公人员的智能网页自动化助手。用自然语言描述需求，系统自动解析为浏览器操作并执行，以桌面应用形式交付。

## 核心特性

- **自然语言驱动**：说人话就能创建自动化任务
- **四层智能自愈**：页面改版也能自动重新定位元素
- **可视化配置**：拖拽编排规则
- **操作录制**：录一遍操作自动生成规则
- **桌面应用**：Tauri 封装，一键安装，本地运行

## 项目结构

```
zhijian-lingxi/
├── frontend/          # Vue 3 + TypeScript + Element Plus
├── backend/           # FastAPI + Playwright + APScheduler
└── src-tauri/         # Tauri 2.x 桌面壳 (Rust)
```

## 开发运行

### 后端

```bash
cd backend
pip install -r requirements.txt
playwright install chromium
uvicorn main:app --host 127.0.0.1 --port 8710 --reload
```

### 前端

```bash
cd frontend
npm install
npm run dev
# 打开 http://localhost:5173
```

## 打包桌面应用

```bash
cd frontend
npm install
npm run build

# 后端打包 exe
cd ../backend
pyinstaller --onefile main.py

# 生成图标（首次需准备 src-tauri/icons/app-icon.png）
cd ../frontend
npm run tauri icon

# Tauri 打包
npm run tauri build
```

## 首次使用

启动后在「设置」页配置通义千问 API Key（qwen-plus / qwen-vl-plus），即可使用自然语言解析与智能自愈视觉定位能力。详细的架构与技术说明见项目根目录的 `Code-Wiki.md`。