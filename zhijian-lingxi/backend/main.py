"""FastAPI 入口

提供服务端 API，接收前端请求，调度任务执行、自然语言解析、
操作录制、报告查询与设置管理。
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

import audit as audit_mod
import config
import database as db
import review as review_mod
from executor import TaskExecutor
from llm_client import LLMClient, LLMError
from models import (
    NLParseRequest,
    NLParseResponse,
    NLRefineRequest,
    RecordingStartRequest,
    ReviewDecision,
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
        audit_mod.log("create_task", "task", task_id, {"name": body.name})
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
    audit_mod.log("update_task", "task", task_id, {"name": fields.get("name")})
    return {"ok": True}


@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str):
    db.delete_task(task_id)
    scheduler_service.remove_job(task_id)
    audit_mod.log("delete_task", "task", task_id)
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
    audit_mod.log("run_task", "task", task_id)
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
    except Exception as e:
        # LLM 输出偶有模型定义之外的结构，兜底转 400，避免闪成 500
        raise HTTPException(400, f"解析失败，请换一种说法再试：{e}")


# === 自然语言多轮修改：用户可多次发消息修改方案，AI 返回新方案供再确认 ===
@app.post("/api/nl/refine", response_model=NLParseResponse)
async def refine_nl(body: NLRefineRequest):
    try:
        data = await NLParser.refine(body.text, body.config)
        return NLParseResponse(config=data, raw=data)
    except LLMError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(400, f"方案修改失败，请换一种说法再试：{e}")


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


# === 报表文件下载 ===
@app.get("/api/export/download/{filename}")
async def export_download(filename: str):
    """下载导出的报表文件（CSV/JSON），filename 为文件名。"""
    import re as _re
    if not _re.fullmatch(r"[\w\u4e00-\u9fff\-\.]{1,120}", filename):
        raise HTTPException(400, "非法文件名")
    path = config.EXPORT_DIR / filename
    if not path.exists():
        raise HTTPException(404, "导出文件不存在，可能已被清理")
    return FileResponse(path, filename=filename, media_type="application/octet-stream")


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
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    # 录完后自动给每步补一句大白话说明（note）；LLM 未配置/失败时不阻塞，原样返回
    try:
        steps = await NLParser.add_notes(steps)
    except Exception:
        pass
    return {"steps": steps}


@app.get("/api/recording/status")
async def recording_status():
    return await recorder.status()


@app.post("/api/recording/force-stop")
async def force_stop_recording():
    """强制结束残留的录制会话（录制窗口被关/卡住时），释放后即可重新录制。"""
    await recorder._force_cleanup()
    return {"ok": True}


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


# === 人工审核队列 ===
@app.get("/api/reviews")
async def list_reviews(status: str = "", task_id: str = "", page: int = 1, page_size: int = 20):
    return review_mod.list_reviews(
        status=status or None,
        task_id=task_id or None,
        page=page,
        page_size=page_size,
    )


@app.get("/api/reviews/pending-count")
async def pending_review_count():
    return {"count": review_mod.count_pending()}


@app.get("/api/reviews/{review_id}")
async def get_review(review_id: str):
    item = review_mod.get_review(review_id)
    if not item:
        raise HTTPException(404, "审核记录不存在")
    return item


@app.post("/api/reviews/{review_id}/approve")
async def approve_review(review_id: str, body: ReviewDecision):
    if not review_mod.approve(review_id, body.operator or audit_mod.get_operator(), body.note or ""):
        raise HTTPException(404, "审核记录不存在")
    audit_mod.log("review_approve", "review", review_id, {"note": body.note})
    return {"ok": True}


@app.post("/api/reviews/{review_id}/reject")
async def reject_review(review_id: str, body: ReviewDecision):
    if not review_mod.reject(review_id, body.operator or audit_mod.get_operator(), body.note or ""):
        raise HTTPException(404, "审核记录不存在")
    audit_mod.log("review_reject", "review", review_id, {"note": body.note})
    return {"ok": True}


@app.post("/api/reviews/{review_id}/update")
async def update_review(review_id: str, body: ReviewDecision):
    if not review_mod.update_and_approve(
        review_id, body.operator or audit_mod.get_operator(), body.corrected_data, body.note or ""
    ):
        raise HTTPException(404, "审核记录不存在")
    audit_mod.log("review_update", "review", review_id, {"note": body.note})
    return {"ok": True}


# === 操作审计日志 ===
@app.get("/api/audit")
async def list_audit(
    operator: str = "",
    action: str = "",
    target_type: str = "",
    start: str = "",
    end: str = "",
    page: int = 1,
    page_size: int = 20,
):
    return audit_mod.list_logs(
        operator=operator or None,
        action=action or None,
        target_type=target_type or None,
        start=start or None,
        end=end or None,
        page=page,
        page_size=page_size,
    )


@app.get("/api/audit/export")
async def export_audit(
    operator: str = "",
    action: str = "",
    target_type: str = "",
    start: str = "",
    end: str = "",
):
    path = audit_mod.export_csv(
        operator=operator or None,
        action=action or None,
        target_type=target_type or None,
        start=start or None,
        end=end or None,
    )
    filename = path.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]
    return FileResponse(path, filename=filename, media_type="text/csv")


# === 模板中心 ===
@app.get("/api/templates")
async def list_templates():
    return db.list_templates()


@app.post("/api/templates/upload")
async def upload_template(
    file: UploadFile = File(...),
    name: str = Form(""),
    description: str = Form(""),
    category: str = Form("document"),
):
    """上传 Excel/Word 报表模板。文件名（不含扩展名）作为默认模板名。"""
    original_name = file.filename or "template"
    suffix = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
    if suffix not in ("xlsx", "xls", "docx"):
        raise HTTPException(400, "仅支持 .xlsx / .docx 模板文件")
    content = await file.read()
    if not content:
        raise HTTPException(400, "文件为空")
    filename = f"tpl_{int(time.time())}_{original_name}"
    tpl_name = (name or "").strip() or original_name.rsplit(".", 1)[0]
    if db.get_template_by_name(tpl_name):
        raise HTTPException(409, f"模板「{tpl_name}」已存在，请换一个名字")
    (config.TEMPLATE_DIR / filename).write_bytes(content)
    tpl_id = db.create_template(
        name=tpl_name,
        filename=filename,
        original_name=original_name,
        description=description,
        category=category,
        size=len(content),
        uploader=audit_mod.get_operator(),
    )
    audit_mod.log("upload_template", "template", tpl_id, {"name": tpl_name})
    return {"id": tpl_id, "name": tpl_name}


@app.delete("/api/templates/{tpl_id}")
async def delete_template(tpl_id: str):
    tpl = db.get_template(tpl_id)
    if not tpl:
        raise HTTPException(404, "模板不存在")
    path = config.TEMPLATE_DIR / tpl["filename"]
    if path.exists():
        try:
            path.unlink()
        except OSError:
            pass
    db.delete_template(tpl_id)
    audit_mod.log("delete_template", "template", tpl_id, {"name": tpl.get("name")})
    return {"ok": True}


@app.get("/api/templates/{tpl_id}/download")
async def download_template(tpl_id: str):
    tpl = db.get_template(tpl_id)
    if not tpl:
        raise HTTPException(404, "模板不存在")
    path = config.TEMPLATE_DIR / tpl["filename"]
    if not path.exists():
        raise HTTPException(404, "模板文件已丢失")
    return FileResponse(path, filename=tpl["original_name"])


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