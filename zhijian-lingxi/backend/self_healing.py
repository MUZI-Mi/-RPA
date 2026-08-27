"""智能自愈机制（四层降级）

元素定位从轻到重逐层尝试：
  第1层：CSS 选择器精确匹配
  第2层：文本/aria-label/placeholder 模糊匹配 + 相邻元素推断
  第3层：精简 DOM → Qwen-Plus 分析返回选择器
  第4层：页面截图 → Qwen-VL 视觉定位返回坐标

还包括弹窗拦截、加载重试、定位结果缓存等辅助能力。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, List, Optional

from config import CONFIDENCE_THRESHOLD, DOM_MAX_NODES, LAYER3_TIMEOUT, LAYER4_TIMEOUT
from database import cache_lookup, cache_set

try:
    from playwright.async_api import Page
    from playwright.async_api import TimeoutError as PWTimeout
except ImportError:  # pragma: no cover
    Page = Any  # type: ignore
    PWTimeout = Exception  # type: ignore

from llm_client import LLMClient, LLMError


class ElementNotFoundError(Exception):
    pass


@dataclass
class LocateResult:
    """定位结果：可能是选择器，也可能是坐标。"""

    method: str                       # selector / coordinate
    value: Any = None                 # selector 字符串 或 (x, y) 坐标
    confidence: float = 1.0
    source_layer: int = 1
    selector: Optional[str] = None

    def __bool__(self) -> bool:
        return self.value is not None


@dataclass
class HealingContext:
    """记录自愈过程，用于报告展示。"""

    actions: List[str] = field(default_factory=list)

    def log(self, msg: str) -> None:
        self.actions.append(msg)


# 第2层属性优先级链
_FUZZY_ATTRS = ["data-testid", "aria-label", "placeholder", "id", "name", "title"]


class SelfHealing:
    def __init__(self):
        self.cache: dict[str, LocateResult] = {}

    # ---- 对外主入口 ----
    async def locate(
        self,
        selector: str,
        intent: str,
        page: Page,
        ctx: Optional[HealingContext] = None,
    ) -> LocateResult:
        ctx = ctx or HealingContext()
        url = page.url
        cache_key = f"{url}::{intent}::{selector}"

        # 文本精确定位优先：录制的元素文本（如「番剧」「原创」）远比 nth-child
        # 链稳定——录制时的 DOM 序号在执行时常失配，但文字还在。
        text_located = await self._text_locate(intent, page)
        if text_located:
            ctx.log(f"按文本精确定位成功 [{text_located.selector}]（意图「{_intent_text(intent)}」）")
            self._save_cache(cache_key, url, intent, text_located.selector, 2)
            return text_located

        # 第1层：CSS 选择器匹配（唯一性 + 文本过滤）
        located = await self._layer1(selector, intent, page, ctx)
        if located:
            self._save_cache(cache_key, url, intent, located.selector, 1)
            return located

        # 缓存：仅在第1层未命中时作为辅助，命中历史第2/3/4层的定位结果
        cached = cache_lookup(cache_key)
        if cached and cached.get("cached_selector"):
            ctx.log(f"命中定位缓存：{cached['cached_selector']}（第{cached.get('source_layer')}层）")
            result = LocateResult(
                method="selector",
                value=cached["cached_selector"],
                selector=cached["cached_selector"],
                source_layer=cached.get("source_layer") or 1,
                confidence=0.95,
            )
            if await self._verify_selector(page, result.value):
                return result

        # 第2层
        fuzzy = await self._layer2(selector, intent, page)
        if fuzzy:
            ctx.log(f"第2层：语义模糊匹配成功 [{fuzzy.selector}]（置信度 {fuzzy.confidence:.2f}）")
            fuzzy.source_layer = 2
            self._save_cache(cache_key, url, intent, fuzzy.selector, 2)
            return fuzzy

        # 第3层
        dom_result = await self._layer3(selector, intent, page)
        if dom_result and dom_result.confidence >= CONFIDENCE_THRESHOLD:
            ctx.log(f"第3层：LLM 分析 DOM 成功 [{dom_result.selector}]（置信度 {dom_result.confidence:.2f}）")
            dom_result.source_layer = 3
            if await self._verify_selector(page, dom_result.selector):
                self._save_cache(cache_key, url, intent, dom_result.selector, 3)
                return dom_result

        # 第4层
        vis_result = await self._layer4(intent, page)
        if vis_result and vis_result.confidence >= CONFIDENCE_THRESHOLD:
            ctx.log(f"第4层：视觉定位成功 坐标{vis_result.value}（置信度 {vis_result.confidence:.2f}）")
            vis_result.source_layer = 4
            return vis_result

        raise ElementNotFoundError(f"元素定位失败（四层降级均未命中）：{selector}")

    # ---- 各层实现 ----
    async def _layer1(
        self, selector: str, intent: str, page: Page, ctx: HealingContext
    ) -> Optional[LocateResult]:
        """第1层：CSS 选择器匹配。

        选择器唯一时直接命中；匹配多个元素时尝试用意图文本（录制时的元素
        文本）精确定位，避免点到错误的第一个匹配；仍无法区分则继续降级。
        """
        try:
            loc = page.locator(selector)
            count = await loc.count()
        except Exception:
            return None
        if count <= 0:
            return None
        if count == 1:
            try:
                await loc.first.wait_for(state="visible", timeout=1500)
            except Exception:
                return None
            ctx.log(f"第1层：CSS 选择器精确匹配成功 [{selector}]")
            return LocateResult(method="selector", value=selector, selector=selector, source_layer=1)
        # 多个匹配：尝试用意图文本过滤精确定位
        text = _intent_text(intent)
        if text:
            try:
                esc = text.replace("'", "\\'")
                refined = f"{selector}:has-text('{esc}')"
                flt = page.locator(refined)
                if await flt.count() == 1:
                    await flt.first.wait_for(state="visible", timeout=1500)
                    ctx.log(f"第1层：选择器匹配 {count} 个，按文本「{text}」精确定位 [{refined}]")
                    return LocateResult(method="selector", value=refined, selector=refined, source_layer=1)
            except Exception:
                pass
        ctx.log(f"第1层：选择器匹配 {count} 个元素且无法按文本区分，继续降级")
        return None

    async def _text_locate(self, intent: str, page: Page) -> Optional[LocateResult]:
        """按意图文本精确定位可交互元素。

        优先精确匹配（元素或其可交互祖先文本完全等于目标），再模糊匹配。
        模糊匹配只接受「短文本标签」——文本长度不超过目标 3 倍且 ≤ 20，
        避免「原创」误点中标题「XXX原创XXX」这类长文本视频卡片。
        """
        text = _intent_text(intent)
        if not text or re.search(r"[#.\[\]:]", text):
            return None
        for exact in (True, False):
            try:
                loc = page.get_by_text(text, exact=exact)
                n = await loc.count()
            except Exception:
                continue
            if n == 0:
                continue
            for i in range(min(n, 20)):
                try:
                    info = await loc.nth(i).evaluate(
                        """(el, arg) => {
                            const c = el.closest('a, button, [role="button"], input, select, textarea, label, li, [onclick]');
                            if (!c) return null;
                            const t = (c.innerText || '').trim();
                            if (t.length === 0) return null;
                            if (arg.exact) {
                                if (t !== arg.text) return null;
                            } else {
                                // 模糊匹配：只接受长度接近目标的短标签（≤ 目标2倍+4），
                                // 拒绝「XXX原创XXX」这类长标题/段落
                                if (t.length > arg.text.length * 2 + 4) return null;
                                if (t.indexOf(arg.text) < 0) return null;
                            }
                            return { hit: true };
                        }""",
                        {"text": text, "exact": exact},
                    )
                except Exception:
                    continue
                if info:
                    return LocateResult(
                        method="selector",
                        value=f"text={text}",
                        selector=f"text={text}",
                        source_layer=2,
                        confidence=0.95,
                    )
        return None

    async def _verify_selector(self, page: Page, selector: str) -> bool:
        try:
            loc = page.locator(selector).first
            await loc.wait_for(state="visible", timeout=1500)
            return True
        except Exception:
            return False

    async def _layer2(self, selector: str, intent: str, page: Page) -> Optional[LocateResult]:
        # 优先按意图文本精确定位（录制时的元素文本，如「登录」「最新」）
        text = _intent_text(intent)
        if text and not re.search(r"[#.\[\]:]", text):
            try:
                loc = page.get_by_text(text, exact=False).first
                if await loc.count() > 0 and await loc.is_visible(timeout=1000):
                    return LocateResult(
                        method="selector", value=f"text={text}", selector=f"text={text}", confidence=0.9
                    )
            except Exception:
                pass
        # 提取意图中的文本描述与选择器中的文本提示
        candidates: List[str] = []
        # 若 selector 是 css 类/id，提取可能的关键词
        for attr in _FUZZY_ATTRS:
            candidates.append(f"[{attr}*='{_clean(selector)}']")
        # 文本模糊匹配
        if re.search(r"[\u4e00-\u9fa5a-zA-Z]", _clean(selector)):
            candidates.append(f"text={_clean(selector)}")
        # 角色+名称
        candidates.append(f"get_by_role('button', name='{_clean(selector)}')") if False else None
        for c in candidates:
            try:
                if c.startswith("get_by_role"):
                    continue
                loc = page.locator(c).first
                if await loc.count() > 0 and await loc.is_visible(timeout=1000):
                    return LocateResult(
                        method="selector", value=c, selector=c, confidence=0.85
                    )
            except Exception:
                continue
        return None

    async def _layer3(self, selector: str, intent: str, page: Page) -> Optional[LocateResult]:
        try:
            dom = await page.evaluate(_DOM_SNAPSHOT_JS, DOM_MAX_NODES)
        except Exception:
            return None
        prompt = (
            "你是网页自动化元素定位助手。给定页面可交互元素列表（JSON）与操作意图，"
            "请返回最可能的 CSS 选择器。"
            "输出严格 JSON：{\"selector\": \"...\", \"confidence\": 0.0-1.0}\n"
            f"操作意图：{intent}\n"
            f"元素列表：{dom}"
        )
        try:
            data = await LLMClient.chat_json(
                [{"role": "user", "content": prompt}],
                temperature=0.1,
                timeout=LAYER3_TIMEOUT,
            )
        except Exception:
            # 覆盖 LLMError 与 httpx.ReadTimeout 等所有异常，
            # 保证降级链继续到第4层而不是直接抛错。
            return None
        sel = data.get("selector")
        if not sel:
            return None
        conf = float(data.get("confidence", 0.5))
        return LocateResult(method="selector", value=sel, selector=sel, confidence=conf)

    async def _layer4(self, intent: str, page: Page) -> Optional[LocateResult]:
        try:
            shot = await page.screenshot(type="png")
        except Exception:
            return None
        try:
            data = await LLMClient.vision(intent, shot, timeout=LAYER4_TIMEOUT)
        except Exception:
            return None
        x, y = data.get("x"), data.get("y")
        if x is None or y is None:
            return None
        conf = float(data.get("confidence", 0.5))
        # 点击前验证该坐标处确实有可交互元素，避免视觉定位点到空白/装饰区域
        try:
            ok = await page.evaluate(
                """(xy) => {
                    const vw = window.innerWidth, vh = window.innerHeight;
                    const el = document.elementFromPoint(Math.round(vw * xy.x), Math.round(vh * xy.y));
                    if (!el) return false;
                    const t = el.tagName.toLowerCase();
                    if (t === 'a' || t === 'button' || t === 'input' || t === 'select' || t === 'textarea') return true;
                    return !!el.closest('a, button, [role="button"], input, select, textarea, [onclick]');
                }""",
                {"x": x, "y": y},
            )
        except Exception:
            ok = False
        if not ok:
            return None
        return LocateResult(method="coordinate", value=(x, y), confidence=conf)

    def _save_cache(self, key: str, url: str, intent: str, selector: str, layer: int) -> None:
        cache_set(key, url, intent, selector, layer)

    # ---- 坐标点击辅助 ----
    @staticmethod
    async def click_by_coordinate(page: Page, x: float, y: float) -> None:
        vw = await page.evaluate("window.innerWidth")
        vh = await page.evaluate("window.innerHeight")
        await page.mouse.click(vw * float(x), vh * float(y))


# 精简 DOM 快照脚本（只保留可交互元素）
_DOM_SNAPSHOT_JS = """
(limit) => {
  const tags = ['button', 'a', 'input', 'select', 'textarea', '[role="button"]', 'label'];
  const nodes = [];
  const els = document.querySelectorAll(tags.join(','));
  for (let i = 0; i < els.length && nodes.length < limit; i++) {
    const el = els[i];
    const rect = el.getBoundingClientRect();
    if (rect.width === 0 && rect.height === 0) continue;
    const info = {
      tag: el.tagName.toLowerCase(),
      id: el.id || '',
      class: (el.className && typeof el.className === 'string') ? el.className.slice(0, 80) : '',
      text: (el.innerText || el.textContent || '').trim().slice(0, 50),
      aria: el.getAttribute('aria-label') || '',
      placeholder: el.getAttribute('placeholder') || '',
      title: el.getAttribute('title') || '',
      type: el.getAttribute('type') || '',
      href: el.getAttribute('href') || '',
      name: el.getAttribute('name') || '',
      index: i
    };
    nodes.push(info);
  }
  return JSON.stringify(nodes);
}
"""


def _clean(s: str) -> str:
    """清理选择器字符串，提取用于模糊匹配的关键词。"""
    s = re.sub(r"[#.\[\]=\"'*^$]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:30]


def _intent_text(intent: str) -> str:
    """从意图描述（如「点击元素「登录」」）中提取元素文本关键词。"""
    m = re.search(r"「(.+?)」", intent or "")
    return m.group(1).strip() if m else ""