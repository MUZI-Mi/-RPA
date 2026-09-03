"""自然语言解析

调用大模型，将用户口语转为结构化规则（TaskConfig JSON），
并支持按用户新要求对已有方案做多轮修改（refine）。
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict

from llm_client import LLMClient, LLMError
from rule_engine import RuleEngine, RuleValidationError

# 选择器异常阈值：超过这些值即视为 LLM 编造的垃圾选择器，需清洗
_MAX_SELECTOR_DEPTH = 25
_MAX_SELECTOR_LEN = 300

SYSTEM_PROMPT = """你是一个网页自动化操作生成器。用户会用自然语言描述需求，你要把它转换为可执行的规则 JSON。

要求：
1. 严格输出 JSON 对象，只包含以下字段：task_name、description、schedule、speed_mode、steps
2. schedule 识别时间意图：
   - "每天早上9点" → {"type": "cron", "expression": "0 9 * * *"}
   - "每个工作日8点半" → {"type": "cron", "expression": "30 8 * * 1-5"}
   - "每隔2小时" → {"type": "interval", "interval": {"hours": 2}}
   - 无时间意图 → {"type": "once"}
3. steps 是数组，每个步骤含 step_id（从1递增）、note（见第7条）和 action。action.type 只能是白名单：
   open / click / input / select / extract / wait / scroll / hover / press_key / upload /
   reload / back / forward / close_tab / set_var /
   goto / if_text / if_element / if_var / foreach / foreach_if /
   ocr / llm_extract / export / read_excel / read_csv / ocr_to_json / data_clean / llm_summarize
4. 普通 action 字段说明：
   - open: {"url": "..."}
   - click: {"selector": "...", "text": "目标元素上可见的精炼文字（2~6字）"}
     text 必须填目标元素上**肉眼可见的文字**（如"热门""登录""确认"），绝不填整句描述
     （整句描述写进 note）。例：点热门标签 → {"selector": ".nav-item:nth-child(2)", "text": "热门"}；
     目标无文字（如图标）才可省略 text
   - input: {"selector": "...", "value": "..."}
   - extract: {"selector": "...", "extract_type": "text", "save_as": "..."}
   - wait: {"value": 秒数}
   - reload: {"": ""} 刷新当前网页
   - back: {"": ""} 浏览器后退
   - forward: {"": ""} 浏览器前进
   - close_tab: {"close_target": ""} 关闭网页。close_target 可留空=关闭当前标签页（回到列表页）；若用户说「关闭xx这个网页」则填 xx（如"关闭番剧页"→close_target=番剧），只关闭标题/网址含该词的标签页
   - set_var: {"var": "变量名", "op": "set/inc/dec", "value": 数字} 设置/增减变量
   - ocr: {"ocr_source": "page/element", "selector": "可选，要识别的元素", "save_as": "..."}
     把整页或某块的截图用 AI 识别成文字（OCR），存进变量，用于图片/扫描件/验证码等无法直接提取的页面
   - llm_extract: {"var"/"selector"/"text": "输入来源", "fields": "标题,日期,金额", "save_as": "..."}
     把一段文字交给 AI，按 fields 抽取成结构化字段（JSON）。输入来源三选一：
     var=上一步提取的变量名 / selector=页面上文字位置 / text=直接给的文字
   - export: {"export_format": "csv/json/xlsx/docx/pdf", "export_filename": "文件名", "template_file": "可选，模板中心里的模板名"}
     把「逐个打开时收集的每条数据」导出成一个数据文件（报表）。放在遍历步骤之后
   - read_excel / read_csv: {"file_path": "本地文件路径", "has_header": true, "save_as": "..."}
     读取本地 Excel/CSV 文件为表格数据，存进变量（用于报表加工）
   - ocr_to_json: {"ocr_source": "page/element", "selector": "可选", "fields": "标题,日期,金额", "save_as": "..."}
     截图 → OCR 识别 → 按字段整理成结构化表格（JSON 数组）
   - data_clean: {"source": "变量名或留空(用收集到的表)", "rules": {"dedup": ["去重列"], "fill_empty": {"列": "填充值"}, "date_format": ["日期列"], "drop_columns": ["删除列"]}, "save_as": "..."}
     数据清洗：去重、空值填充、日期格式统一、删列。关键列缺失可标记异常进审核
   - llm_summarize: {"source": "变量名或留空(用收集到的表)", "batch_size": 10, "save_as": "..."}
     把表格数据交给 AI 生成语义总结与异常预警，低置信度/异常数据自动进入人工审核队列
   - 注：以上报表动作的字段会随用户描述自然生成，用户没提就用默认
