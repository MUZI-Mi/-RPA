"""任务执行器（核心调度）

驱动 Playwright 浏览器执行规则步骤，
集成弹窗拦截、新窗口接管、随机延迟、智能自愈、截图与报告。
"""

from __future__ import annotations

import asyncio
import random
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import SCREENSHOT_DIR, SPEED_MODES, ensure_dirs
from rule_engine import RuleEngine, CONTROL_FLOW_TYPES
from self_healing import SelfHealing, HealingContext, ElementNotFoundError

try:
    from playwright.async_api import (
        Browser,
        BrowserContext,
        Page,
        async_playwright,
    )
except ImportError:  # pragma: no cover
    Browser = BrowserContext = Page = Any  # type: ignore
    async_playwright = None  # type: ignore


class BrowserManager:
    """浏览器生命周期管理。"""

    def __init__(self):
        self._pw = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None

    async def start(self, headless: bool = True) -> Browser:
        self._pw = await async_playwright().start()
        self.browser = await self._pw.chromium.launch(headless=headless)
        self.context = await self.browser.new_context()
        return self.browser

    async def new_page(self) -> Page:
        return await self.context.new_page()

    async def start_attach(self, cdp_url: str) -> Browser:
        """连接到一个已以调试模式启动的浏览器（Edge/Chrome/360）。"""
        self._pw = await async_playwright().start()
        self.browser = await self._pw.chromium.connect_over_cdp(cdp_url)
        contexts = self.browser.contexts
        # 优先沿用已有上下文（用户已登录的浏览器），无则新建
        self.context = contexts[0] if contexts else await self.browser.new_context()
        return self.browser

    async def close(self) -> None:
        try:
            if self.browser:
                await self.browser.close()
            if self._pw:
                await self._pw.stop()
        except Exception:
            pass


