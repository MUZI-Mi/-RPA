"""操作录制

使用 Playwright CDP 事件监听，捕获用户在浏览器中的
点击、输入、切换等交互，智能过滤无意义操作后转为规则步骤。
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional

try:
    from playwright.async_api import async_playwright
except ImportError:  # pragma: no cover
    async_playwright = None  # type: ignore


class RecordingSession:
    def __init__(self, start_url: str):
        self.session_id = str(uuid.uuid4())
        self.start_url = start_url
        self.events: List[Dict[str, Any]] = []
        self.browser = None
        self.context = None
        self.page = None
        self.running = False


class ActionRecorder:
    """录制器：管理录制会话，监听 CDP 事件。"""

    _session: Optional[RecordingSession] = None

    async def start(self, start_url: str) -> str:
        if self._session and self._session.running:
            raise RuntimeError("已有录制正在进行")
        session = RecordingSession(start_url)
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(headless=False)
        context = await browser.new_context()
        # 关键：将录制脚本设为“新文档自动注入”，否则用户点击跳转到新页面后
        # 原页面注入的监听全部丢失，导致只录到跳转前的少量操作
        await context.add_init_script(_INJECT_RECORDER_JS)
        page = await context.new_page()
        await page.goto(start_url)
        session.browser = browser
        session.context = context
        session.page = page
        session.running = True
        self._session = session
        await self._attach_listeners(session)
        return session.session_id

    async def _attach_listeners(self, session: RecordingSession) -> None:
        # 注入脚本监听交互（add_init_script 已保证每个新文档自动注入，这里再补一次当前页）
        await session.page.evaluate(_INJECT_RECORDER_JS)
        # 定期读取录制事件：遍历上下文内所有页面（含新标签页），避免只盯着初始页丢事件
        import asyncio

        async def _poller():
            while session.running:
                await asyncio.sleep(0.5)
                try:
                    pages = session.context.pages
                except Exception:
                    continue
                for pg in pages:
                    try:
                        new_events = await pg.evaluate("window.__zlx_recorder_dump()")
                    except Exception:
                        continue
                    if new_events:
                        for e in new_events:
                            if e not in session.events:
                                session.events.append(e)

        asyncio.ensure_future(_poller())

    async def stop(self) -> List[Dict[str, Any]]:
        if not self._session or not self._session.running:
            raise RuntimeError("无进行中的录制")
        session = self._session
        session.running = False
        # 停止前最后抽取一次所有页面（含新标签页）尚未被轮询取走的剩余事件
        try:
            pages = session.context.pages
        except Exception:
            pages = []
        for pg in pages:
            try:
                remaining = await pg.evaluate("window.__zlx_recorder_dump()")
            except Exception:
                continue
            for e in remaining:
                if e not in session.events:
                    session.events.append(e)
        try:
            await session.page.evaluate("window.__zlx_recorder_stop()")
        except Exception:
            pass
        try:
            await session.browser.close()
        except Exception:
            pass
        steps = self._filter_noise(session.events)
        self._session = None
        return steps

    async def status(self) -> Dict[str, Any]:
        if self._session and self._session.running:
            return {"recording": True, "session_id": self._session.session_id, "event_count": len(self._session.events)}
        return {"recording": False}

    def _filter_noise(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """智能过滤：去重、去噪，转规则步骤。"""
        filtered: List[Dict[str, Any]] = []
        seen_keys: Dict[str, float] = {}
        for e in events:
            etype = e.get("type")
            if etype not in ("click", "input", "change"):
                continue
            # input 无内容过滤
            if etype in ("input", "change") and not str(e.get("value", "")).strip():
                continue
            # change 事件仅保留来自 <select> 的，input 触发的 change 已由 input 捕获
            if etype == "change" and e.get("tag") != "select":
                continue
            # <select> 改值同时触发 input，统一用 select 动作表达，忽略其 input 事件
            if etype == "input" and e.get("tag") == "select":
                continue
            key = f"{etype}::{e.get('selector')}"
            now = time.time()
            # 1 秒内同一元素重复点击只保留一次
            if key in seen_keys and now - seen_keys[key] < 1.0 and etype == "click":
                continue
            seen_keys[key] = now
            filtered.append(e)

        steps: List[Dict[str, Any]] = []
        for i, e in enumerate(filtered):
            etype = e.get("type")
            selector = e.get("selector", "")
            if etype == "click":
                action = {"type": "click", "selector": selector, "text": e.get("text", "")}
            elif etype == "input":
                action = {"type": "input", "selector": selector, "value": e.get("value", "")}
            else:
                action = {"type": "select", "selector": selector, "value": e.get("value", "")}
            steps.append({"step_id": i + 1, "condition": {"type": "always"}, "action": action})
        # 首步注入打开起始页
        if self._session:
            open_step = {"step_id": 0, "condition": {"type": "always"},
                         "action": {"type": "open", "url": self._session.start_url}}
            steps.insert(0, open_step)
            for i, s in enumerate(steps, 1):
                s["step_id"] = i
        return steps


# 注入页面的录制脚本
_INJECT_RECORDER_JS = """
(() => {
  if (window.__zlx_recorder) return;
  const events = [];
  window.__zlx_recorder = true;
  const isStateClass = (c) => /active|selected|current|hover|focus|checked|disabled|open|visited|on/i.test(c);
  // 生成「录制时刻全页唯一」的 CSS 选择器（类似 Playwright codegen）：
  // id → data-testid → 标签+类 → 逐级向上拼接父级 :nth-child 链，直到唯一。
  // 从源头避免裸标签/多匹配导致的执行时乱点。
  const makeUniqueSelector = (el) => {
    const escape = (s) => { try { return CSS.escape(s); } catch (e) { return s; } };
    const doc = el.ownerDocument || document;
    if (el.id) {
      const s = '#' + escape(el.id);
      if (doc.querySelectorAll(s).length === 1) return s;
    }
    const dtid = el.getAttribute('data-testid');
    if (dtid) {
      const s = '[data-testid="' + dtid + '"]';
      if (doc.querySelectorAll(s).length === 1) return s;
    }
    const tag = el.tagName.toLowerCase();
    const cls = Array.prototype.slice.call(el.classList)
      .filter(function (c) { return !isStateClass(c); });
    let simple = tag + (cls.length ? '.' + cls.slice(0, 3).join('.') : '');
    try {
      if (doc.querySelectorAll(simple).length === 1) return simple;
    } catch (e) { simple = tag; }
    // 逐级向上拼接父级 :nth-child 链，直到全页唯一（最多 5 层）
    let path = [];
    let unique = null;
    for (let depth = 0, node = el; node && node.nodeType === 1 && depth < 5; depth++, node = node.parentElement) {
      let part = node.tagName.toLowerCase();
      if (node.id) {
        part = '#' + escape(node.id);
      } else {
        const parent = node.parentElement;
        if (parent) {
          const kids = Array.prototype.slice.call(parent.children);
          const idx = kids.indexOf(node);
          if (idx >= 0) part += ':nth-child(' + (idx + 1) + ')';
        }
      }
      path.unshift(part);
      const cand = path.join(' > ');
      try {
        if (doc.querySelectorAll(cand).length === 1) { unique = cand; break; }
      } catch (e) { break; }
    }
    return unique || simple;
  };
  window.__zlx_make_selector = makeUniqueSelector;

  const describe = (el) => {
    if (!el) return {selector: '', text: '', tag: ''};
    // 点击 SVG 图标内部时，ev.target 往往是 <path>/<use>/<g> 等无语义标签，
    // 直接生成选择器会得到裸标签名（如 path），执行时会命中页面上任意一个 SVG。
    // 因此向上回溯到承载图标的可点击元素（a/button/li/input 等）。
    const svgTags = ['path', 'use', 'svg', 'g', 'circle', 'rect', 'line', 'polyline', 'polygon', 'ellipse', 'defs', 'clipPath', 'mask', 'symbol'];
    let cur = el;
    if (svgTags.indexOf(cur.tagName.toLowerCase()) >= 0) {
      cur = cur.closest('a, button, [role="button"], li, input, select, [onclick], [data-testid], [id]')
        || cur.parentElement
        || cur;
    }
    const sel = makeUniqueSelector(cur);
    return {selector: sel, text: (cur.innerText || cur.value || '').trim().slice(0, 50), tag: cur.tagName.toLowerCase()};
  };
  document.addEventListener('click', (ev) => {
    const d = describe(ev.target);
    events.push({type: 'click', ...d, ts: Date.now()});
  }, true);
  document.addEventListener('input', (ev) => {
    const d = describe(ev.target);
    events.push({type: 'input', ...d, value: ev.target.value, ts: Date.now()});
  }, true);
  document.addEventListener('change', (ev) => {
    const d = describe(ev.target);
    events.push({type: 'change', ...d, value: ev.target.value, ts: Date.now()});
  }, true);
  window.__zlx_recorder_dump = () => { const r = events.splice(0, events.length); return r; };
  window.__zlx_recorder_stop = () => { window.__zlx_recorder = false; };
})()
"""