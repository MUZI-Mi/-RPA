"""配置管理模块

集中管理应用配置：路径、服务端口、LLM API 配置等。
配置支持从环境变量读取，并持久化到 SQLite settings 表。
"""

import os
import sys
from pathlib import Path

# === 基础路径 ===
def _is_frozen() -> bool:
    """判断是否运行于 PyInstaller 打包后的环境。"""
    return getattr(sys, "frozen", False)


if _is_frozen():
    # 打包运行时：数据目录放到 exe 同级目录，
    # 避免 onefile 模式下 __file__ 指向临时解压目录导致数据丢失。
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data"
SCREENSHOT_DIR = DATA_DIR / "screenshots"
REPORT_DIR = DATA_DIR / "reports"
TEMPLATE_DIR = BASE_DIR / "templates"
DB_PATH = DATA_DIR / "app.db"

# === 服务配置 ===
HOST = "127.0.0.1"
PORT = 8710
BASE_URL = f"http://{HOST}:{PORT}"

# === LLM 配置（兼容 OpenAI 协议，支持切换免费/付费服务商） ===
# 默认使用硅基流动（SiliconFlow）免费模型：国内直连、无需付费
DASHSCOPE_BASE_URL = os.getenv(
    "LLM_BASE_URL", "https://api.siliconflow.cn/v1"
)
DASHSCOPE_API_KEY = os.getenv("LLM_API_KEY", "")

# 默认模型名称（硅基流动免费模型）
# 注意：7B 太小，复杂 NL→JSON 解析会崩溃，文本解析/DOM 分析统一用 14B
QWEN_TEXT_MODEL = "Qwen/Qwen2.5-14B-Instruct"    # 文本解析 / DOM 分析（免费）
QWEN_VL_MODEL = "Qwen/Qwen2.5-VL-7B-Instruct"    # 视觉定位（免费）

# 服务商预设（供前端下拉选择，自动填充 base_url + 模型名）
LLM_PROVIDERS = [
    {
        "id": "zhipu",
        "name": "智谱 AI（免费·推荐）",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model": "glm-4-flash-250414",
        "vl_model": "glm-4v-flash",
        "note": "GLM-4-Flash 永久免费，中文能力优秀",
        "register_url": "https://open.bigmodel.cn/usercenter/apikeys",
    },
    {
        "id": "siliconflow",
        "name": "硅基流动（免费）",
        "base_url": "https://api.siliconflow.cn/v1",
        "model": "Qwen/Qwen2.5-14B-Instruct",
        "vl_model": "Qwen/Qwen2.5-VL-7B-Instruct",
        "note": "国内直连，注册即送免费额度，文本+视觉模型均免费",
        "register_url": "https://cloud.siliconflow.cn/account/ak",
    },
    {
        "id": "dashscope",
        "name": "通义千问 DashScope（付费）",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
        "vl_model": "qwen-vl-plus",
        "note": "原默认服务商，需付费 API Key",
        "register_url": "https://bailian.console.aliyun.com/?apiKey=1",
    },
    {
        "id": "custom",
        "name": "自定义（兼容 OpenAI 协议）",
        "base_url": "",
        "model": "",
        "vl_model": "",
        "note": "填写任意 OpenAI 兼容服务的 base_url 和模型名",
        "register_url": "",
    },
]

# === 自愈阈值 ===
CONFIDENCE_THRESHOLD = 0.75
DOM_MAX_NODES = 150
LAYER3_TIMEOUT = 25     # 秒（免费模型分析 DOM 较慢，需留足时间）
LAYER4_TIMEOUT = 25     # 秒

# === 速度档位延迟区间（秒） ===
SPEED_MODES = {
    "fast": (0.2, 0.6),
    "normal": (0.5, 2.0),
    "slow": (1.5, 4.0),
}

# === 报告清理 ===
REPORT_RETENTION_DAYS = 30

# === 浏览器接管（远程调试/CDP） ===
BROWSER_CDP_PORT = 9222
# 浏览器档案必须放在纯英文路径下：Chromium 的 --user-data-dir 遇到中文路径会启动后崩溃
_BROWSER_PROFILE_ROOT = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
BROWSER_PROFILE_DIR = _BROWSER_PROFILE_ROOT / "zhijian-lingxi" / "browser_profile"


def ensure_dirs() -> None:
    """确保运行时目录存在。"""
    for d in (DATA_DIR, SCREENSHOT_DIR, REPORT_DIR):
        d.mkdir(parents=True, exist_ok=True)