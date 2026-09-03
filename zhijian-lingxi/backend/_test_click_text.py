"""验证 click 缺 text 时自动从 note 提取目标文字。"""
from nl_parser import NLParser, LLMError


def case(note, expected):
    data = {
        "task_name": "t",
        "schedule": {"type": "once"},
        "steps": [
            {"step_id": 1, "action": {"type": "open", "url": "https://www.bilibili.com/"}, "note": "打开哔哩哔哩网站首页"},
            {
                "step_id": 2,
                "action": {"type": "click", "selector": ".nav-item:nth-child(2)"},
                "note": note,
            },
        ],
    }
    try:
        out = NLParser._finalize(data, "t")
    except LLMError as e:
        print(f"FAIL[{note}] schema err: {e}")
        return
    txt = out["steps"][1]["action"].get("text", "")
    status = "OK " if txt == expected else "FAIL"
    print(f"{status} note={note!r} -> text={txt!r} (expect {expected!r})")
    assert txt == expected, f"expected {expected!r}, got {txt!r}"


case("点击热门标签，观看热门视频推荐", "热门")
case("点击「登录」按钮", "登录")
case("点击确认按钮，确认报销单", "确认")
case("点击下一页按钮", "下一页")
case("打开百度首页", "")  # 无点击目标 → 不提取
case("点击热门区域的第一条视频", "")  # 无高置信模式 → 不瞎提取

print("ALL PASS")
