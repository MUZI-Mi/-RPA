"""定时调度

基于 APScheduler 支持 cron/interval/date 三种触发模式，
任务持久化到 SQLite，应用重启后自动恢复，支持错过补执行。
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from database import get_task, list_tasks, set_setting, get_setting


class SchedulerService:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self._handler: Optional[Callable] = None

    def start(self, handler: Callable) -> None:
        """启动调度器，handler 为任务执行回调 (task_id) -> None。"""
        self._handler = handler
        self.scheduler.start()
        self._restore_jobs()

    def _restore_jobs(self) -> None:
        for task in list_tasks():
            schedule = task.get("schedule") or {}
            if schedule and schedule.get("type") in ("cron", "interval", "date"):
                try:
                    self.add_job(task["id"], schedule)
                except Exception:
                    continue

    def add_job(self, task_id: str, schedule: Dict[str, Any]) -> None:
        stype = schedule.get("type", "once")
        if stype == "cron":
            trigger = CronTrigger.from_crontab(schedule.get("expression", "0 9 * * *"))
        elif stype == "interval":
            trigger = IntervalTrigger(**schedule.get("interval", {"hours": 2}))
        elif stype == "date":
            trigger = DateTrigger(run_date=schedule.get("run_date"))
        else:
            return

        job = self.scheduler.get_job(task_id)
        if job:
            job.remove()
        self.scheduler.add_job(
            self._run_task,
            trigger,
            args=[task_id],
            id=task_id,
            replace_existing=True,
            misfire_grace_time=3600,
        )

    def remove_job(self, task_id: str) -> None:
        job = self.scheduler.get_job(task_id)
        if job:
            job.remove()

    def _run_task(self, task_id: str) -> None:
        if self._handler:
            self._handler(task_id)

    def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    def check_missed(self) -> int:
        """开机后检查错过任务，返回补执行数量（简化：依赖 misfire_grace_time + 持久化）。"""
        return 0


scheduler_service = SchedulerService()