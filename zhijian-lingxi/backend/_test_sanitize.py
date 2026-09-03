"""验证 _sanitize_selectors：超长选择器应被清洗。"""
import nl_parser

# 1) 超长 div 链 + 无 text → 应裁剪为最后 3 段
bad = "div#main > " + " > ".join(["div"] * 400)
data = {"steps": [{"action": {"type": "click", "selector": bad}}]}
out = nl_parser.NLParser._sanitize_selectors(data)
sel = out["steps"][0]["action"]["selector"]
print("case1 sel =", repr(sel))
assert " > ".join(["div"] * 3) == sel, "case1 fail"

# 2) 超长链 + 有 text → 应删掉 selector，只留 text
data2 = {"steps": [{"action": {"type": "click", "selector": bad, "text": "热门"}}]}
out2 = nl_parser.NLParser._sanitize_selectors(data2)
a = out2["steps"][0]["action"]
print("case2 action =", a)
assert "selector" not in a and a.get("text") == "热门", "case2 fail"

# 3) 正常短选择器 → 原样保留
data3 = {"steps": [{"action": {"type": "click", "selector": "ul.video-list li:first-child a"}}]}
out3 = nl_parser.NLParser._sanitize_selectors(data3)
sel3 = out3["steps"][0]["action"]["selector"]
print("case3 sel =", repr(sel3))
assert sel3 == "ul.video-list li:first-child a", "case3 fail"

# 4) 边界：刚好 25 层 → 不裁剪
edge = " > ".join(["div"] * 25)
data4 = {"steps": [{"action": {"type": "click", "selector": edge}}]}
out4 = nl_parser.NLParser._sanitize_selectors(data4)
assert out4["steps"][0]["action"]["selector"] == edge, "case4 fail"

print("ALL PASS")
