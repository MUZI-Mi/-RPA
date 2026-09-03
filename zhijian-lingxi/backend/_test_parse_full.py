"""完整 parse 链路测试：连续调用，确认是否偶发空 / 还是 _finalize 有问题。"""
import asyncio
from nl_parser import NLParser
from llm_client import LLMError


async def main():
    texts = [
        "打开哔哩哔哩点击热门区域的第一条视频",
        "打开哔哩哔哩，点击热门标签下的第一条视频",
    ]
    for t in texts:
        try:
            r = await NLParser.parse(t)
            print("OK:", t, "steps=", len(r["steps"]))
            for s in r["steps"]:
                print("   ", s["step_id"], s["action"].get("type"), s["action"].get("selector") or s["action"].get("url") or s["action"].get("text"))
        except LLMError as e:
            print("LLMERR:", t, "->", e)
        except Exception as e:
            print("ERR:", t, "->", type(e).__name__, e)


asyncio.run(main())