5. 控制流 action（用于条件分支、循环、翻页等复杂流程）：
   - goto: {"target": 目标step_id}，无条件跳转到某个步骤
   - if_text: {"text": "关键词", "goto_if_found": step_id, "goto_if_not": step_id}
     页面文本包含关键词 → 跳 goto_if_found，否则 → 跳 goto_if_not
   - if_element: {"selector": "...", "goto_if_found": step_id, "goto_if_not": step_id}
     元素存在 → 跳 goto_if_found，否则 → 跳 goto_if_not
   - if_var: {"var": "变量名", "op": "比较符", "value": "期望值", "goto_if_found": step_id, "goto_if_not": step_id}
     对变量做判断后分支；op ∈ equals / contains / not_equals / not_contains / less / less_equals / greater / greater_equals
   - goto_if_found / goto_if_not 可为 null，表示结束执行
   - 循环：用 set_var 初始化/递增计数器变量 + if_var 判断 + goto 跳回前面的 step_id
   - click 的选择器可用 {{变量名}} 引用变量（如点第 N 个：{{i}}），变量会被替换为当前值
   - 重要：若用户描述了"对每个条目/每条记录/翻页直到处理完/打开第1个第2个…逐个处理"这类需求，
     必须用 计数器+循环 的写法：set_var 初始化计数器 → click {{计数器}} 定位当前项 → 处理 →
     set_var 计数器加1 → if_var 判断未结束则 goto 跳回循环体，不要只生成线性步骤
6. 每个 action 额外输出 confidence（0~1 置信度）字段。
7. note 字段（重要）：每个步骤必须额外输出 note —— 用大白话的一句话描述该步骤要做什么，
   面向完全不懂技术的用户（如行政、财务人员）。要求：
   - 不写 CSS 选择器、网址、变量名、step_id 等专业内容
   - 写清楚"打开哪个网页 / 点击哪个内容 / 输入什么 / 最后要做什么"
   - 例如 open 公告页 → note="打开巨潮资讯网股票 603192 的公告列表页"
   - 例如 foreach 遍历公告链接 → note="逐个打开公告标题下的每条公告，看完后关闭，直到最后一页再切换下一页"
   - 例如 close_tab → note="关闭刚打开的公告页面"
   - 例如 wait → note="稍等 2 秒，等页面加载"
8. 选择器（selector）硬性要求：
   - 必须是网页元素的**标识**（CSS 选择器，如 a[href*='detail']、li a、.item a）
   - **严禁把中文句子/中文描述当选择器**（如 "财务报告下的文件链接"、"下一页按钮" 都是错的）
   - 不确定真实结构时：对「列表里的链接」统一用通用选择器 `a[href]`；
     对翻页按钮不确定时 next_selector 留空；对普通可点击目标不确定时用 text 文字定位、不写 selector
   - 系统会自愈定位，选择器只需合理即可。
9. 通用遍历（特别重要）：当用户想要「把某列表里的链接/条目全都点一遍/逐个打开/都浏览一次」，
   且列表数量未知、可能需要翻页时，不要生成复杂的 set_var+if_var 循环，
   而是用**一个 foreach 步骤**：
   - action: {"type": "foreach", "selector": "列表链接的CSS选择器（如 ul#ul1 li a 或 .announcement a）", "next_selector": "分页"下一页"按钮的CSS选择器，如 a.nextPage；若用户没说翻页可留空"}
   - foreach 会自动逐个打开这些链接、查看后关闭，全部读完后再点下一页继续，直到没有下一页。
   例如「把这个网站公告标题下的链接全都点一遍，然后关闭，到末页就切换下一页」
   → 一个步骤 open(打开公告列表网址) + 一个步骤 foreach(selector=公告链接, next_selector=下一页)
   即可，不要用 set_var/if_var/goto 去手工拼循环。
   - 非常重要：只要用户提到「逐个打开/都看一遍/全都点一遍」并且可能涉及「翻页/下一页」，
     **必须合并成一个 foreach 步骤**（同时带 selector 和 next_selector），
     绝不能拆成两个 foreach，也不能在 foreach 后面再生成点击/后退/跳转等多余步骤。
