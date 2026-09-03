"""通义千问 LLM 客户端

封装对通义千问（兼容 OpenAI 协议端点）的调用，
供自然语言解析、DOM 语义分析、视觉定位复用。
"""

from __future__ import annotations

import base64
import json
from typing import Any, Dict, List, Optional

import httpx

from config import (
    DASHSCOPE_API_KEY,
    DASHSCOPE_BASE_URL,
    QWEN_TEXT_MODEL,
    QWEN_VL_MODEL,
)
from database import get_setting


def _api_key() -> str:
    return get_setting("api_key") or DASHSCOPE_API_KEY


def _base_url() -> str:
    return get_setting("base_url") or DASHSCOPE_BASE_URL


class LLMError(Exception):
    pass


class LLMClient:
    """统一 LLM 调用入口。"""

    @staticmethod
    async def chat(
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        temperature: float = 0.3,
        timeout: float = 90,
        response_format: Optional[str] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """文本对话，返回模型输出的字符串内容。"""
        key = _api_key()
        if not key:
            raise LLMError("未配置 API Key，请在设置页选择模型来源并填入对应平台的免费 Key")
        model = model or get_setting("model") or QWEN_TEXT_MODEL
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        if response_format == "json_object":
            payload["response_format"] = {"type": "json_object"}
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{_base_url()}/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json=payload,
            )
        if resp.status_code != 200:
            raise LLMError(f"LLM 调用失败 ({resp.status_code}): {resp.text[:300]}")
        data = resp.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise LLMError(f"LLM 响应格式异常: {data}") from e

    @staticmethod
    async def chat_json(
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        temperature: float = 0.1,
        timeout: float = 90,
    ) -> Dict[str, Any]:
        """文本对话并解析为 JSON。"""
        content = await LLMClient.chat(
            messages, model=model, temperature=temperature, timeout=timeout,
            response_format="json_object", max_tokens=2048
        )
        return _extract_json(content)

    @staticmethod
    async def vision(
        intent: str,
        image_bytes: bytes,
        model: Optional[str] = None,
        timeout: float = 15,
    ) -> Dict[str, Any]:
        """多模态视觉定位：发送截图 + 意图，返回坐标与置信度。"""
        model = model or get_setting("vl_model") or QWEN_VL_MODEL
        prompt = (
            "你是网页元素视觉定位助手。请根据操作意图，在截图中找到目标元素的中心坐标，"
            "并输出 JSON。注意坐标使用相对于整张图的像素比例（0~1 浮点数）。\n"
            f"操作意图：{intent}\n"
            '输出格式严格为 JSON：{"x": 0.5, "y": 0.3, "confidence": 0.9, "reason": "..."}'
        )
        return await LLMClient._vision_ask(prompt, image_bytes, model, timeout)

    @staticmethod
    async def vision_ask(
        prompt: str,
        image_bytes: bytes,
        model: Optional[str] = None,
        timeout: float = 15,
    ) -> Dict[str, Any]:
        """通用视觉问答：发送自定义问题 + 截图，返回 JSON（用于元素复核等）。"""
        model = model or get_setting("vl_model") or QWEN_VL_MODEL
        return await LLMClient._vision_ask(prompt, image_bytes, model, timeout)

    @staticmethod
    async def ocr(image_bytes: bytes, model: Optional[str] = None,
                  timeout: float = 25) -> str:
        """OCR 读图：用多模态模型读出截图/图片里的全部文字。

        用于网页截图、扫描件、PDF 渲染页等无法直接提取的图片内容。
        """
        model = model or get_setting("vl_model") or QWEN_VL_MODEL
        key = _api_key()
        if not key:
            raise LLMError("未配置 API Key，无法使用 OCR 读图，请先在设置页配置")
        b64 = base64.b64encode(image_bytes).decode()
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "请识别这张图片里的全部文字，按原样逐行输出，只输出识别出的文字内容，不要任何解释。"},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                ],
            }
        ]
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{_base_url()}/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={"model": model, "messages": messages, "temperature": 0.1},
            )
        if resp.status_code != 200:
            raise LLMError(f"OCR 调用失败 ({resp.status_code}): {resp.text[:300]}")
        data = resp.json()
        try:
            return (data["choices"][0]["message"]["content"] or "").strip()
        except (KeyError, IndexError) as e:
            raise LLMError("OCR 响应格式异常") from e

    @staticmethod
    async def extract_fields(
        text: str,
        fields: List[str],
        model: Optional[str] = None,
        timeout: float = 40,
    ) -> Dict[str, Any]:
        """结构化 NLP 抽取：把一段文字按指定字段抽成 JSON。

        fields 为要抽取的字段名列表（如 ["标题","日期","金额"]）。
        返回 {字段名: 值}；模型输出不合法/缺少字段时兜底补齐空字符串。
        """
        model = model or get_setting("model") or QWEN_TEXT_MODEL
        field_list = "、".join(fields) if fields else "关键信息"
        example = (
            "{" + ", ".join('"%s": "示例值"' % f for f in fields[:3]) + "}"
            if fields else '{"关键信息": "示例值"}'
        )
        prompt = (
            "你是信息抽取助手。请从下面的文字中抽取指定的字段，只输出 JSON 对象，不要任何解释。\n"
            f"要抽取的字段（字段之间用、分隔，输出时键名必须与字段名逐字一致）：{field_list}\n"
            f"输出示例（键名严格等于字段名，不要拆分、不要加空格或标点）：{example}\n"
            "要求：\n"
            "1. 严格输出 JSON 对象，键用字段名原样，值为抽取到的文本；抽不到就填空字符串\n"
            "2. 字段名保持用户给定的名称不变，禁止拆成单个字\n"
            "3. 只输出 JSON，不要任何前后缀文字\n\n"
            f"待抽取的文字：\n{text[:8000]}"
        )
        messages = [
            {"role": "system", "content": "你是一个严谨的信息抽取助手，只输出 JSON。"},
            {"role": "user", "content": prompt},
        ]
        content = await LLMClient.chat(
            messages, model=model, temperature=0.1, timeout=timeout,
            response_format="json_object", max_tokens=2048,
        )
        data = _extract_json(content)
        if not isinstance(data, dict):
            data = {}
        # 键名与字段不符（例如模型把键拆成单字）时重试一次，用更严格的示例
        matched = sum(1 for f in fields if f in data)
        if fields and matched < max(1, len(fields) // 2):
            retry_prompt = (
                "上一步输出不符合要求。请严格按下述键名输出 JSON 对象，键名不能拆分：\n"
                + "".join(f"{i+1}. \"{f}\"（值为从文字中抽取的内容，抽不到填空字符串）\n" for i, f in enumerate(fields))
                + "只输出 JSON，不要任何解释。\n\n"
                f"待抽取的文字：\n{text[:8000]}"
            )
            retry_messages = [
                {"role": "system", "content": "你是一个严谨的信息抽取助手，只输出键名完全一致的 JSON。"},
                {"role": "user", "content": retry_prompt},
            ]
            content2 = await LLMClient.chat(
                retry_messages, model=model, temperature=0.0, timeout=timeout,
                response_format="json_object", max_tokens=2048,
            )
            data2 = _extract_json(content2)
            if isinstance(data2, dict):
                data = data2
        # 兜底：模型未按字段名输出时，补全缺失字段为空字符串
        out: Dict[str, Any] = {}
        for f in fields:
            out[f] = data.get(f) or data.get(f.replace("：", "")) or ""
        return out

    @staticmethod
    async def rows_from_text(
        text: str,
        columns: List[str],
        model: Optional[str] = None,
        timeout: float = 60,
    ) -> List[Dict[str, Any]]:
        """把一段文字（OCR 结果等）按指定列整理成 JSON 数组（表格）。

        columns 为目标列名列表。模型输出 {"rows": [...]}；占位符 @MASK_n@ 必须原样保留。
        """
        model = model or get_setting("model") or QWEN_TEXT_MODEL
        col_str = "、".join(columns) if columns else "识别到的字段"
        prompt = (
            "你是表格整理助手。请从下面的文字中提取数据，整理成对象数组。\n"
            f"字段：{col_str}\n"
            "要求：\n"
            "1. 严格输出 JSON 对象：{\"rows\": [每行一个对象，键为字段名]}\n"
            "2. 抽不到的字段填空字符串\n"
            "3. 遇到 '@MASK_n@' 这样的占位符必须逐字原样保留，禁止改动或删除\n"
            "4. 只输出 JSON，不要任何前后缀文字\n\n"
            f"文字内容：\n{text[:8000]}"
        )
        messages = [
            {"role": "system", "content": "你是严谨的表格数据整理助手，只输出 JSON。"},
            {"role": "user", "content": prompt},
        ]
        content = await LLMClient.chat(
            messages, model=model, temperature=0.1, timeout=timeout,
            response_format="json_object", max_tokens=2048,
        )
        data = _extract_json(content)
        if isinstance(data, dict) and isinstance(data.get("rows"), list):
            data = data["rows"]
        if not isinstance(data, list):
            data = [data] if isinstance(data, dict) else []
        out: List[Dict[str, Any]] = []
        for r in data:
            if isinstance(r, dict):
                out.append({c: (r.get(c) or "") for c in columns})
        return out

    @staticmethod
    async def summarize_rows(
        rows_json: str,
        model: Optional[str] = None,
        timeout: float = 90,
    ) -> Dict[str, Any]:
        """AI 语义总结 + 异常预警。输入（已脱敏的）行 JSON，返回：
        {"overall_summary": str, "rows": [{"index", "summary", "confidence", "compliance_issues", "anomaly"}]}
        低置信度/异常由调用方据此进入人工审核队列。
        """
        model = model or get_setting("model") or QWEN_TEXT_MODEL
        prompt = (
            "你是政务数据审核助手。下面是若干条数据的 JSON 数组，请逐条分析并输出总结与异常预警。\n"
            "要求：\n"
            "1. 严格输出 JSON 对象：{\"overall_summary\": \"整体摘要\", \"rows\": [...]}\n"
            "2. rows 中每个元素对应输入的一条："
            "{\"index\": 输入序号, \"summary\": \"本条一句话总结\", \"confidence\": 0~1 的数字, "
            "\"compliance_issues\": [\"异常问题，无则空数组\"], \"anomaly\": 布尔（是否需人工复核）}\n"
            "3. 数据中形如 '@MASK_1@' 的占位符代表已脱敏的敏感值："
            "总结里若需提及该值，请原样引用占位符本身，但严禁添加"
            "'存在占位符''已脱敏''@MASK_n@' 之类的解释性文字\n"
            "4. 只输出 JSON，不要任何前后缀文字\n\n"
            f"数据：\n{rows_json[:16000]}"
        )
        messages = [
            {"role": "system", "content": "你是严谨的政务数据审核助手，只输出 JSON。"},
            {"role": "user", "content": prompt},
        ]
        content = await LLMClient.chat(
            messages, model=model, temperature=0.1, timeout=timeout,
            response_format="json_object", max_tokens=3072,
        )
        data = _extract_json(content)
        if not isinstance(data, dict):
            data = {}
        data.setdefault("overall_summary", "")
        if not isinstance(data.get("rows"), list):
            data["rows"] = []
        return data

    @staticmethod
    async def _vision_ask(
        prompt: str,
        image_bytes: bytes,
        model: str,
        timeout: float = 15,
    ) -> Dict[str, Any]:
        """视觉模型调用底层实现。"""
        key = _api_key()
        if not key:
            raise LLMError("未配置 API Key，请在设置页选择模型来源并填入对应平台的免费 Key")
        b64 = base64.b64encode(image_bytes).decode()
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64}"},
                    },
                ],
            }
        ]
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{_base_url()}/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={"model": model, "messages": messages, "temperature": 0.1},
            )
        if resp.status_code != 200:
            raise LLMError(f"视觉定位调用失败 ({resp.status_code}): {resp.text[:300]}")
        data = resp.json()
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise LLMError("视觉定位响应格式异常") from e
        return _extract_json(content)


def _extract_json(content: str) -> Dict[str, Any]:
    """从模型输出中提取 JSON 对象。"""
    content = content.strip()
    # 去除可能的 ```json 包裹
    if content.startswith("```"):
        content = content.strip("`")
        if content.startswith("json"):
            content = content[4:]
    start, end = content.find("{"), content.rfind("}")
    if start == -1 or end == -1:
        raise LLMError(f"无法从模型输出中提取 JSON: {content[:200]}")
    try:
        return json.loads(content[start : end + 1])
    except json.JSONDecodeError as e:
        raise LLMError(f"JSON 解析失败: {content[:200]}") from e