class PageOperator:
    """页面操作封装，统一处理自愈定位与动作执行。"""

    def __init__(self, healing: SelfHealing):
        self.healing = healing

    async def _resolve_locator(
        self, page: Page, selector: str, intent: str, ctx: HealingContext
    ):
        """通过自愈机制定位元素，返回 locator 或坐标。"""
        result = await self.healing.locate(selector, intent, page, ctx)
        if result.method == "coordinate":
            return ("coordinate", result.value)
        return ("locator", page.locator(result.value).first)

    async def click(self, page: Page, selector: str, intent: str = "", ctx: Optional[HealingContext] = None) -> bool:
        ctx = ctx or HealingContext()
        kind, val = await self._resolve_locator(page, selector, intent or "点击元素", ctx)
        if kind == "coordinate":
            await SelfHealing.click_by_coordinate(page, *val)
            return True
        # 目标是链接时，记住其绝对 href，用于点击后验证是否真正跳转
        href = None
        try:
            href = await val.evaluate("el => { const c = el.closest('a[href]'); return c ? c.href : null; }")
        except Exception:
            pass
        before = page.url
        # 正常点击，缩短默认超时；元素不稳定（轮播图动画）时快速降级
        try:
            await val.click(timeout=8000)
        except Exception:
            ctx.log("元素不稳定/被遮挡，降级为强制点击")
            try:
                await val.click(force=True, timeout=5000)
            except Exception:
                ctx.log("强制点击失败，降级为 JS 直接点击")
                try:
                    await val.evaluate("el => el.click()")
                except Exception:
                    pass
        # 点击后验证页面是否跳转：链接被弹窗/遮罩拦截时「点击成功但无反应」。
        # 用 wait_for_url 轮询等待 URL 真正变化（页面加载慢时也不误判）。
        if href and href != before:
            navigated = False
            try:
                await page.wait_for_url(lambda u: u != before, timeout=8000)
                navigated = True
            except Exception:
                navigated = False
            if not navigated:
                ctx.log(f"点击链接后页面未跳转（可能被遮罩拦截），直接导航到 {href}")
                try:
                    await page.goto(href, wait_until="domcontentloaded", timeout=15000)
                except Exception:
                    pass
        return True

    async def input_text(self, page: Page, selector: str, value: str, speed: str = "normal",
                         intent: str = "", ctx: Optional[HealingContext] = None) -> bool:
        ctx = ctx or HealingContext()
        kind, val = await self._resolve_locator(page, selector, intent or "输入内容", ctx)
        if kind == "coordinate":
            await SelfHealing.click_by_coordinate(page, *val)
            target = page
        else:
            target = val
            await val.click()
        # 模拟打字
        lo, hi = SPEED_MODES.get(speed, SPEED_MODES["normal"])
        for ch in str(value):
            await target.keyboard.type(ch, delay=random.randint(30, 90))
        return True

    async def select(self, page: Page, selector: str, value: str, intent: str = "",
                     ctx: Optional[HealingContext] = None) -> bool:
        ctx = ctx or HealingContext()
        kind, val = await self._resolve_locator(page, selector, intent or "选择下拉项", ctx)
        if kind == "coordinate":
            await SelfHealing.click_by_coordinate(page, *val)
            return True
        await val.select_option(value)
        return True

    async def extract(self, page: Page, selector: str, extract_type: str = "text",
                      attribute: str = "", intent: str = "", ctx: Optional[HealingContext] = None) -> Any:
        ctx = ctx or HealingContext()
        # 提取动作不要求元素可见（如 <title>、隐藏字段），先尝试直接定位
        locator = page.locator(selector).first
        try:
            if await locator.count() == 0:
                raise Exception("no element")
        except Exception:
            # 直接定位失败，走自愈降级
            kind, val = await self._resolve_locator(page, selector, intent or "提取数据", ctx)
            if kind == "coordinate":
                return None
            locator = val
        if extract_type == "text":
            # text_content 可提取隐藏元素文本；title 等标签 inner_text 为空
            text = await locator.text_content()
            return (text or "").strip()
        if extract_type == "attribute":
            return await locator.get_attribute(attribute or "value")
        if extract_type == "inner_html":
            return await locator.inner_html()
        if extract_type == "value":
            return await locator.input_value()
        if extract_type == "count":
            return await locator.count()
        return (await locator.text_content() or "").strip()


