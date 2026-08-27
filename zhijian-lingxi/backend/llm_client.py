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
        key = _api_key()
        if not key:
            raise LLMError("未配置 API Key，请在设置页选择模型来源并填入对应平台的免费 Key")
        model = model or get_setting("vl_model") or QWEN_VL_MODEL
        b64 = base64.b64encode(image_bytes).decode()
        prompt = (
            "你是网页元素视觉定位助手。请根据操作意图，在截图中找到目标元素的中心坐标，"
            "并输出 JSON。注意坐标使用相对于整张图的像素比例（0~1 浮点数）。\n"
            f"操作意图：{intent}\n"
            '输出格式严格为 JSON：{"x": 0.5, "y": 0.3, "confidence": 0.9, "reason": "..."}'
        )
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