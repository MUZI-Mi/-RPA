"""验证 _with_retry：空 steps 自动重试、仍空给友好提示、其它错误不重试。"""
import asyncio
from llm_client import LLMError
import nl_parser


async def main():
    P = nl_parser.NLParser

    # 1) 首次空 steps 报错 → 重试后成功
    calls = []

    async def g1():
        calls.append(1)
        if len(calls) == 1:
            raise LLMError("方案未通过校验：规则校验失败: [] should be non-empty")
        return {"steps": [{"step_id": 1}]}

    r1 = await P._with_retry(g1)
    assert r1["steps"] == [{"step_id": 1}] and len(calls) == 2, f"case1 fail {calls}"
    print("case1 ok: 空结果自动重试成功")

    # 2) 一直空 → 抛友好错误
    async def g2():
        raise LLMError("方案未通过校验：规则校验失败: [] should be non-empty")

    try:
        await P._with_retry(g2)
        print("case2 FAIL: 未抛错")
    except LLMError as e:
        assert "换个说法" in str(e), f"case2 msg={e}"
        print("case2 ok: 仍空时给出友好提示")

    # 3) 其它校验错误 → 不重试、直接抛原始错误
    n = [0]

    async def g3():
        n[0] += 1
        raise LLMError("方案未通过校验：规则校验失败: xxx is not of type 'string'")

    try:
        await P._with_retry(g3)
        print("case3 FAIL: 未抛错")
    except LLMError as e:
        assert n[0] == 1, f"case3 calls={n[0]}"
        assert "string" in str(e), f"case3 msg={e}"
        print("case3 ok: 非空 steps 错误不重试、原样抛出")

    print("ALL PASS")


asyncio.run(main())
