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
    # 真实点击内容：{text: 被点元素可见文字, href: 被点链接的真实地址}，用于历史/报告展示
    clicked: Optional[dict] = None

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

        # 位置序号定位：「第N个」意图（如「第一个视频」）不靠 LLM 猜选择器，
        # 直接从页面真实可见链接里取第 N 个，比假 CSS / 模型猜更可靠。
        ordinal = await self._ordinal_locate(intent, page)
        if ordinal:
            ctx.log(
                f"按「第 {_ordinal_of(intent)} 个」位置定位成功 [{ordinal.selector}]"
                f"（目标类型：{'视频链接' if '视频' in intent else '通用链接/按钮'}）"
            )
            self._save_cache(cache_key, url, intent, ordinal.selector, 2)
            return ordinal

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
            if await self._verify_selector(page, dom_result.selector) and await self._verify_anchor(
                page, page.locator(dom_result.selector).first, intent
            ):
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
            if not await self._verify_anchor(page, loc.first, intent):
                ctx.log(f"第1层：命中 [{selector}] 但文字与意图标签不符，拒绝并继续降级")
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

        返回的选择器带 nth=，精确指向验证通过的**那一个**元素：
        若只返回 text=热门（子串匹配），点击时取 .first 会点到 DOM 里
        第一个含「热门」的无关元素（如横幅「热门番剧影视看不停」），
        与内部验证通过的元素不一致。
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
                    # 精确到验证通过的这一项：带引号=精确整段匹配，nth=锁定位置
                    quoted = f'"{text}"' if exact else text
                    selector = f"text={quoted} >> nth={i}"
                    return LocateResult(
                        method="selector",
                        value=selector,
                        selector=selector,
                        source_layer=2,
                        confidence=0.95,
                    )
        return None

    async def _ordinal_locate(self, intent: str, page: Page) -> Optional[LocateResult]:
        """按「第N个」位置描述定位：从页面真实可点击链接里取第 N 个。

        用于模型编造了假选择器、且意图是「第一个视频/第2条」这类位置描述时，
        不靠 LLM 猜选择器，直接按可见链接顺序取第 N 个，保证点到的确实是
        「第几个」，而不是模型随手给的选择器。
        """
        n = _ordinal_of(intent)
        if not n:
            return None
        # 按目标类型选择候选列表：提到「视频」优先取视频链接，否则通用链接/按钮
        candidates = []
        if "视频" in (intent or ""):
            candidates.append("a[href*='/video/']")
        candidates.append("a[href], button")
        for sel in candidates:
            try:
                loc = page.locator(sel)
                count = await loc.count()
            except Exception:
                continue
            if count <= 0:
                continue
            seen = 0
            for i in range(min(count, 80)):
                try:
                    if not await loc.nth(i).is_visible():
                        continue
                except Exception:
                    continue
                seen += 1
                if seen == n:
                    selector = f"{sel} >> nth={i}"
                    return LocateResult(
                        method="selector",
                        value=selector,
                        selector=selector,
                        source_layer=2,
                        confidence=0.9,
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
                loc = page.get_by_text(text, exact=True).first
                if await loc.count() > 0 and await loc.is_visible(timeout=1000):
                    return LocateResult(
                        method="selector", value=f'text="{text}"', selector=f'text="{text}"', confidence=0.9
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
        # 意图是「第N个」位置描述时，明确让模型按列表序号挑，而不是自由发挥
        ordinal_n = _ordinal_of(intent)
        if ordinal_n:
            prompt = (
                "注意：操作意图明确是「第 N 个」（位置描述）。请从元素列表中按顺序数，"
                f"选出第 {ordinal_n} 个匹配目标类型的元素（如第{ordinal_n}个视频链接/列表项），"
                "返回能唯一定位到它的选择器（优先带 nth 的精确选择器），不要返回任意一个同类元素。\n"
            ) + prompt
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
        # 意图是纯 CSS 选择器（录制器存的精确选择器）时，视觉模型看不懂 CSS，
        # 返回的坐标只是瞎猜（如把「div>p」猜成顶部导航的「娱乐」）。此时直接
        # 跳过视觉定位，宁可靠失败也不点错元素。
        if re.search(r"[#.\[\]:=\s/]", _intent_text(intent)):
            return None
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
        # 跨层验证：视觉坐标指向的元素文字须与意图标签相符，否则视为定位错误
        if not _anchor_match(_intent_anchor(intent), await self._text_at_coord(page, x, y)):
            return None
        return LocateResult(method="coordinate", value=(x, y), confidence=conf)

    def _save_cache(self, key: str, url: str, intent: str, selector: str, layer: int) -> None:
        cache_set(key, url, intent, selector, layer)

    # ---- 跨层互相验证（以意图标签为锚） ----
    async def _element_text(self, loc: Any) -> str:
        """读取元素可见文字。"""
        try:
            return (await loc.evaluate("el => (el.innerText || el.textContent || '').trim()")) or ""
        except Exception:
            return ""

    async def _text_at_coord(self, page: Page, x: float, y: float) -> str:
        """读取页面某比例坐标处元素的文字。"""
        try:
            return (await page.evaluate(
                """(xy) => {
                    const el = document.elementFromPoint(
                        Math.round(window.innerWidth * xy.x),
                        Math.round(window.innerHeight * xy.y)
                    );
                    return el ? (el.innerText || el.textContent || '').trim().slice(0, 80) : '';
                }""",
                {"x": x, "y": y},
            )) or ""
        except Exception:
            return ""

    async def _verify_anchor(self, page: Page, loc: Any, intent: str) -> bool:
        """校验定位到的元素文字是否与意图标签一致（宽松规则，放行式判断）。"""
        return _anchor_match(_intent_anchor(intent), await self._element_text(loc))

    # ---- 低信任点击的视觉复核保障 ----
    @staticmethod
    def is_low_trust(intent: str) -> bool:
        """低信任点击：意图里既无真实标签、也不是「第N个」位置描述时才算。

        - 无文字（只有 CSS 选择器）→ 低信任，需视觉复核防止点错相邻元素
        - 有真实标签（如"热门""登录"）→ 文字定位优先，无需复核
        - text 是精确 CSS 选择器（录制器生成，如图片卡片无文字时）→ 用户真实
          点击过的位置，第1层 CSS 命中即可信，无需复核（否则会误拒录制动作）
        - 位置描述（如"第一个视频""第2条"，含说明里"第一个图片"）→ 已明确
          指定第几个，视觉复核会把"第1个"误读成要"找叫'第一个'的文字"而误拒，
          故跳过
        """
        text = _intent_text(intent)
        if not text:
            return True
        if _is_label(text):
            return False
        # text 含选择器语法 → 录制器把精确 CSS 存进了 text，直接信任 CSS 命中
        if re.search(r"[#.\[\]:=\s/]", text):
            return False
        # 位置描述：在整个意图（含说明）里识别「第N个」
        if re.search(r"第[一二三四五六七八九十百0-9]+[个条项页]", intent):
            return False
        return True

    async def visual_confirm(self, page: Page, intent: str, loc: Any) -> Optional[bool]:
        """截取命中元素截图，问视觉模型它是否用户想点击的目标。

        返回 True=是 / False=不是 / None=无法判断（未配Key、截图失败或模型报错）。
        """
        try:
            box = await loc.bounding_box()
            if not box or box["width"] < 5 or box["height"] < 5:
                return None
            shot = await page.screenshot(
                type="png",
                clip={k: box[k] for k in ("x", "y", "width", "height")},
            )
        except Exception:
            return None
        prompt = (
            "下面截图是网页上一个被选中的元素。请判断它是不是用户想点击的目标。\n"
            f"用户意图：{intent}\n"
            '只输出 JSON：{"yes": true} 或 {"yes": false}'
        )
        try:
            data = await LLMClient.vision_ask(prompt, shot, timeout=LAYER4_TIMEOUT)
            return bool(data.get("yes"))
        except Exception:
            return None

    async def visual_locate(self, intent: str, page: Page) -> Optional[tuple]:
        """全页视觉定位兜底：返回目标中心坐标 (x, y)；失败返回 None。"""
        res = await self._layer4(intent, page)
        if res and res.method == "coordinate" and res.confidence >= CONFIDENCE_THRESHOLD:
            return (res.value[0], res.value[1])
        return None

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


def _is_label(text: str) -> bool:
    """疑似真实页面标签：短文本、不含选择器语法/空格/网址/位置描述。

    排除「第N个/第N条/第N页」这类位置、序数描述（"第一个视频"不是标签），
    也排除含"的"的描述性短语——它们交给视觉复核，避免误拦真实目标。
    """
    if not text:
        return False
    if re.search(r"[#.\[\]:=\s/]", text):
        return False
    if not (2 <= len(text) <= 8):
        return False
    if re.search(r"第[一二三四五六七八九十百0-9]+[个条项页]", text):
        return False
    if "的" in text:
        return False
    return True


_CN_NUMS = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
            "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def _cn_to_int(s: str) -> Optional[int]:
    """中文/阿拉伯数字转整数，如「一」→1、「十二」→12、「二十」→20。失败返回 None。"""
    if not s:
        return None
    if s.isdigit():
        return int(s)
    total = 0
    section = 0
    for ch in s:
        if ch == "十":
            section = section * 10 if section else 10
        elif ch == "百":
            section *= 100
        elif ch in _CN_NUMS:
            section += _CN_NUMS[ch]
        else:
            return None
    return total + section


def _ordinal_of(intent: str) -> Optional[int]:
    """从意图里提取「第N个」的位置序号；不是位置描述返回 None。"""
    m = re.search(r"第([一二三四五六七八九十百0-9]+)[个条项页]", intent or "")
    if not m:
        return None
    n = _cn_to_int(m.group(1))
    return n if n and n >= 1 else None


def _intent_anchor(intent: str) -> str:
    """从意图中提取用于跨层验证的标签锚点；无有效标签时返回空串。

    例如「点击元素「热门」」→ "热门"；「点击元素「.video-list .item:first-child」」→ ""。
    """
    text = _intent_text(intent)
    return text if _is_label(text) else ""


def _anchor_match(anchor: str, el_text: str) -> bool:
    """标签锚点与元素文本比对（宽松规则，避免误拦）：
    - 锚点不是有效标签 / 元素无文字 / 元素是长文本（标题、段落）→ 放行
    - 两者都是短标签时，必须互相包含才算匹配，否则拒绝（防止点错相邻标签）
    """
    if not _is_label(anchor):
        return True
    el_text = (el_text or "").strip()
    if not el_text:
        return True
    if not _is_label(el_text) and len(el_text) > 12:
        return True
    return anchor in el_text or el_text in anchor