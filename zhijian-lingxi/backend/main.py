"""FastAPI 入口

提供服务端 API，接收前端请求，调度任务执行、自然语言解析、
操作录制、报告查询与设置管理。
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

import config
import database as db
from executor import TaskExecutor
from llm_client import LLMClient, LLMError
from models import (
    NLParseRequest,
    NLParseResponse,
    RecordingStartRequest,
    SettingsUpdate,
    TaskCreate,
    TaskUpdate,
)
from nl_parser import NLParser
from notifier import Notifier
from recorder import ActionRecorder
from report import ReportGenerator
from scheduler import scheduler_service

# 运行中的任务 (task_id -> stop event)
_running_tasks: Dict[str, asyncio.Event] = {}

executor = TaskExecutor()
recorder = ActionRecorder()


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.ensure_dirs()
    # 启动调度器，handler 将任务放入后台执行
    scheduler_service.start(_schedule_dispatch)
    yield
    scheduler_service.shutdown()


app = FastAPI(title="智简灵析", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# === 内部：调度分发 ===
def _schedule_dispatch(task_id: str) -> None:
    asyncio.ensure_future(_run_task_by_id(task_id))


async def _run_task_by_id(task_id: str) -> None:
    """执行任务并写入执行记录 + 报告 + 通知。"""
    task = db.get_task(task_id)
    if not task:
        return
    task_config = task["config"]
    # 标记为运行中，前端即可看到状态变化
    db.update_task(task_id, {"status": "running"})
    exec_id = db.create_execution(task_id)
    result = None
    try:
        # 用户可选择「显示执行窗口」：默认可见（headless=False），勾选与否都先以可见窗口运行
        show_browser = str(db.get_setting("show_browser", "true")).lower() in ("true", "1")
        # 浏览器模式：builtin=内置浏览器；attach=接管用户已调试启动的浏览器
        browser_mode = str(db.get_setting("browser_mode", "builtin")).lower()
        attach_url = None
        if browser_mode == "attach":
            attach_url = str(db.get_setting("cdp_url", f"http://127.0.0.1:{config.BROWSER_CDP_PORT}"))
        print(f"[execute] task={task_id} browser_mode={browser_mode} headless={not show_browser} attach={attach_url}", flush=True)
        try:
            result = await executor.run(
                task_config,
                exec_id=exec_id,
                headless=not show_browser,
                stop_event=_running_tasks.get(task_id),
                attach_url=attach_url,
            )
        except Exception as e:
            result = {
                "status": "failed",
                "duration_ms": 0,
                "steps": [],
                "error_msg": "浏览器启动/连接失败：" + (str(e) or repr(e)),
            }
        print(f"[execute] task={task_id} finished status={result['status']} steps={len(result['steps'])}", flush=True)
        end = result.get("duration_ms")
        db.update_execution(
            exec_id,
            {
                "status": result["status"],
                "end_time": _now(),
                "duration_ms": end,
                "error_msg": result.get("error_msg"),
            },
        )
        # 步骤日志入库
        for log in result["steps"]:
            db.add_step_log(exec_id, log)
        # 生成报告
        summary = {
            "task_id": task_id,
            "task_name": task_config.get("task_name", ""),
            "run_id": exec_id,
            "status": result["status"],
            "start_time": db.get_execution(exec_id)["start_time"],
            "end_time": _now(),
            "duration_ms": end,
            "error_msg": result.get("error_msg"),
        }
        report_path = ReportGenerator.generate(task_config, summary, result["steps"])
        db.update_execution(exec_id, {"report_path": report_path})
        # 清理旧报告
        ReportGenerator.cleanup_old_reports()
        # 通知
        await Notifier.notify(
            task_config.get("task_name", ""), result["status"], end or 0, result.get("error_msg") or ""
        )
        # 执行完成，更新任务状态
        db.update_task(task_id, {"status": result["status"]})
    except Exception:
        # 报告/通知等环节异常时，避免任务状态卡在 running
        db.update_task(task_id, {"status": "failed"})
    finally:
        # 无论成功失败，清理运行标记，否则下次点击会一直提示「任务已在运行」
        if task_id in _running_tasks:
            del _running_tasks[task_id]


def _now() -> str:
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# === 健康检查 ===
@app.get("/health")
async def health():
    return {"status": "ok", "service": "zhijian-lingxi"}


@app.get("/api/health")
async def api_health():
    return {"status": "ok"}


# === 任务管理 ===
@app.get("/api/tasks")
async def get_tasks():
    return db.list_tasks()


@app.post("/api/tasks")
async def create_task(body: TaskCreate):
    try:
        task_id = db.create_task(body.name, body.config.model_dump())
        schedule = body.config.schedule.model_dump()
        scheduler_service.add_job(task_id, schedule)
        return {"id": task_id}
    except Exception as e:
        raise HTTPException(400, str(e))


@app.get("/api/tasks/{task_id}")
async def get_task(task_id: str):
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    return task


@app.put("/api/tasks/{task_id}")
async def update_task(task_id: str, body: TaskUpdate):
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    fields = body.model_dump(exclude_none=True)
    db.update_task(task_id, fields)
    if body.config:
        scheduler_service.add_job(task_id, body.config.schedule.model_dump())
    return {"ok": True}


@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str):
    db.delete_task(task_id)
    scheduler_service.remove_job(task_id)
    return {"ok": True}


@app.post("/api/tasks/{task_id}/run")
async def run_task(task_id: str):
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    if task_id in _running_tasks:
        raise HTTPException(409, "任务已在运行")
    _running_tasks[task_id] = asyncio.Event()
    asyncio.ensure_future(_run_task_by_id(task_id))
    return {"ok": True, "status": "started"}


@app.post("/api/tasks/{task_id}/stop")
async def stop_task(task_id: str):
    ev = _running_tasks.get(task_id)
    if not ev:
        raise HTTPException(404, "任务未在运行")
    ev.set()
    return {"ok": True}


@app.get("/api/tasks/{task_id}/history")
async def task_history(task_id: str):
    return db.list_executions(task_id)


# === 自然语言解析 ===
@app.post("/api/nl/parse", response_model=NLParseResponse)
async def parse_nl(body: NLParseRequest):
    try:
        data = await NLParser.parse(body.text)
        return NLParseResponse(config=data, raw=data)
    except LLMError as e:
        raise HTTPException(400, str(e))


# === 执行报告 ===
@app.get("/api/reports/{task_id}")
async def latest_report(task_id: str):
    execs = db.list_executions(task_id)
    for e in execs:
        if e.get("report_path"):
            return {"run_id": e["id"], "report_path": e["report_path"]}
    raise HTTPException(404, "无报告")


@app.get("/api/reports/{task_id}/{run_id}")
async def report_detail(task_id: str, run_id: str):
    exec_rec = db.get_execution(run_id)
    if not exec_rec:
        raise HTTPException(404, "报告不存在")
    steps = db.list_step_logs(run_id)
    return {"execution": exec_rec, "steps": steps}


@app.get("/api/reports/{task_id}/{run_id}/screenshots/{step}")
async def step_screenshot(task_id: str, run_id: str, step: str):
    exec_rec = db.get_execution(run_id)
    if not exec_rec:
        raise HTTPException(404, "报告不存在")
    steps = db.list_step_logs(run_id)
    for s in steps:
        if str(s.get("step_id")) == step:
            path = s.get("screenshot_after") or s.get("screenshot_before")
            if path:
                return FileResponse(path)
    raise HTTPException(404, "截图不存在")


# === 操作录制 ===
@app.post("/api/recording/start")
async def start_recording(body: RecordingStartRequest):
    try:
        session_id = await recorder.start(body.start_url)
        return {"session_id": session_id}
    except RuntimeError as e:
        raise HTTPException(409, str(e))


@app.post("/api/recording/stop")
async def stop_recording():
    try:
        steps = await recorder.stop()
        return {"steps": steps}
    except RuntimeError as e:
        raise HTTPException(400, str(e))


@app.get("/api/recording/status")
async def recording_status():
    return await recorder.status()


# === 设置管理 ===
@app.get("/api/settings")
async def get_settings():
    return db.get_all_settings()


@app.get("/api/settings/providers")
async def get_providers():
    """返回 LLM 服务商预设（免费/付费/自定义）。"""
    return {"providers": config.LLM_PROVIDERS}


@app.put("/api/settings")
async def update_settings(body: SettingsUpdate):
    fields = body.model_dump(exclude_none=True)
    for k, v in fields.items():
        db.set_setting(k, v)
    return {"ok": True}


@app.post("/api/settings/test-llm")
async def test_llm():
    try:
        reply = await LLMClient.chat(
            [{"role": "user", "content": "回复 OK"}], temperature=0.0, timeout=15
        )
        return {"ok": True, "reply": reply[:50]}
    except LLMError as e:
        raise HTTPException(400, str(e))


# === 浏览器接管 ===
_BROWSER_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]


def _find_browser_exe() -> Optional[str]:
    for path in _BROWSER_CANDIDATES:
        if os.path.exists(path):
            return path
    for exe in ("msedge.exe", "chrome.exe"):
        found = shutil.which(exe)
        if found:
            return found
    return None


@app.post("/api/browser/launch")
async def launch_debug_browser():
    """以远程调试模式启动本机 Edge/Chrome，供「接管我的浏览器」模式使用。"""
    exe = _find_browser_exe()
    if not exe:
        raise HTTPException(400, "未检测到 Edge 或 Chrome，请先安装浏览器")
    profile_dir = config.BROWSER_PROFILE_DIR
    profile_dir.mkdir(parents=True, exist_ok=True)
    args = [
        exe,
        f"--remote-debugging-port={config.BROWSER_CDP_PORT}",
        "--remote-allow-origins=*",
        f"--user-data-dir={profile_dir}",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {
        "ok": True,
        "cdp_url": f"http://127.0.0.1:{config.BROWSER_CDP_PORT}",
        "msg": "已启动浏览器窗口，登录一次后会保持登录状态",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.HOST, port=config.PORT)