10. 若遍历对象不是链接而是要「逐个操作」的普通条目（无跳转链接），才回退到计数器循环写法。
11. 逐条筛选处理（foreach_if）：当用户想「从列表/表单里逐条检查，命中条件才处理（如点"确认"），
    其他自动跳过」，且可能需要翻页时，用一个 foreach_if 步骤：
    - action: {"type": "foreach_if",
               "selector": "列表项的选择器（如 tbody tr 或 ul li）",
               "match_text": "命中关键词（该项文字包含它就处理，如"差旅"）",
               "click_selector": "命中的项里要点的按钮/链接，如 button 含"确认"；若想直接打开该项链接可留空",
               "next_selector": "分页"下一页"按钮，如 button.btn-next；用户没说翻页可留空"}
    - 系统会逐条检查：该项文字包含 match_text 就点 click_selector（或打开该项链接），
      不包含就自动跳过，当前页查完再点 next_selector 翻页继续，直到没有下一页。
    例如「把报销单列表里名称含"差旅"的单据点确认，其他的跳过」
    → 一个步骤 open(列表网址) + 一个步骤 foreach_if(selector=表格行, match_text=差旅, click_selector=确认按钮)
    即可，不要在 foreach_if 后再生成多余的点击/跳转步骤。
12. 选择器书写规范（重要，违反会判为不合格）：
   - 选择器必须简洁：优先用类名/id/标签组合，如 ul.video-list li:first-child a、.hot-list .item a
   - 禁止输出超长的逐层嵌套链（div > div > … 超过 10 层）——这种选择器在真实网页里一定匹配不到，
     宁可写短一点（如 .feed-card:first-child）也不要编长链
   - 目标是「列表第 1 个 / 第 N 个」时，用 :first-child / :nth-child(N) 这类简洁写法
   - 目标有可见文字（按钮/标签/链接文字）时，把文字写进 text 字段（如点击「热门」→ text="热门"），
     系统会优先按文字定位，最可靠
   - 实在不确定选择器：selector 写短或留空，把目标描述写进 text，系统会自己分析网页定位，不要瞎编长链

只输出 JSON，不要任何解释文字。"""

REFINE_SYSTEM_PROMPT = """你是一个网页自动化操作方案的修改助手。用户已经有一份可执行的规则 JSON，现在提出新的修改要求，你要输出**修改后的完整规则 JSON**。

要求：
1. 只输出 JSON 对象，字段与原方案一致：task_name、description、schedule、speed_mode、steps
2. steps 保持 step_id 从 1 连续递增；用户没要求改动的步骤保持原样，只按要求增/删/改
3. 每个步骤都带 note（用大白话描述该步骤做什么，面向不懂技术的用户）；被修改的步骤必须同步更新 note
4. 动作类型白名单同初次生成：
   open / click / input / select / extract / wait / scroll / hover / press_key / upload /
   reload / back / forward / close_tab / set_var / goto / if_text / if_element / if_var /
   foreach / foreach_if / ocr / llm_extract / export / read_excel / read_csv /
   ocr_to_json / data_clean / llm_summarize
5. 修改口径示例：
   - "第2步改成先输入账号" → 把第2步 action 改为 input（value 填相应内容）
   - "删掉第3步" → 移除该步骤并重新编号
   - "翻页按钮改成 a.nextPage" → 更新对应 foreach 的 next_selector
   - "每步之间等 3 秒" → 在相关步骤后加 wait 步骤
   - "增加一步：打开百度" → 在合适位置插入 open 步骤
   - "把遍历的链接改成 li a" → 更新 foreach 的 selector
6. 选择器书写规范（重要）：选择器必须简洁（类名/id/标签组合或 :first-child/:nth-child(N)），
   禁止输出超过 10 层的 div > div > … 嵌套链；click 步骤的 text 必须填目标元素上可见的精炼文字
   （如"热门""登录""确认"，2~6 字），不要填整句描述（整句描述写进 note），目标无文字才可省略 text
