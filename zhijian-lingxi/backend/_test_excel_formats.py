"""Excel 读取兼容性单元测试（_test_excel_formats.py）

覆盖补丁：
- 老式 .xls 用 xlrd 读取（openpyxl 不支持 .xls，此前会直接报错）
- .xlsx 用 openpyxl 读取（回归）
- 无表头时按 A/B/C 列名、空行跳过

运行：在 backend 目录执行 `python _test_excel_formats.py`
"""
import sys
import tempfile
from pathlib import Path

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


def make_xls(path: Path, sheet_name=None):
    """用 xlwt 生成老式 .xls 文件（含表头 + 两行数据 + 一行空行）。"""
    import xlwt

    wb = xlwt.Workbook()
    ws = wb.add_sheet(sheet_name or "Sheet1")
    for r, row in enumerate([["姓名", "身份证号", "金额"],
                             ["张三", "110101199003078888", "5000"],
                             ["李四", "110101199103078889", "3200"],
                             ["", "", ""]]):
        for c, v in enumerate(row):
            ws.write(r, c, v)
    wb.save(str(path))


def make_xlsx(path: Path):
    """用 openpyxl 生成 .xlsx 文件。"""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    for row in [["姓名", "金额"], ["张三", "5000"], ["李四", "3200"]]:
        ws.append(row)
    wb.save(str(path))


def test_read_xls():
    print("\n== 老式 .xls 读取（补丁）==")
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "名单.xls"
        make_xls(p)
        rows = TaskExecutor()._action_read_excel({"file_path": str(p)})
        check("正确读取 2 行数据", len(rows) == 2, str(rows))
        check("行1 身份证号正确", rows[0]["身份证号"] == "110101199003078888", str(rows[0]))
        check("行2 金额为数字", rows[1]["金额"] == "3200" or rows[1]["金额"] == 3200, str(rows[1]))
        # 指定工作表
        rows2 = TaskExecutor()._action_read_excel({"file_path": str(p), "sheet_name": "Sheet1"})
        check("指定工作表读取", len(rows2) == 2, str(rows2))


def test_read_xls_no_header():
    print("\n== .xls 无表头 → A/B/C 列名 ==")
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "nohdr.xls"
        make_xls(p)
        rows = TaskExecutor()._action_read_excel({"file_path": str(p), "has_header": False})
        check("表头行作为数据保留", len(rows) == 3, str(rows))
        check("列名按 A/B/C", rows[0] == {"A": "姓名", "B": "身份证号", "C": "金额"}, str(rows[0]))


def test_read_xlsx_regression():
    print("\n== .xlsx 回归 ==")
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "名单.xlsx"
        make_xlsx(p)
        rows = TaskExecutor()._action_read_excel({"file_path": str(p)})
        check(".xlsx 正常读取", rows == [{"姓名": "张三", "金额": "5000"}, {"姓名": "李四", "金额": "3200"}], str(rows))


def test_missing_file():
    print("\n== 文件不存在报错 ==")
    with tempfile.TemporaryDirectory() as td:
        try:
            TaskExecutor()._action_read_excel({"file_path": str(Path(td) / "x.xls")})
            check("文件不存在应抛错", False)
        except FileNotFoundError:
            check("文件不存在报错", True)


def main():
    test_read_xls()
    test_read_xls_no_header()
    test_read_xlsx_regression()
    test_missing_file()

    print("\n===== 结果: %d 通过, %d 失败 =====" % (PASS, FAIL))
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