class TaskExecutor:
    """任务执行器。"""

    def __init__(self):
        self.manager = BrowserManager()
        self.healing = SelfHealing()
        self.operator = PageOperator(self.healing)

    async def run(
        self,
        task_config: Dict[str, Any],
        on_step_log=None,
        on_screenshot=None,
        exec_id: str = "",
        headless: bool = True,
        stop_event: Optional[asyncio.Event] = None,
        attach_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """执行完整任务，返回执行结果摘要。"""
        ensure_dirs()
        stop_event = stop_event or asyncio.Event()
        speed = task_config.get("speed_mode", "normal")
        steps = RuleEngine.normalize_steps(task_config.get("steps", []))
        context_vars: Dict[str, Any] = {}
        step_logs: List[Dict[str, Any]] = []
        start_time = time.time()

        screenshot_dir = SCREENSHOT_DIR / (task_config.get("task_name", "task")[:20] or "task") / (exec_id or str(int(start_time)))
        screenshot_dir.mkdir(parents=True, exist_ok=True)

        try:
            if attach_url:
                await asyncio.wait_for(self.manager.start_attach(attach_url), timeout=15)
            else:
                await asyncio.wait_for(self.manager.start(headless=headless), timeout=30)
        except asyncio.TimeoutError:
            await self.manager.close()
            raise RuntimeError(
                "浏览器启动/连接超时：内置浏览器 30 秒未就绪，或接管模式未连接到调试浏览器（默认端口 9222）"
            )
        page = await self.manager.new_page()
        await self._register_page_handlers(page)

        current_page: List[Page] = [page]

        try:
            # 建立 step_id -> 数组下标 映射，供 goto/if 跳转
            id_to_index: Dict[int, int] = {}
            for idx, s in enumerate(steps):
                id_to_index[int(s.get("step_id", idx + 1))] = idx

            # 程序指针 + 最大步数保护（防止死循环）
            pc = 0
            max_steps = max(1000, len(steps) * 200)
            executed = 0

            while pc < len(steps):
                if stop_event.is_set():
                    break
                if executed >= max_steps:
                    step_logs.append({
                        "step_id": steps[pc].get("step_id"),
                        "action_type": "loop_guard",
                        "status": "failed",
                        "error_info": f"超过最大执行步数 {max_steps}，疑似死循环已终止",
                    })
                    break

                step = steps[pc]
                action = RuleEngine.resolve_params(step.get("action", {}), context_vars)
                condition = step.get("condition", {}) or {}
                step_id = step.get("step_id", len(step_logs) + 1)
                atype = action.get("type", "")
                intent = self._build_intent(action)
                ctx = HealingContext()

                # ---- 控制流动作：不操作页面，只改 pc ----
                if atype in CONTROL_FLOW_TYPES:
                    jump = await self._eval_control_flow(
                        current_page[0], action, context_vars
                    )
                    try:
                        page_url = current_page[0].url
                    except Exception:
                        page_url = None
                    log = {
                        "step_id": step_id,
                        "action_type": atype,
                        "target_element": self._control_target(action),
                        "status": "success",
                        "duration_ms": 0,
                        "healing_actions": [],
                        "extracted": jump["remark"],
                        "page_url": page_url,
                    }
                    step_logs.append(log)
                    if on_step_log:
                        on_step_log(log)
                    if jump["to"] is None:
                        break  # 结束执行
                    target_idx = id_to_index.get(jump["to"])
                    if target_idx is None:
                        log["status"] = "failed"
                        log["error_info"] = f"跳转目标 step_id {jump['to']} 不存在"
                        break
                    pc = target_idx
                    executed += 1
                    continue

                # ---- 普通动作 ----
                t0 = time.time()
                before_path = await self._shot(current_page[0], screenshot_dir, f"{step_id}_before")
                try:
                    # 条件等待
                    if not await self._wait_condition(current_page[0], condition):
                        raise ElementNotFoundError(f"条件未满足: {condition.get('type')}")

                    # 执行动作
                    result = await self._execute_action(
                        current_page, action, speed, intent, ctx, stop_event
                    )
                    # 随机延迟（模拟人类）
                    lo, hi = SPEED_MODES.get(speed, SPEED_MODES["normal"])
                    await asyncio.sleep(random.uniform(lo, hi))

                    # 提取变量
                    save_as = action.get("save_as")
                    if save_as and result is not None:
                        context_vars[save_as] = result

                    duration = int((time.time() - t0) * 1000)
                    after_path = await self._shot(current_page[0], screenshot_dir, f"{step_id}_after")
                    # 记录「该步骤执行后」所在页面
                    try:
                        page_url = current_page[0].url
                    except Exception:
                        page_url = None
                    log = {
                        "step_id": step_id,
                        "action_type": atype,
                        "target_element": action.get("selector") or action.get("url") or "",
                        "status": "success",
                        "duration_ms": duration,
                        "screenshot_before": str(before_path) if before_path else None,
                        "screenshot_after": str(after_path) if after_path else None,
                        "healing_actions": ctx.actions,
                        "extracted": result,
                        "page_url": page_url,
                    }
                    step_logs.append(log)
                    if on_step_log:
                        on_step_log(log)
                except Exception as e:
                    duration = int((time.time() - t0) * 1000)
                    err_text = str(e) or repr(e)
                    try:
                        page_url = current_page[0].url
                    except Exception:
                        page_url = None
                    log = {
                        "step_id": step_id,
                        "action_type": atype,
                        "target_element": action.get("selector") or action.get("url") or "",
                        "status": "failed",
                        "duration_ms": duration,
                        "healing_actions": ctx.actions,
                        "error_info": err_text,
                        "page_url": page_url,
                    }
                    step_logs.append(log)
                    if on_step_log:
                        on_step_log(log)
                    # 失败不中断，继续后续步骤，但记录错误
                pc += 1
                executed += 1
        finally:
            await self.manager.close()

        total_ms = int((time.time() - start_time) * 1000)
        failed = [l for l in step_logs if l["status"] == "failed"]
        status = "success" if not failed else ("failed" if len(failed) == len(step_logs) else "partial")
        return {
            "status": status,
            "duration_ms": total_ms,
            "steps": step_logs,
            "error_msg": "; ".join(l.get("error_info", "") for l in failed) if failed else None,
        }

    # ---- 内部实现 ----
    def _build_intent(self, action: Dict[str, Any]) -> str:
        atype = action.get("type")
        desc = action.get("text") or action.get("selector") or action.get("url") or ""
        map_intent = {
            "click": f"点击元素「{desc}」",
            "input": f"在输入框「{desc}」输入内容",
            "select": f"选择「{desc}」中的选项",
            "extract": f"提取「{desc}」的数据",
        }
        return map_intent.get(atype, f"执行{atype}操作：{desc}")

    async def _eval_control_flow(
        self, page: Page, action: Dict[str, Any], context_vars: Dict[str, Any]
    ) -> Dict[str, Any]:
        """求值控制流动作，返回 {"to": <step_id|None>, "remark": str}。

        - goto: 无条件跳转到 target
        - if_text: 页面文本包含指定关键词则跳 goto_if_found，否则 goto_if_not
        - if_element: 元素存在则跳 goto_if_found，否则 goto_if_not
        to 为 None 表示结束执行。
        """
        atype = action.get("type")

        if atype == "goto":
            return {"to": action.get("target"), "remark": f"跳转到步骤 {action.get('target')}"}

        if atype == "if_text":
            text = str(action.get("text", ""))
            try:
                body_text = await page.evaluate("() => document.body.innerText || ''")
            except Exception:
                body_text = ""
            found = text and (text in body_text)
            target = action.get("goto_if_found") if found else action.get("goto_if_not")
            label = "命中" if found else "未命中"
            return {"to": target, "remark": f"if_text 关键词「{text}」{label} → 跳转 {target}"}

        if atype == "if_element":
            selector = action.get("selector", "")
            try:
                found = await page.locator(selector).first.count() > 0
            except Exception:
                found = False
            target = action.get("goto_if_found") if found else action.get("goto_if_not")
            label = "存在" if found else "不存在"
            return {"to": target, "remark": f"if_element 「{selector}」{label} → 跳转 {target}"}

        if atype == "if_var":
            var_name = action.get("var", "")
            expected = str(action.get("value", ""))
            op = action.get("op", "equals")  # equals / contains / not_equals / not_contains
            actual = context_vars.get(var_name)
            actual_s = "" if actual is None else str(actual)
            if op == "equals":
                found = actual_s == expected
            elif op == "not_equals":
                found = actual_s != expected
            elif op == "not_contains":
                found = expected not in actual_s
            else:  # contains
                found = expected in actual_s
            target = action.get("goto_if_found") if found else action.get("goto_if_not")
            label = "命中" if found else "未命中"
            return {
                "to": target,
                "remark": f"if_var {var_name}={actual_s!r} {op} {expected!r} {label} → 跳转 {target}",
            }

        return {"to": None, "remark": f"未知控制流动作 {atype}"}

    def _control_target(self, action: Dict[str, Any]) -> str:
        atype = action.get("type", "")
        if atype == "goto":
            return f"target={action.get('target')}"
        if atype == "if_text":
            return f"text={action.get('text')} → 有[{action.get('goto_if_found')}]/无[{action.get('goto_if_not')}]"
        if atype == "if_element":
            return f"selector={action.get('selector')} → 有[{action.get('goto_if_found')}]/无[{action.get('goto_if_not')}]"
        if atype == "if_var":
            return f"var {action.get('var')} {action.get('op', 'contains')} {action.get('value')} → 是[{action.get('goto_if_found')}]/否[{action.get('goto_if_not')}]"
        return atype

    async def _register_page_handlers(self, page: Page) -> None:
        # 弹窗自动关闭
        page.on("dialog", lambda d: asyncio.ensure_future(self._dismiss_dialog(d)))

    async def _dismiss_dialog(self, dialog) -> None:
        try:
            await dialog.dismiss()
        except Exception:
            pass

    async def _wait_condition(self, page: Page, condition: Dict[str, Any]) -> bool:
        ctype = condition.get("type", "always")
        timeout = condition.get("timeout", 10000)
        if ctype == "always":
            return True
        if ctype == "page_load":
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=timeout)
                return True
            except Exception:
                return True
        if ctype == "element_visible":
            sel = condition.get("selector")
            try:
                await page.locator(sel).first.wait_for(state="visible", timeout=timeout)
                return True
            except Exception:
                return False
        if ctype == "text_appears":
            text = condition.get("text", "")
            try:
                await page.get_by_text(text).first.wait_for(state="visible", timeout=timeout)
                return True
            except Exception:
                return False
        return True

    async def _execute_action(
        self, current_page: List[Page], action: Dict[str, Any], speed: str,
        intent: str, ctx: HealingContext, stop_event: asyncio.Event,
    ) -> Any:
        page = current_page[0]
        atype = action.get("type")
        if atype == "open":
            await page.goto(action.get("url", ""), wait_until="domcontentloaded")
            await self._settle(page)
            return None
        if atype == "click":
            await self.operator.click(page, action.get("selector", ""), intent, ctx)
            await self._settle(page)
            return None
        if atype == "input":
            await self.operator.input_text(page, action.get("selector", ""),
                                           action.get("value", ""), speed, intent, ctx)
            return None
        if atype == "select":
            await self.operator.select(page, action.get("selector", ""),
                                       action.get("value", ""), intent, ctx)
            return None
        if atype == "extract":
            return await self.operator.extract(
                page, action.get("selector", ""),
                action.get("extract_type", "text"),
                action.get("attribute", ""), intent, ctx
            )
        if atype == "wait":
            try:
                await asyncio.sleep(float(action.get("value", 1)))
            except (TypeError, ValueError):
                await asyncio.sleep(1)
            return None
        if atype == "scroll":
            await page.mouse.wheel(0, action.get("amount", 300) or 300)
            return None
        if atype == "hover":
            kind, val = await self.operator._resolve_locator(
                page, action.get("selector", ""), intent, ctx
            )
            if kind == "locator":
                await val.hover()
            return None
        if atype == "press_key":
            await page.keyboard.press(action.get("keys", "Enter"))
            return None
        if atype == "upload":
            kind, val = await self.operator._resolve_locator(
                page, action.get("selector", ""), intent or "上传文件", ctx
            )
            if kind == "locator":
                await val.set_input_files(action.get("files", []))
            return None
        raise ValueError(f"未知动作类型: {atype}")

    async def _settle(self, page: Page, seconds: float = 1.2) -> None:
        """等待页面相对稳定。

        打开页面/点击后会触发动态内容加载（如轮播图动画、热榜请求），
        这里等一次加载态结束并静置片刻，减少下一步定位命中抖动中的元素。
        """
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=6000)
        except Exception:
            pass
        await asyncio.sleep(seconds)

    async def _shot(self, page: Page, dirpath: Path, name: str) -> Optional[str]:
        try:
            path = dirpath / f"{name}.jpg"
            await page.screenshot(path=str(path), type="jpeg", quality=70)
            return str(path)
        except Exception:
            return None