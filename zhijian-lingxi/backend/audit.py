"""操作审计日志

记录操作人、时间、对象、类型的操作轨迹，支持查询与导出 CSV。
审计日志只存元数据（操作动作/对象），不落 PII 明文正文。
"""

from __future__ import annotations

import csv
import json
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from config import EXPORT_DIR, ensure_dirs
from database import get_conn, get_setting


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_operator() -> str:
    """当前操作人：从设置 operator_name 读取，缺省 system。"""
    v = get_setting("operator_name")
    return str(v).strip() if v and str(v).strip() else "system"


def log(
    action: str,
    target_type: str,
    target_id: Optional[str] = None,
    detail: Optional[Dict[str, Any]] = None,
    operator: Optional[str] = None,
) -> None:
    """写入一条审计日志。"""
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO audit_logs (id, operator, action, target_type, target_id, detail, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                str(uuid.uuid4()),
                operator or get_operator(),
                action,
                target_type,
                target_id,
                json.dumps(detail, ensure_ascii=False) if detail else None,
                _now(),
            ),
        )


def list_logs(
    operator: Optional[str] = None,
    action: Optional[str] = None,
    target_type: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> Dict[str, Any]:
    """按条件分页查询审计日志。"""
    where, params = [], []
    if operator:
        where.append("operator = ?")
        params.append(operator)
    if action:
        where.append("action = ?")
        params.append(action)
    if target_type:
        where.append("target_type = ?")
        params.append(target_type)
    if start:
        where.append("created_at >= ?")
        params.append(start)
    if end:
        where.append("created_at <= ?")
        params.append(end)
    cond = (" WHERE " + " AND ".join(where)) if where else ""
    page = max(1, int(page))
    page_size = min(max(1, int(page_size)), 100)
    with get_conn() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM audit_logs{cond}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM audit_logs{cond} ORDER BY created_at DESC, id LIMIT ? OFFSET ?",
            params + [page_size, (page - 1) * page_size],
        ).fetchall()
    items = []
    for r in rows:
        d = dict(r)
        if d.get("detail"):
            try:
                d["detail"] = json.loads(d["detail"])
            except (ValueError, TypeError):
                d["detail"] = None
        items.append(d)
    return {"items": items, "total": total}


def export_csv(
    operator: Optional[str] = None,
    action: Optional[str] = None,
    target_type: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> str:
    """导出筛选后的审计日志为 CSV，返回文件路径。"""
    data = list_logs(operator, action, target_type, start, end, page=1, page_size=10000)
    ensure_dirs()
    stamp = time.strftime("%Y%m%d_%H%M%S")
    path = EXPORT_DIR / f"audit_{stamp}.csv"
    cols = ["created_at", "operator", "action", "target_type", "target_id", "detail"]
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        for item in data["items"]:
            writer.writerow({k: item.get(k, "") for k in cols})
    return str(path)
