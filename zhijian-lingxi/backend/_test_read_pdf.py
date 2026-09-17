"""read_pdf 动作单元测试（_test_read_pdf.py）

覆盖新增的 PDF/扫描件解析能力：
- text 模式：pdfplumber 抽每页文字 → {"页码": n, "内容": "..."}
- table 模式：抽取表格并按表头生成行
- auto 模式：文本型 PDF 直接抽文字（不调 LLM）；扫描件（无文字层）自动转 OCR
- ocr 模式：强制走多模态 OCR（渲染成图）
- pdf_page 只解析指定页、非法参数/缺失文件的报错

运行：在 backend 目录执行 `python _test_read_pdf.py`
（OCR 路径会 mock LLMClient.ocr，不实际调用模型）
"""
import asyncio
import sys
import tempfile
from pathlib import Path

import executor
from executor import TaskExecutor

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


# --- 造测试 PDF -------------------------------------------------------------
def make_text_pdf(path: Path):
    """报告：含标题、正文、表格，共两页。使用 CID 中文字体，保证可被抽取。"""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    doc = SimpleDocTemplate(str(path), pagesize=A4)
    styles = getSampleStyleSheet()
    styles["Title"].fontName = "STSong-Light"
    styles["Normal"].fontName = "STSong-Light"
    t = Table([["姓名", "金额"], ["张三", "5000"], ["李四", "3200"]], colWidths=[120, 120])
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
    ]))
    story = [
        Paragraph("月度材料汇总", styles["Title"]),
        Spacer(1, 12),
        Paragraph("本季度共完成材料报送 3 份，全部通过审核。", styles["Normal"]),
        Spacer(1, 12),
        t,
        PageBreak(),
        Paragraph("补充说明：张三名下金额较大，需复核。", styles["Normal"]),
    ]
    doc.build(story)


