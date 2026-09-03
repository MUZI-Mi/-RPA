"""人工审核队列

AI 业务判断产生的异常/低置信度数据进入待审核队列，
人工可 通过 / 驳回 / 修改 后处理。
审核页需要看到真值供人工判定，故 raw_data/ai_result 存明文（本地 SQLite、数据不上云）。
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from database import get_conn


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def add_review(
    *,
    source: str,
    raw_data: Any,
    ai_result: Any = None,
    confidence: Optional[float] = None,
    compliance_issues: Optional[List[str]] = None,
    task_id: Optional[str] = None,
    execution_id: Optional[str] = None,
    step_id: Optional[int] = None,
) -> str:
    """新增一条待审核记录，返回 review id。"""
    review_id = str(uuid.uuid4())
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO reviews (id, task_id, execution_id, step_id, source, raw_data, ai_result, "
            "confidence, compliance_issues, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                review_id,
                task_id,
                execution_id,
                step_id,
                source,
                json.dumps(raw_data, ensure_ascii=False) if raw_data is not None else None,
                json.dumps(ai_result, ensure_ascii=False) if ai_result is not None else None,
                confidence,
                json.dumps(compliance_issues or [], ensure_ascii=False),
                "pending",
                _now(),
            ),
        )
    return review_id


def _row_to_item(r: Any) -> Dict[str, Any]:
    d = dict(r)
    for key in ("raw_data", "ai_result", "corrected_data"):
        if d.get(key):
            try:
                d[key] = json.loads(d[key])
            except (ValueError, TypeError):
                d[key] = None
    if d.get("compliance_issues"):
        try:
            d["compliance_issues"] = json.loads(d["compliance_issues"])
        except (ValueError, TypeError):
            d["compliance_issues"] = []
    else:
        d["compliance_issues"] = []
    return d


def list_reviews(
    status: Optional[str] = None,
    task_id: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> Dict[str, Any]:
    where, params = [], []
    if status:
        where.append("status = ?")
        params.append(status)
    if task_id:
        where.append("task_id = ?")
        params.append(task_id)
    cond = (" WHERE " + " AND ".join(where)) if where else ""
    page = max(1, int(page))
    page_size = min(max(1, int(page_size)), 100)
    with get_conn() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM reviews{cond}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM reviews{cond} ORDER BY created_at DESC, id LIMIT ? OFFSET ?",
            params + [page_size, (page - 1) * page_size],
        ).fetchall()
    return {"items": [_row_to_item(r) for r in rows], "total": total}


def get_review(review_id: str) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM reviews WHERE id = ?", (review_id,)).fetchone()
    return _row_to_item(row) if row else None


def _set_status(review_id: str, status: str, operator: str, note: str,
                corrected_data: Any = None) -> bool:
    with get_conn() as conn:
        cur = conn.execute("SELECT id FROM reviews WHERE id = ?", (review_id,)).fetchone()
        if not cur:
            return False
        conn.execute(
            "UPDATE reviews SET status = ?, operator = ?, review_note = ?, corrected_data = ?, "
            "reviewed_at = ? WHERE id = ?",
            (
                status,
                operator,
                note,
                json.dumps(corrected_data, ensure_ascii=False) if corrected_data is not None else None,
                _now(),
                review_id,
            ),
        )
    return True


def approve(review_id: str, operator: str, note: str = "") -> bool:
    return _set_status(review_id, "approved", operator, note)


def reject(review_id: str, operator: str, note: str = "") -> bool:
    return _set_status(review_id, "rejected", operator, note)


def update_and_approve(review_id: str, operator: str, corrected_data: Any, note: str = "") -> bool:
    return _set_status(review_id, "approved", operator, note, corrected_data)


def count_pending() -> int:
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM reviews WHERE status = 'pending'").fetchone()[0]
