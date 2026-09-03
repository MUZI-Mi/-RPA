"""PII 脱敏网关

数据进入 AI 前用内置正则规则自动掩码敏感信息（身份证/手机号/银行卡/邮箱/车牌/座机/姓名等），
AI 返回后再按占位符映射反向还原。

设计要点：
- 占位符格式 @MASK_{n}@（不用 {{...}}，避免与规则引擎的 {{变量}}、模板引擎的 {{占位符}} 冲突）
- 相同敏感值映射到同一占位符，保持 LLM 上下文简短、还原一致
- 姓名不做全文正则（2~4 字中文正则会灾难性误伤普通词），
  仅对指定列（name_fields）或显式名单（extra_terms）做整值占位
- mask/unmask 只在单次 LLM 调用局部成对出现，外部永远存明文
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

from database import get_setting

_RULES = [
    # 身份证 18 位（数字边界限定，避免匹配到更长数字串的一部分）
    ("id_card", re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")),
    # 15 位旧身份证（放银行卡前：60/62 开头的 15 位银行卡也属于敏感信息，一并掩码）
    ("id_card15", re.compile(r"(?<!\d)\d{15}(?!\d)")),
    # 手机号
    ("phone", re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")),
    # 银行卡（62/60 开头 14~18 位）
    ("bank_card", re.compile(r"(?<!\d)(?:62|60)\d{14,17}(?!\d)")),
    # 邮箱
    ("email", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    # 车牌（省份简称 + 字母 + 5~6 位）
    ("plate", re.compile(
        r"(?<![A-Z0-9])[京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼]"
        r"[A-Z][A-Z0-9]{5,6}(?![A-Z0-9])"
    )),
    # 座机（0 + 区号 + 号码）
    ("landline", re.compile(r"(?<!\d)0\d{2,3}-?\d{7,8}(?!\d)")),
]

_MASK_RE = re.compile(r"@MASK_\d+@")

# 姓名判定：2~4 个纯中文字符（不含数字/字母），视为姓名
_NAME_RE = re.compile(r"^[\u4e00-\u9fff]{2,4}$")


class PIIGateway:
    """PII 脱敏/还原的静态工具类。"""

    # ---- 开关 ----
    @staticmethod
    def is_enabled() -> bool:
        """读设置 pii_masking_enabled，缺省开启。"""
        v = get_setting("pii_masking_enabled")
        if v is None:
            return True
        return str(v).lower() in ("1", "true", "yes", "on")

    # ---- 占位符管理 ----
    @staticmethod
    def _placeholder_for(val: str, mapping: Dict[str, str], state: Dict[str, int]) -> str:
        """相同值复用同一占位符，否则分配新占位符并记录映射。"""
        for ph, orig in mapping.items():
            if orig == val:
                return ph
        state["seq"] += 1
        ph = f"@MASK_{state['seq']}@"
        mapping[ph] = val
        return ph

    # ---- 文本级 ----
    @staticmethod
    def mask(
        text: Any,
        extra_terms: Optional[Iterable[str]] = None,
    ) -> Tuple[str, Dict[str, str]]:
        """把文本中的敏感信息替换为占位符。

        返回 (masked_text, mapping)；mapping = {占位符: 原始值}。
        extra_terms 为需要整值掩码的显式名单（如姓名列表）。
        """
        text = "" if text is None else str(text)
        if not text:
            return "", {}
        mapping: Dict[str, str] = {}
        state = {"seq": 0}

        for _name, pattern in _RULES:
            text = pattern.sub(
                lambda m: PIIGateway._placeholder_for(m.group(0), mapping, state), text
            )

        for term in extra_terms or []:
            term = str(term).strip()
            if not term:
                continue
            text = re.sub(
                re.escape(term),
                lambda m: PIIGateway._placeholder_for(m.group(0), mapping, state),
                text,
            )
        return text, mapping

    @staticmethod
    def unmask(text: Any, mapping: Dict[str, str]) -> Tuple[str, List[str]]:
        """按映射还原占位符，返回 (还原后文本, 缺失占位符列表)。

        缺失的占位符原样保留并计入 missing，绝不静默丢弃。
        """
        text = "" if text is None else str(text)
        if not text or not mapping:
            return text, []
        missing: List[str] = []

        def _sub(m: "re.Match") -> str:
            ph = m.group(0)
            if ph in mapping:
                return mapping[ph]
            missing.append(ph)
            return ph

        return _MASK_RE.sub(_sub, text), missing

    # ---- 字典/行级 ----
    @staticmethod
    def mask_dict(
        d: Any,
        name_fields: Optional[List[str]] = None,
    ) -> Tuple[Any, Dict[str, str]]:
        """递归对 dict/list 中的字符串值脱敏。

        name_fields：这些列名对应的整值若为姓名（2~4 个纯中文）则整体占位。
        返回 (脱敏后的结构, mapping)。
        """
        mapping: Dict[str, str] = {}
        state = {"seq": 0}

        def _walk(v: Any) -> Any:
            if isinstance(v, dict):
                return {k: _walk(x) for k, x in v.items()}
            if isinstance(v, list):
                return [_walk(x) for x in v]
            if isinstance(v, str):
                masked = v
                # 所有规则用共享 mapping/state，保证同一敏感值复用同一占位符、
                # 不同值分配不同占位符，避免全部塌缩成 @MASK_1@
                for _name, pattern in _RULES:
                    masked = pattern.sub(
                        lambda m: PIIGateway._placeholder_for(m.group(0), mapping, state),
                        masked,
                    )
                return masked
            return v

        out = _walk(d)

        # 姓名列整值占位：支持 dict 或 list[dict] 两种结构
        def _apply_name_fields(obj: Any) -> None:
            if isinstance(obj, dict):
                for k in name_fields:
                    v = obj.get(k)
                    if isinstance(v, str) and "@MASK_" not in v and _NAME_RE.match(v.strip()):
                        obj[k] = PIIGateway._placeholder_for(v.strip(), mapping, state)
            elif isinstance(obj, list):
                for item in obj:
                    _apply_name_fields(item)

        if name_fields:
            _apply_name_fields(out)
        return out, mapping

    @staticmethod
    def unmask_dict(d: Any, mapping: Dict[str, str]) -> Any:
        """递归还原 dict/list 中的占位符。"""
        if not mapping:
            return d

        def _walk(v: Any) -> Any:
            if isinstance(v, dict):
                return {k: _walk(x) for k, x in v.items()}
            if isinstance(v, list):
                return [_walk(x) for x in v]
            if isinstance(v, str):
                text, _missing = PIIGateway.unmask(v, mapping)
                return text
            return v

        return _walk(d)

    @staticmethod
    def mask_json_rows(
        rows: List[Dict[str, Any]],
        name_fields: Optional[List[str]] = None,
    ) -> Tuple[str, Dict[str, str]]:
        """把表格行列表序列化为 JSON 字符串并整体脱敏，供整表送 LLM。"""
        masked_rows, mapping = PIIGateway.mask_dict(rows, name_fields)
        return json.dumps(masked_rows, ensure_ascii=False), mapping
