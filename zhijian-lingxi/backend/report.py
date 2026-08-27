"""报告生成

使用 Jinja2 模板将任务执行日志与截图渲染为 HTML 报告，
并支持清理过期报告。
"""

from __future__ import annotations

import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

from jinja2 import Environment, FileSystemLoader, select_autoescape

from config import REPORT_DIR, REPORT_RETENTION_DAYS, TEMPLATE_DIR, ensure_dirs
from database import get_setting

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{ task.task_name }} - 执行报告</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: -apple-system, "Microsoft YaHei", sans-serif; background: #f5f7fa; color: #333; }
    .container { max-width: 960px; margin: 0 auto; padding: 24px; }
    h1 { font-size: 24px; margin-bottom: 8px; }
    .meta { color: #888; font-size: 13px; margin-bottom: 24px; }
    .summary { display: flex; gap: 16px; margin-bottom: 24px; flex-wrap: wrap; }
    .card { background: #fff; border-radius: 8px; padding: 16px 20px; box-shadow: 0 1px 3px rgba(0,0,0,.08); flex: 1; min-width: 140px; }
    .card .label { font-size: 12px; color: #999; }
    .card .value { font-size: 22px; font-weight: 600; margin-top: 4px; }
    .status-success { color: #18a058; } .status-failed { color: #d03050; } .status-partial { color: #f0a020; }
    .step { background: #fff; border-radius: 8px; padding: 16px; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0,0,0,.08); }
    .step-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
    .step-title { font-weight: 600; }
    .badge { padding: 2px 10px; border-radius: 12px; font-size: 12px; }
    .badge.success { background: #e6f7ef; color: #18a058; }
    .badge.failed { background: #fde8e8; color: #d03050; }
    .healing { background: #fff7e6; border-left: 3px solid #f0a020; padding: 8px 12px; margin-top: 8px; font-size: 13px; border-radius: 4px; }
    .healing li { margin-left: 18px; }
    img { max-width: 100%; border-radius: 6px; border: 1px solid #eee; margin-top: 8px; }
    .shots { display: flex; gap: 12px; flex-wrap: wrap; }
    .shots figure { flex: 1; min-width: 200px; }
    figcaption { font-size: 12px; color: #999; margin-top: 4px; }
    .error { color: #d03050; font-size: 13px; margin-top: 8px; }
    .extract { background: #f0f7ff; padding: 8px 12px; border-radius: 4px; margin-top: 8px; font-size: 13px; }
  </style>
</head>
<body>
  <div class="container">
    <h1>{{ task.task_name }}</h1>
    <div class="meta">
      指令：{{ task.description or '无' }}<br>
      开始：{{ summary.start_time }} · 结束：{{ summary.end_time or '—' }} ·
      总耗时：{{ summary.duration_ms }}ms
    </div>
    <div class="summary">
      <div class="card"><div class="label">执行状态</div><div class="value status-{{ summary.status }}">{{ status_text }}</div></div>
      <div class="card"><div class="label">总步骤</div><div class="value">{{ steps | length }}</div></div>
      <div class="card"><div class="label">成功步骤</div><div class="value status-success">{{ success_count }}</div></div>
      <div class="card"><div class="label">失败步骤</div><div class="value status-failed">{{ failed_count }}</div></div>
    </div>
    {% for s in steps %}
    <div class="step">
      <div class="step-head">
        <span class="step-title">步骤 {{ s.step_id }} · {{ s.action_type }}</span>
        <span class="badge {{ s.status }}">{{ '成功' if s.status == 'success' else '失败' }}</span>
      </div>
      <div class="target">目标：{{ s.target_element or '—' }} · 耗时 {{ s.duration_ms }}ms</div>
      {% if s.healing_actions %}
      <div class="healing">
        自愈记录：
        <ul>{% for h in s.healing_actions %}<li>{{ h }}</li>{% endfor %}</ul>
      </div>
      {% endif %}
      {% if s.error_info %}<div class="error">错误：{{ s.error_info }}</div>{% endif %}
      {% if s.extracted is not none %}<div class="extract">提取结果：{{ s.extracted }}</div>{% endif %}
      {% if s.screenshot_before or s.screenshot_after %}
      <div class="shots">
        {% if s.screenshot_before %}<figure><img src="file://{{ s.screenshot_before }}" alt="操作前"><figcaption>操作前</figcaption></figure>{% endif %}
        {% if s.screenshot_after %}<figure><img src="file://{{ s.screenshot_after }}" alt="操作后"><figcaption>操作后</figcaption></figure>{% endif %}
      </div>
      {% endif %}
    </div>
    {% endfor %}
  </div>
</body>
</html>
"""


class ReportGenerator:
    """报告生成器。"""

    @staticmethod
    def generate(
        task_config: Dict[str, Any],
        summary: Dict[str, Any],
        step_logs: List[Dict[str, Any]],
    ) -> str:
        ensure_dirs()
        task_id = summary.get("task_id", "task")
        run_id = summary.get("run_id", "")
        report_dir = REPORT_DIR / task_id / run_id
        report_dir.mkdir(parents=True, exist_ok=True)

        status_text = {"success": "成功", "failed": "失败", "partial": "部分成功"}.get(
            summary.get("status"), summary.get("status")
        )
        success_count = len([s for s in step_logs if s.get("status") == "success"])
        failed_count = len([s for s in step_logs if s.get("status") == "failed"])

        env = Environment(loader=FileSystemLoader("."))
        template = env.from_string(HTML_TEMPLATE)
        html = template.render(
            task=task_config,
            summary=summary,
            steps=step_logs,
            status_text=status_text,
            success_count=success_count,
            failed_count=failed_count,
        )
        report_path = report_dir / "report.html"
        report_path.write_text(html, encoding="utf-8")
        return str(report_path)

    @staticmethod
    def cleanup_old_reports() -> None:
        """清理超过保留天数的旧报告。"""
        retention = int(get_setting("report_retention_days") or REPORT_RETENTION_DAYS)
        cutoff = datetime.now() - timedelta(days=retention)
        if not REPORT_DIR.exists():
            return
        for task_dir in REPORT_DIR.iterdir():
            if not task_dir.is_dir():
                continue
            for run_dir in task_dir.iterdir():
                try:
                    mtime = datetime.fromtimestamp(run_dir.stat().st_mtime)
                    if mtime < cutoff:
                        shutil.rmtree(run_dir, ignore_errors=True)
                except Exception:
                    continue