"""SQLite 数据库操作

使用 sqlite3 同步操作（数据量小），提供任务、执行记录、
步骤日志、定位缓存、设置等表的 CRUD。
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from config import DB_PATH, ensure_dirs

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    config      TEXT NOT NULL,
    schedule    TEXT,
    speed_mode  TEXT DEFAULT 'normal',
    status      TEXT DEFAULT 'idle',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS executions (
    id          TEXT PRIMARY KEY,
    task_id     TEXT NOT NULL,
    status      TEXT NOT NULL,
    start_time  TEXT NOT NULL,
    end_time    TEXT,
    duration_ms INTEGER,
    report_path TEXT,
    error_msg   TEXT
);

CREATE TABLE IF NOT EXISTS step_logs (
    id              TEXT PRIMARY KEY,
    execution_id    TEXT NOT NULL,
    step_id         INTEGER NOT NULL,
    action_type     TEXT NOT NULL,
    target_element  TEXT,
    status          TEXT NOT NULL,
    duration_ms     INTEGER,
    screenshot_before TEXT,
    screenshot_after  TEXT,
    healing_actions TEXT,
    error_info      TEXT,
    extracted       TEXT,
    page_url        TEXT,
    clicked_info    TEXT
);

CREATE TABLE IF NOT EXISTS locator_cache (
    id              TEXT PRIMARY KEY,
    cache_key       TEXT NOT NULL UNIQUE,
    url_pattern     TEXT NOT NULL,
    element_desc    TEXT NOT NULL,
    cached_selector TEXT,
    source_layer    INTEGER,
    last_used_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id          TEXT PRIMARY KEY,
    operator    TEXT NOT NULL,
    action      TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id   TEXT,
    detail      TEXT,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reviews (
    id                TEXT PRIMARY KEY,
    task_id           TEXT,
    execution_id      TEXT,
    step_id           INTEGER,
    source            TEXT,
    raw_data          TEXT,
    ai_result         TEXT,
    confidence        REAL,
    compliance_issues TEXT,
    status            TEXT DEFAULT 'pending',
    operator          TEXT,
    review_note       TEXT,
    corrected_data    TEXT,
    created_at        TEXT NOT NULL,
    reviewed_at       TEXT
);

CREATE TABLE IF NOT EXISTS templates (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    description   TEXT,
    category      TEXT DEFAULT 'document',
    filename      TEXT NOT NULL,
    original_name TEXT NOT NULL,
    size          INTEGER,
    uploader      TEXT,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_conn() -> sqlite3.Connection:
    ensure_dirs()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(_SCHEMA)
        _migrate(conn)


def _migrate(conn: sqlite3.Connection) -> None:
    """轻量迁移：为旧数据库补新增列。"""
    cols = [r[1] for r in conn.execute("PRAGMA table_info(step_logs)").fetchall()]
    if "page_url" not in cols:
        conn.execute("ALTER TABLE step_logs ADD COLUMN page_url TEXT")
    if "clicked_info" not in cols:
        conn.execute("ALTER TABLE step_logs ADD COLUMN clicked_info TEXT")


# === 任务 ===
def create_task(name: str, config: Dict[str, Any], speed_mode: str = "normal") -> str:
    task_id = str(uuid.uuid4())
    now = _now()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO tasks (id, name, config, schedule, speed_mode, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                task_id,
                name,
                json.dumps(config, ensure_ascii=False),
                json.dumps(config.get("schedule", {}), ensure_ascii=False),
                speed_mode,
                "idle",
                now,
                now,
            ),
        )
    return task_id


def list_tasks() -> List[Dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM tasks ORDER BY created_at DESC").fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["config"] = json.loads(d.get("config") or "{}")
        d["schedule"] = json.loads(d.get("schedule") or "{}")
        result.append(d)
    return result


def get_task(task_id: str) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["config"] = json.loads(d.get("config") or "{}")
    d["schedule"] = json.loads(d.get("schedule") or "{}")
    return d


def update_task(task_id: str, fields: Dict[str, Any]) -> None:
    allow = {"name", "config", "schedule", "speed_mode", "status"}
    sets, params = [], []
    for k, v in fields.items():
        if k not in allow:
            continue
        if k in ("config", "schedule"):
            v = json.dumps(v, ensure_ascii=False)
        sets.append(f"{k} = ?")
        params.append(v)
    if not sets:
        return
    sets.append("updated_at = ?")
    params.append(_now())
    params.append(task_id)
    with get_conn() as conn:
        conn.execute(f"UPDATE tasks SET {', '.join(sets)} WHERE id = ?", params)


def delete_task(task_id: str) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))


# === 执行记录 ===
def create_execution(task_id: str) -> str:
    exec_id = str(uuid.uuid4())
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO executions (id, task_id, status, start_time) VALUES (?, ?, ?, ?)",
            (exec_id, task_id, "running", _now()),
        )
    return exec_id


def update_execution(exec_id: str, fields: Dict[str, Any]) -> None:
    allow = {"status", "end_time", "duration_ms", "report_path", "error_msg"}
    sets, params = [], []
    for k, v in fields.items():
        if k not in allow:
            continue
        sets.append(f"{k} = ?")
        params.append(v)
    if not sets:
        return
    params.append(exec_id)
    with get_conn() as conn:
        conn.execute(f"UPDATE executions SET {', '.join(sets)} WHERE id = ?", params)


def get_execution(exec_id: str) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM executions WHERE id = ?", (exec_id,)).fetchone()
    return dict(row) if row else None


def list_executions(task_id: str) -> List[Dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM executions WHERE task_id = ? ORDER BY start_time DESC", (task_id,)
        ).fetchall()
    return [dict(r) for r in rows]


# === 步骤日志 ===
def add_step_log(exec_id: str, log: Dict[str, Any]) -> None:
    log_id = str(uuid.uuid4())
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO step_logs (id, execution_id, step_id, action_type, target_element, "
            "status, duration_ms, screenshot_before, screenshot_after, healing_actions, "
            "error_info, extracted, page_url, clicked_info) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                log_id,
                exec_id,
                log.get("step_id"),
                log.get("action_type"),
                log.get("target_element"),
                log.get("status", "success"),
                log.get("duration_ms"),
                log.get("screenshot_before"),
                log.get("screenshot_after"),
                json.dumps(log.get("healing_actions", []), ensure_ascii=False),
                log.get("error_info"),
                json.dumps(log.get("extracted"), ensure_ascii=False) if log.get("extracted") is not None else None,
                log.get("page_url"),
                json.dumps(log.get("clicked_info"), ensure_ascii=False) if log.get("clicked_info") is not None else None,
            ),
        )


def list_step_logs(exec_id: str) -> List[Dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM step_logs WHERE execution_id = ? ORDER BY step_id", (exec_id,)
        ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["healing_actions"] = json.loads(d.get("healing_actions") or "[]")
        if d.get("clicked_info"):
            try:
                d["clicked_info"] = json.loads(d["clicked_info"])
            except (ValueError, TypeError):
                d["clicked_info"] = None
        if d.get("extracted"):
            d["extracted"] = json.loads(d["extracted"])
        result.append(d)
    return result


# === 模板 ===
def create_template(
    name: str,
    filename: str,
    original_name: str,
    description: str = "",
    category: str = "document",
    size: Optional[int] = None,
    uploader: Optional[str] = None,
) -> str:
    tpl_id = str(uuid.uuid4())
    now = _now()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO templates (id, name, description, category, filename, original_name, size, "
            "uploader, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (tpl_id, name, description, category, filename, original_name, size, uploader, now, now),
        )
    return tpl_id


def list_templates() -> List[Dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM templates ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]


def get_template(tpl_id: str) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM templates WHERE id = ?", (tpl_id,)).fetchone()
    return dict(row) if row else None


def get_template_by_name(name: str) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM templates WHERE name = ?", (name,)).fetchone()
    return dict(row) if row else None


def delete_template(tpl_id: str) -> bool:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM templates WHERE id = ?", (tpl_id,))
    return cur.rowcount > 0


# === 定位缓存 ===
def cache_lookup(key: str) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM locator_cache WHERE cache_key = ? AND last_used_at > datetime('now', '-30 day')",
            (key,),
        ).fetchone()
    return dict(row) if row else None


def cache_set(key: str, url_pattern: str, element_desc: str, cached_selector: str, source_layer: int) -> None:
    now = _now()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO locator_cache (id, cache_key, url_pattern, element_desc, cached_selector, "
            "source_layer, last_used_at) VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(cache_key) DO UPDATE SET cached_selector=excluded.cached_selector, "
            "source_layer=excluded.source_layer, last_used_at=excluded.last_used_at",
            (str(uuid.uuid4()), key, url_pattern, element_desc, cached_selector, source_layer, now),
        )


# === 设置 ===
def get_setting(key: str, default: Any = None) -> Any:
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key: str, value: Any) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )


def get_all_settings() -> Dict[str, str]:
    with get_conn() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
    return {r["key"]: r["value"] for r in rows}


init_db()