7. 若用户只是说"可以/没问题/再确认一遍/就是这样"等，则原样返回当前方案。
8. 输出格式硬性要求（违反会失败）：
   - steps 必须是「步骤对象数组」，禁止输出成字符串列表（如 ["打开网址"]）或纯文本
   - 每个步骤对象必须含 step_id、action（action.type 必填）
   - 输出必须是一整个完整 JSON 对象，不能截断
9. 遇到看不清/不确定的步骤，**原样保留原步骤内容**，只改动用户明确要求的部分。
10. **遍历意图必须合并为 foreach（特别重要）**：当用户的修改要求包含「逐个打开/每条都点/
    都看一遍/看完关闭/翻页直到没有下一页」这类遍历意图时，必须把方案中重复的线性 click 步骤
    合并成**一个 foreach 步骤**，不要保留一堆重复的 click/close_tab：
    - action: {"type": "foreach", "selector": "列表链接的CSS选择器", "next_selector": "翻页按钮选择器"}
    - foreach 会自动逐个打开链接、查看后关闭、全部读完点下一页继续，直到没有下一页
    - foreach 的 selector 可从原方案 click 步骤的选择器中提取**通用列表项链接形式**
      （去掉 nth-child(N) 序号），如 #bond-finance-content-list li a、ul li a、a[href]
    - 删除原方案中所有被 foreach 取代的重复 click/close_tab 步骤
    - 示例：原方案是 open + click×18，用户要求"逐个打开全部报告再关闭、末页点下一页继续"
      → 应输出 open + 一个 foreach(selector=列表链接, next_selector=下一页) 共 2 步
只输出 JSON，不要任何解释文字。"""

NOTES_SYSTEM_PROMPT = """你是网页自动化操作的大白话翻译助手。用户录制了一段网页操作，下面是每一步的动作 JSON（含 step_id、动作类型、选择器、文字、输入值等）。

请给每一步写一句大白话说明（note），面向完全不懂技术的用户（如行政、财务人员）。

要求：
1. 只输出一个 JSON 对象，格式为 {"notes": [{"step_id": 1, "note": "..."}, ...]}，notes 数量与输入一致、顺序一致
2. 必须为输入里的**每一步**都写一条 note，一条都不能少；宁可简单也不能漏
3. 每句简短、口语化，不写 CSS 选择器、class、变量名、网址等专业内容
4. 尽量用动作里的文字/值来描述，写清楚「点哪里 / 输入什么 / 做什么」，例如：
   - 点击了文字为「登录」的元素 → "点击页面上的「登录」按钮"
   - 在输入框输入了内容 → "在输入框里输入 xxx"
   - 关闭了标签页 → "关闭刚打开的页面"
   - 刷新页面 → "刷新当前页面"
   - 选择下拉框 → "在下拉框里选择 xxx"