def make_scanned_pdf(path: Path):
    """纯图片扫描件 PDF：无文字层，pdfplumber 抽不出文字。"""
    import io

    import pymupdf as fitz
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (400, 300), "white")
    d = ImageDraw.Draw(img)
    d.rectangle([30, 30, 370, 120], outline="black", width=3)
    d.text((50, 60), "SCANNED DOC", fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    doc = fitz.open()
    page = doc.new_page()
    page.insert_image(fitz.Rect(0, 0, 400, 300), stream=buf.getvalue())
    doc.save(str(path))
    doc.close()


# --- OCR mock ---------------------------------------------------------------
_OCR_CALLS = []


async def _fake_ocr(image_bytes, model=None, timeout=25):
    _OCR_CALLS.append(len(image_bytes))
    return "扫描件识别结果：会议纪要 2026-09-01"


async def _run(action, expected_error=None):
    """调用 _action_read_pdf，返回 rows 或抛出的异常。"""
    ex = TaskExecutor()
    try:
        return await ex._action_read_pdf(action)
    except Exception as e:  # noqa: BLE001
        if expected_error is None:
            raise
        return e


def test_text_mode():
    print("\n== text 模式 ==")
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "doc.pdf"
        make_text_pdf(p)
        rows = asyncio.run(_run({"file_path": str(p), "pdf_extract": "text"}))
        check("每页一行（页码+内容）", len(rows) == 2, str(rows))
        check("第1页含标题文字", "月度材料汇总" in rows[0]["内容"], str(rows[0]))
        check("第2页含补充说明", "补充说明" in rows[1]["内容"], str(rows[1]))
        check("页码标注正确", rows[0]["页码"] == 1 and rows[1]["页码"] == 2, str(rows))


def test_auto_no_ocr_for_text_pdf():
    print("\n== auto 模式：文本型 PDF 不调 OCR（有表抽表，无表抽文字）==")
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "doc.pdf"
        make_text_pdf(p)
        _OCR_CALLS.clear()
        old = executor.LLMClient.ocr

        async def boom(*a, **k):  # 若被调用则测试失败
            raise AssertionError("文本型 PDF 不应触发 OCR")

        executor.LLMClient.ocr = staticmethod(boom)
        try:
            rows = asyncio.run(_run({"file_path": str(p)}))  # 默认 auto
        finally:
            executor.LLMClient.ocr = old
        check("第1页表格被抽取", rows[:2] == [{"姓名": "张三", "金额": "5000"}, {"姓名": "李四", "金额": "3200"}], str(rows))
        check("第2页文字被抽取", len(rows) == 3 and "补充说明" in rows[2]["内容"], str(rows))
        check("未调用 OCR", _OCR_CALLS == [], str(_OCR_CALLS))


def test_table_mode():
    print("\n== table 模式 ==")
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "doc.pdf"
        make_text_pdf(p)
        rows = asyncio.run(_run({"file_path": str(p), "pdf_extract": "table"}))
        check("只抽表格（无表页跳过）", len(rows) == 2, str(rows))
        check("行1 姓名/金额正确", rows[0] == {"姓名": "张三", "金额": "5000"}, str(rows[0]))
        check("行2 姓名/金额正确", rows[1] == {"姓名": "李四", "金额": "3200"}, str(rows[1]))


def test_pdf_page():
    print("\n== pdf_page 只解析指定页 ==")
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "doc.pdf"
        make_text_pdf(p)
        rows = asyncio.run(_run({"file_path": str(p), "pdf_extract": "text", "pdf_page": 2}))
        check("只返回第2页", len(rows) == 1 and rows[0]["页码"] == 2, str(rows))


def test_scanned_auto_ocr():
    print("\n== auto 模式：扫描件自动转 OCR ==")
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "scan.pdf"
        make_scanned_pdf(p)
        _OCR_CALLS.clear()
        old = executor.LLMClient.ocr
        executor.LLMClient.ocr = staticmethod(_fake_ocr)
        try:
            rows = asyncio.run(_run({"file_path": str(p)}))
        finally:
            executor.LLMClient.ocr = old
        check("扫描件走 OCR 得到内容", rows and "会议纪要" in rows[0]["内容"], str(rows))
        check("OCR 被调用", len(_OCR_CALLS) == 1, str(_OCR_CALLS))
        check("页码标注正确", rows[0]["页码"] == 1, str(rows))


def test_ocr_mode_forced():
    print("\n== ocr 模式：即使有文字层也强制 OCR ==")
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "doc.pdf"
        make_text_pdf(p)
        _OCR_CALLS.clear()
        old = executor.LLMClient.ocr
        executor.LLMClient.ocr = staticmethod(_fake_ocr)
        try:
            rows = asyncio.run(_run({"file_path": str(p), "pdf_extract": "ocr"}))
        finally:
            executor.LLMClient.ocr = old
        check("强制 OCR 返回识别内容", rows and "会议纪要" in rows[0]["内容"], str(rows))
        check("每页都 OCR", len(_OCR_CALLS) == 2, str(_OCR_CALLS))


def test_errors():
    print("\n== 参数与文件报错 ==")
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "doc.pdf"
        make_text_pdf(p)
        e = asyncio.run(_run({"file_path": str(p), "pdf_extract": "badmode"}, expected_error=ValueError))
        check("非法模式报错", isinstance(e, ValueError), repr(e))
        e = asyncio.run(_run({"file_path": str(p), "pdf_page": 99}, expected_error=ValueError))
        check("页码越界报错", isinstance(e, ValueError), repr(e))
        e = asyncio.run(_run({"file_path": str(Path(td) / "not_exist.pdf")}, expected_error=FileNotFoundError))
        check("文件不存在报错", isinstance(e, FileNotFoundError), repr(e))


def main():
    test_text_mode()
    test_auto_no_ocr_for_text_pdf()
    test_table_mode()
    test_pdf_page()
    test_scanned_auto_ocr()
    test_ocr_mode_forced()
    test_errors()

    print("\n===== 结果: %d 通过, %d 失败 =====" % (PASS, FAIL))
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
