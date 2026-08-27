"""消息通知

任务完成/失败时发送通知：
  - 本地系统通知（由 Tauri 负责，这里预留回调）
  - 企业微信机器人 Webhook
  - SMTP 邮件
"""

from __future__ import annotations

import smtplib
from email.header import Header
from email.mime.text import MIMEText
from typing import Any, Dict, Optional

import httpx

from database import get_setting


class Notifier:
    @staticmethod
    async def notify(task_name: str, status: str, duration_ms: int, error_msg: str = "") -> bool:
        """发送通知，返回是否至少一种渠道发送成功。"""
        sent = False
        if await Notifier._wechat(task_name, status, duration_ms, error_msg):
            sent = True
        if Notifier._email(task_name, status, duration_ms, error_msg):
            sent = True
        return sent

    @staticmethod
    async def _wechat(task_name: str, status: str, duration_ms: int, error_msg: str) -> bool:
        webhook = get_setting("wechat_webhook")
        if not webhook:
            return False
        status_text = {"success": "成功", "failed": "失败", "partial": "部分成功"}.get(status, status)
        content = f"【智简灵析】任务「{task_name}」执行{status_text}，耗时 {duration_ms / 1000:.1f}s"
        if error_msg:
            content += f"\n失败原因：{error_msg[:200]}"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(webhook, json={"msgtype": "text", "text": {"content": content}})
            return True
        except Exception:
            return False

    @staticmethod
    def _email(task_name: str, status: str, duration_ms: int, error_msg: str) -> bool:
        host = get_setting("smtp_host")
        user = get_setting("smtp_user")
        password = get_setting("smtp_password")
        to = get_setting("smtp_to")
        if not (host and user and password and to):
            return False
        try:
            port = int(get_setting("smtp_port") or 465)
            status_text = {"success": "成功", "failed": "失败", "partial": "部分成功"}.get(status, status)
            subject = f"【智简灵析】任务「{task_name}」执行{status_text}"
            body = f"任务「{task_name}」执行{status_text}，耗时 {duration_ms / 1000:.1f}s"
            if error_msg:
                body += f"\n失败原因：{error_msg[:200]}"
            msg = MIMEText(body, "plain", "utf-8")
            msg["Subject"] = Header(subject, "utf-8")
            msg["From"] = user
            msg["To"] = to
            if port == 465:
                server = smtplib.SMTP_SSL(host, port, timeout=10)
            else:
                server = smtplib.SMTP(host, port, timeout=10)
                server.starttls()
            server.login(user, password)
            server.sendmail(user, [to], msg.as_string())
            server.quit()
            return True
        except Exception:
            return False