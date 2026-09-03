"""验证跨层锚点逻辑：_is_label / _intent_anchor / _anchor_match。"""
from self_healing import _is_label, _intent_anchor, _anchor_match

# _is_label
assert _is_label("热门") is True
assert _is_label("登录") is True
assert _is_label(".video-list .item:first-child") is False  # 选择器
assert _is_label("第一个视频") is False  # 位置描述不是标签
assert _is_label("点击确认按钮") is True  # 短名词短语可作标签
assert _is_label("确认的按钮") is False  # 含"的"的描述短语不是标签
assert _is_label("https://a.com") is False
assert _is_label("很长的整句描述文字超过八个字了吧") is False
print("is_label ok")

# _intent_anchor
assert _intent_anchor("点击元素「热门」") == "热门"
assert _intent_anchor("点击元素「.video-list .item:first-child」") == ""  # 选择器→无锚
assert _intent_anchor("点击元素「第一个视频」；说明：点击热门区域的第一条视频") == ""  # 位置描述→无锚
assert _intent_anchor("点击元素") == ""
print("intent_anchor ok")

# _anchor_match —— 关键场景
# 1) 锚「热门」 vs 元素「娱乐」→ 拒绝（防止点错相邻标签）
assert _anchor_match("热门", "娱乐") is False
# 2) 锚「热门」 vs 元素「热门」→ 通过
assert _anchor_match("热门", "热门") is True
# 3) 锚「热门」 vs 长标题「热门综艺TOP10全集」→ 放行（长文本不按标签校验）
assert _anchor_match("热门", "热门综艺TOP10全集") is True
# 4) 锚「第一个视频」 vs 视频标题「三体动画 全集」→ 放行（描述性锚不误拦真实目标）
assert _anchor_match("第一个视频", "三体动画 全集") is True
# 5) 无锚 → 放行
assert _anchor_match("", "娱乐") is True
# 6) 元素无文字 → 放行
assert _anchor_match("热门", "") is True
# 7) 元素长文本（列表容器）→ 放行
assert _anchor_match("热门", "首页 热门 直播 游戏中心 娱乐 音乐 舞蹈 游戏 知识") is True
print("anchor_match ok")

print("ALL PASS")