5. 说明里带上具体文字或值，让用户一看就懂
只输出 JSON，不要任何解释文字。"""


class NLParser:
    @staticmethod
    def _extract_click_text(note: str) -> str:
        """从步骤大白话说明中提取目标可见文字（click 缺 text 时兜底）。

        只取高置信模式，避免误提取：
        1) 引号/书名号内的文字：「热门」「登录」
        2) "点击X标签/按钮/链接/图标…" 中的 X（如「点击热门标签…」→ 热门）
        """
        note = (note or "").strip()
        if not note:
            return ""
        m = re.search(r"[「『\"'](.+?)[」』\"']", note)
        if m:
            return m.group(1).strip()[:8]
        m = re.search(r"点击(.{1,6}?)(?:标签|按钮|链接|图标|选项|菜单|栏目|分区|入口|卡片|控件)", note)
        if m:
            return m.group(1).strip()[:8]
        return ""

    @staticmethod
    def _fix_cn_selectors(action: Dict[str, Any]) -> Dict[str, Any]:
        """把中文句子/描述被误当选择器的字段，兜底替换为通用可执行选择器或删除。

        foreach/foreach_if 的 selector 和 next_selector、click/input/extract 的 selector，
        LLM 不了解真实网页结构时常输出中文（如 "财务报告下的文件链接"），可执行性为 0。
        这里统一处理，避免生成不可执行的规则。
        """
        a_type = action.get("type")

        def _cn_fallback(sel: str, kind: str):
            if not isinstance(sel, str):
                return sel
            s = sel.strip()
            if not re.search(r"[\u4e00-\u9fff]", s):
                return sel  # 无中文，原样保留
            if len(s) > 20:
                # 一段含中文的长描述 → 判定为描述性内容，非真实选择器
                return None
            # 可能是「xxx按钮/链接」这类短语；只要能拆出纯 CSS 后缀就保留，否则作废
            if re.fullmatch(r"[^A-Za-z\[\].#>\s]+", s):
                return None  # 全是中文/标点 → 不是选择器
            return sel

        if a_type == "foreach":
            if not action.get("selector") or _cn_fallback(action["selector"], "sel") is None:
                action["selector"] = "a[href]"
            nxt = action.get("next_selector")
            if nxt:
                fixed = _cn_fallback(nxt, "next")
                if fixed is None:
                    action.pop("next_selector", None)  # 翻页按钮不确定时留空，不阻塞遍历
                else:
                    action["next_selector"] = fixed
            return action

        if a_type == "foreach_if":
            if not action.get("selector") or _cn_fallback(action["selector"], "sel") is None:
                action["selector"] = "ul li"
            return action

        # 普通 click/input/extract：中文选择器直接删除，交由自愈按 text/文字定位
        sel = action.get("selector")
        if isinstance(sel, str) and re.search(r"[\u4e00-\u9fff]", sel.strip()):
            if a_type in ("click", "input", "hover", "extract"):
                action.pop("selector", None)
        return action

    @staticmethod
    def _drop_nulls(obj: Any) -> Any:
        """递归去掉值为 None 的字段。

        LLM 修改方案时常把模型全字段回显并填 null（如 url:null、note:null），
        这些 null 会让 jsonschema 校验误报「None is not of type ...」。
        缺省即表示 None，语义等价，因此直接删除。
        """
        if isinstance(obj, dict):
            return {k: NLParser._drop_nulls(v) for k, v in obj.items() if v is not None}
        if isinstance(obj, list):
            return [NLParser._drop_nulls(x) for x in obj]
        return obj

    @staticmethod
    def _sanitize_selectors(data: Dict[str, Any]) -> Dict[str, Any]:
        """清洗 LLM 生成的异常选择器。

        LLM 对结构复杂的网站（如 B 站首页）常输出几百层的 div > div > ... 嵌套链，
        这类选择器在真实 DOM 里必然匹配不到、只会浪费大量自愈时间。处理策略：
        - 有 text 字段：直接删掉垃圾选择器，交给「按文本定位 + 自愈」处理
        - 无 text 字段：只保留最深 3 段（通常含类名/id），尽量别整条作废
        """
        for step in data.get("steps", []):
            action = step.get("action") or {}
            sel = action.get("selector")
            if not isinstance(sel, str) or not sel.strip():
                continue
            depth = len([s for s in sel.split(">") if s.strip()])
            if depth <= _MAX_SELECTOR_DEPTH and len(sel) <= _MAX_SELECTOR_LEN:
                continue
            if action.get("text"):
                action.pop("selector", None)
            else:
                segs = [s.strip() for s in sel.split(">") if s.strip()]
                action["selector"] = " > ".join(segs[-3:])
        return data

    @staticmethod
    def _finalize(data: Dict[str, Any], fallback_name: str) -> Dict[str, Any]:
        """清洗 LLM 输出：补默认字段、去 confidence、类型规整、去 null，并做 schema 校验。"""
        steps = data.get("steps", [])
        if not isinstance(steps, list):
            steps = []
        cleaned_steps = []
        for i, s in enumerate(steps):
            # 模型偶发把步骤输出成字符串（如 steps:["打开网址"]）或纯文本，格式错误直接丢弃
            if not isinstance(s, dict):
                continue
            step = dict(s)
            step.setdefault("step_id", i + 1)
            step.setdefault("condition", {"type": "always"})
            action = step.get("action")
            if not isinstance(action, dict):
                action = {}
            action = dict(action)
            action.pop("confidence", None)
            # 模型复制/修改长方案时常把某一步的 action 输出成空对象 {}（无 type），
            # 无法执行且会让 schema 校验失败导致整个修改崩掉。直接丢弃该步骤，
            # 保留其余可执行步骤，而不是让整个方案失败。
            if not action.get("type"):
                continue
            # 中文句子/描述被误当选择器（如 "财务报告下的文件链接"、"下一页按钮"）
            # 时，可执行性为 0。按动作类型兜底替换为通用可执行选择器或删除：
            action = NLParser._fix_cn_selectors(action)
            # click 步骤缺 text 时，自动从 note 里提取目标可见文字兜底，
            # 让执行时优先走文字定位（如 note="点击热门标签…" → text="热门"），
            # 不依赖模型每次是否老实填 text。
            if action.get("type") == "click" and not action.get("text"):
                t = NLParser._extract_click_text(step.get("note") or "")
                if t:
                    action["text"] = t
            # value 字段在模型里是字符串（input/if_var/set_var 等共用）。
            # LLM 时常把数字笔误输出成 int（如 value:2、value:0），这里统一转 str，
            # 避免响应校验阶段因类型不符而闪成 500「解析失败」。
            if action.get("value") is not None and not isinstance(action.get("value"), str):
                action["value"] = str(action["value"])
            # 控制流跳转目标统一转 int（LLM 可能输出字符串），null 保持 None
            for key in ("target", "goto_if_found", "goto_if_not"):
                if action.get(key) is not None:
                    try:
                        action[key] = int(action[key])
                    except (TypeError, ValueError):
                        action[key] = None
            step["action"] = NLParser._drop_nulls(action)
            cleaned_steps.append(NLParser._drop_nulls(step))
        data["steps"] = cleaned_steps
        # 清洗异常选择器（超长 div 嵌套链等），避免执行时浪费大量自愈时间
        data = NLParser._sanitize_selectors(data)
        name = data.get("task_name")
        if not isinstance(name, str) or not name.strip():
            data["task_name"] = fallback_name[:20]
        # 顶层（含 schedule）残留的 null 一并清理，避免校验报 "None is not of type ..."
        data = NLParser._drop_nulls(data)
        data.setdefault("schedule", {"type": "once"})
        sched = data.get("schedule")
        if not isinstance(sched, dict) or not sched.get("type"):
            data["schedule"] = {"type": "once"}
        data.setdefault("speed_mode", "normal")

        # Schema 校验
        try:
            RuleEngine.validate(data)
        except RuleValidationError as e:
            raise LLMError(f"方案未通过校验：{e}")

        return data

    @staticmethod
    async def _chat_finalize(system_prompt: str, user_text: str, fallback_name: str) -> Dict[str, Any]:
        """调 LLM 生成并做最终清洗/校验，返回完整方案 JSON。"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ]
        data = await LLMClient.chat_json(messages, temperature=0.1)
        return NLParser._finalize(data, fallback_name)

    @staticmethod
    async def _with_retry(generate: Any) -> Dict[str, Any]:
        """LLM 偶发输出空 steps（校验报 "should be non-empty"）时自动重试一次。

        重试后仍为空则抛一条给用户看的友好错误；其它校验错误不重试、直接抛。
        """
        last_err: Any = None
        for _ in range(2):  # 首次 + 1 次重试
            try:
                data = await generate()
                if data.get("steps"):
                    return data
            except LLMError as e:
                last_err = e
                if "should be non-empty" not in str(e):
                    raise
        if last_err is not None and "should be non-empty" not in str(last_err):
            raise last_err
        raise LLMError("没太理解你的意思，生成的方案是空的，请换个说法再试一次")

    @staticmethod
    async def parse(user_input: str) -> Dict[str, Any]:
        return await NLParser._with_retry(
            lambda: NLParser._chat_finalize(SYSTEM_PROMPT, user_input, user_input)
        )

    @staticmethod
    def _compact_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
        """精简方案后传给模型做多轮修改：去掉冗余空字段、截断超长选择器，
        减小模型输出压力，避免长 JSON 让免费模型输出截断或结构损坏。"""
        compact: Dict[str, Any] = {
            "task_name": cfg.get("task_name"),
            "description": cfg.get("description"),
            "schedule": cfg.get("schedule"),
            "speed_mode": cfg.get("speed_mode"),
            "steps": [],
        }
        keep = {
            "type", "url", "selector", "next_selector", "text", "value", "keys",
            "extract_type", "save_as", "close_target", "var", "op",
            "target", "goto_if_found", "goto_if_not", "match_text",
            "fields", "ocr_source", "export_format", "export_filename", "template_file",
            "file_path", "sheet_name", "has_header", "encoding", "delimiter",
            "source", "rules", "batch_size", "threshold", "append_to_table",
        }
        for s in cfg.get("steps") or []:
            if not isinstance(s, dict):
                continue
            st: Dict[str, Any] = {
                "step_id": s.get("step_id"),
                "condition": {"type": (s.get("condition") or {}).get("type", "always")},
            }
            a = s.get("action")
            na = {k: v for k, v in (a or {}).items() if k in keep and v not in (None, "")}
            for k in ("selector", "next_selector"):
                if isinstance(na.get(k), str) and len(na[k]) > 60:
                    na[k] = na[k][:60] + "..."
            st["action"] = na
            if s.get("note"):
                st["note"] = s["note"]
            compact["steps"].append(st)
        return compact

    @staticmethod
    async def refine(user_input: str, current_config: Dict[str, Any]) -> Dict[str, Any]:
        """按用户新要求修改已有方案，返回修改后的完整方案 JSON。"""
        prompt = (
            "当前方案（JSON）：\n"
            + json.dumps(NLParser._compact_config(current_config), ensure_ascii=False, indent=2)
            + "\n\n用户的修改要求：\n"
            + user_input
        )
        return await NLParser._with_retry(
            lambda: NLParser._chat_finalize(REFINE_SYSTEM_PROMPT, prompt, user_input)
        )

    @staticmethod
    async def add_notes(steps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """给录制生成的步骤补大白话说明（note）。

        LLM 失败（未配置 Key/网络异常等）时原样返回，不阻塞录制结果。
        """
        if not steps:
            return steps
        try:
            messages = [
                {"role": "system", "content": NOTES_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(steps, ensure_ascii=False, indent=2)},
            ]
            data = await LLMClient.chat_json(messages, temperature=0.1)
            notes = data.get("notes") or []
            note_map: Dict[int, str] = {}
            for n in notes:
                if isinstance(n, dict) and n.get("step_id") is not None:
                    note_map[int(n["step_id"])] = str(n.get("note") or "").strip()
            for s in steps:
                sid = s.get("step_id")
                if sid is not None and note_map.get(int(sid)):
                    s["note"] = note_map[int(sid)]
        except Exception:
            pass
        # 兜底：LLM 漏写说明的步骤，用动作类型生成一句默认大白话，保证每步都有
        for s in steps:
            if not s.get("note"):
                s["note"] = NLParser._note_fallback(s)
        return steps

    @staticmethod
    def _note_fallback(step: Dict[str, Any]) -> str:
        """给缺少 note 的步骤生成一句兜底大白话说明。"""
        action = step.get("action") or {}
        atype = action.get("type", "")
        text = (action.get("text") or "").strip()
        value = (action.get("value") or "").strip()
        target = (action.get("close_target") or "").strip()
        if atype == "click" and text:
            return f"点击页面上的「{text}」"
        if atype == "input" and value:
            return f"在输入框里输入 {value}"
        if atype == "select" and value:
            return f"在下拉框里选择 {value}"
        if atype == "close_tab" and target:
            return f"关闭标题或网址带「{target}」的页面"
        if atype == "close_tab":
            return "关闭当前打开的页面"
        if atype == "reload":
            return "刷新当前页面"
        if atype == "back":
            return "返回上一页"
        if atype == "forward":
            return "前进一页"
        if atype == "scroll":
            return "滚动页面"
        if atype == "extract":
            return "读取页面上的内容"
        if atype == "wait":
            return "稍等片刻，等页面加载完成"
        if atype == "open":
            return "打开对应的网页"
        if atype == "hover":
            return "把鼠标移到页面上的目标"
        if atype == "press_key":
            return "在页面上按下对应按键"
        if atype == "upload":
            return "上传文件"
        if atype == "set_var":
            return "更新内部记录的数字"
        return f"执行「{atype}」操作"