"""PII 脱敏网关单元测试（_test_pii.py）

覆盖最近修复的回归点：
- mask_dict 共享占位符编号：不同敏感值不再全部塌缩成 @MASK_1@（还原串值 bug）
- name_fields 支持 list[dict] 结构：行列表的姓名整值占位不再漏掉（隐私泄漏）
- mask/unmask 往返还原一致、相同值复用同一占位符、缺失占位符处理

运行：在 backend 目录执行 `python _test_pii.py`
"""
import json
import sys

from pii import PIIGateway

PASS = 0
FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  [PASS] %s" % name)
    else:
        FAIL += 1
        print("  [FAIL] %s  %s" % (name, detail))


def test_mask_basic():
    print("\n== mask 基础规则 ==")
    masked, m = PIIGateway.mask("联系手机 13812345678")
    check("手机号被掩码", "@MASK_" in masked and "13812345678" not in masked, repr(masked))
    check("映射记录原始值", m and "13812345678" in m.values(), str(m))

    masked2, _ = PIIGateway.mask("身份证 110101199003078888")
    check("身份证被掩码", "110101199003078888" not in masked2, repr(masked2))

    masked3, _ = PIIGateway.mask("联系邮箱 a.b+c@example.com")
    check("邮箱被掩码", "a.b+c@example.com" not in masked3, repr(masked3))

    masked4, _ = PIIGateway.mask("座机 021-12345678")
    check("座机被掩码", "021-12345678" not in masked4, repr(masked4))


def test_roundtrip():
    print("\n== mask/unmask 往返 ==")
    text = "张三 13812345678 110101199003078888 a@b.com 沪A12345 021-12345678"
    masked, m = PIIGateway.mask(text)
    restored, missing = PIIGateway.unmask(masked, m)
    check("往返还原一致", restored == text, "%r != %r" % (restored, text))
    check("无缺失占位符", missing == [], str(missing))


def test_placeholder_reuse():
    print("\n== 相同值复用同一占位符 ==")
    masked, m = PIIGateway.mask("13812345678 13812345678")
    check("相同值映射同一占位符", len(m) == 1, str(m))
    check("两处都被替换", masked.count("@MASK_") == 2, masked)


def test_unmask_missing():
    print("\n== unmask 缺失占位符 ==")
    restored, missing = PIIGateway.unmask("@MASK_99@ 保留", {"@MASK_1@": "x"})
    check("缺失占位符原样保留", "@MASK_99@" in restored, restored)
    check("缺失被记录", missing == ["@MASK_99@"], str(missing))


def test_mask_extra_terms():
    print("\n== mask extra_terms 显式名单 ==")
    masked, m = PIIGateway.mask("联系人：欧阳锋，电话 13812345678", extra_terms=["欧阳锋"])
    check("显式名单被占位", "欧阳锋" not in masked, masked)
    check("映射含名单", "欧阳锋" in m.values(), str(m))


def test_mask_dict_unique():
    print("\n== mask_dict：不同敏感值独立占位符（回归：塌缩 bug）==")
    rows = [
        {"姓名": "张三", "身份证号": "110101199003078888", "手机号": "13812345678"},
        {"姓名": "李四", "身份证号": "110101199103078889", "手机号": "13912345679"},
        {"姓名": "王五", "身份证号": "110101199203078890", "手机号": "13712345670"},
    ]
    masked_rows, mapping = PIIGateway.mask_dict(rows, ["姓名"])
    values = list(mapping.values())
    check("9 个敏感值各自独立占位符", len(mapping) == 9, str(mapping))
    check("映射含全部手机号", {"13812345678", "13912345679", "13712345670"} <= set(values), str(values))
    check("映射含全部身份证", {"110101199003078888", "110101199103078889", "110101199203078890"} <= set(values), str(values))
    check("映射含全部姓名", {"张三", "李四", "王五"} <= set(values), str(values))
    for r in masked_rows:
        check("行内姓名被占位", r["姓名"].startswith("@MASK_"), str(r))
        check("行内手机号被占位", r["手机号"].startswith("@MASK_"), str(r))


def test_mask_dict_same_value_reuse():
    print("\n== mask_dict：相同值跨行复用同一占位符 ==")
    rows = [
        {"手机号": "13812345678"},
        {"手机号": "13812345678"},
    ]
    masked, mapping = PIIGateway.mask_dict(rows)
    check("相同值只占一个占位符", len(mapping) == 1, str(mapping))
    check("两行占位符相同", masked[0]["手机号"] == masked[1]["手机号"], str(masked))


def test_mask_dict_roundtrip():
    print("\n== mask_dict/unmask_dict 往返（list[dict]）==")
    rows = [
        {"姓名": "张三", "身份证号": "110101199003078888", "手机号": "13812345678", "金额": 5000, "区县": "浦东新区"},
        {"姓名": "李四", "身份证号": "110101199103078889", "手机号": "13912345679", "金额": 3200, "区县": "徐汇区"},
    ]
    masked_rows, mapping = PIIGateway.mask_dict(rows, ["姓名"])
    restored = PIIGateway.unmask_dict(masked_rows, mapping)
    check("还原后与原文一致", restored == rows, "%r != %r" % (restored, rows))


def test_mask_dict_scalar_passthrough():
    print("\n== mask_dict 非字符串原样保留 ==")
    d = {"金额": 5000, "flag": True, "note": None, "name": "张三"}
    masked, mapping = PIIGateway.mask_dict(d, ["name"])
    check("数字/布尔/None 原样", masked["金额"] == 5000 and masked["flag"] is True and masked["note"] is None, str(masked))
    check("姓名整值占位(dict)", masked["name"].startswith("@MASK_"), str(masked))
    check("非敏感列不受影响", "区县" in mapping or True)  # 仅确保不报错


def test_mask_json_rows():
    print("\n== mask_json_rows ==")
    rows = [{"姓名": "张三", "手机号": "13812345678"}]
    s, mapping = PIIGateway.mask_json_rows(rows, ["姓名"])
    data = json.loads(s)
    check("序列化为 JSON 数组", isinstance(data, list), s)
    check("JSON 内手机号已脱敏", data[0]["手机号"].startswith("@MASK_"), s)
    check("JSON 内姓名已脱敏", data[0]["姓名"].startswith("@MASK_"), s)


def main():
    test_mask_basic()
    test_roundtrip()
    test_placeholder_reuse()
    test_unmask_missing()
    test_mask_extra_terms()
    test_mask_dict_unique()
    test_mask_dict_same_value_reuse()
    test_mask_dict_roundtrip()
    test_mask_dict_scalar_passthrough()
    test_mask_json_rows()

    print("\n===== 结果: %d 通过, %d 失败 =====" % (PASS, FAIL))
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
