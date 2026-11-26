"""把听书版各章合并成一本：Markdown、纯文本（给朗读软件）、Word。

用法：python 制作/export-audio.py
输出：听书版/中国政治是怎么运转的-听书版.{md,txt,docx}
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DIR = ROOT / "听书版"
NAME = "中国政治是怎么运转的-听书版"
TITLE = "中国政治是怎么运转的"
SUB = "听书版"
NOTE = ("这是专门为听书整理的版本，去掉了注释、来源、表格和图。"
        "书里的现实情况以2026年9月29日为准，少数地方补充了到2026年11月26日的新消息。"
        "需要查出处，请看带注释的原版。")


def order(p: pathlib.Path):
    n = p.name
    if n.startswith("导读"):
        return (0, n)
    if n.startswith("第"):
        return (1, n)
    return (2, n)


def main() -> int:
    parts = sorted((p for p in DIR.glob("*.md")
                    if not p.name.startswith(NAME) and p.name != "README.md"), key=order)
    expected = len(list((DIR / "底稿").glob("*.md")))
    if len(parts) != expected:
        print(f"错误：听书版有 {len(parts)} 个章节文件，底稿有 {expected} 个；先补齐缺的章节再导出",
              file=sys.stderr)
        return 1
    md = f"# {TITLE}\n\n{SUB}\n\n{NOTE}\n\n" + "\n\n".join(
        p.read_text(encoding="utf-8").strip() for p in parts) + "\n"
    (DIR / f"{NAME}.md").write_text(md, encoding="utf-8")

    # 纯文本：去掉 # 记号，标题前后空行，方便朗读软件分段停顿
    txt = re.sub(r"^#{1,6}\s*", "", md, flags=re.M)
    (DIR / f"{NAME}.txt").write_text(txt, encoding="utf-8-sig")

    from docx import Document
    from docx.oxml.ns import qn
    from docx.shared import Pt

    doc = Document()
    st = doc.styles["Normal"]
    st.font.name = "宋体"
    st.font.size = Pt(12)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
    first = True
    for line in md.splitlines():
        if not line.strip():
            continue
        m = re.match(r"^(#{1,6})\s*(.*)", line)
        if m:
            level = len(m.group(1))
            if level == 1 and not first:
                doc.add_page_break()
            h = doc.add_heading(m.group(2), level=min(level, 3))
            for r in h.runs:
                r.font.name = "黑体"
                r._element.rPr.rFonts.set(qn("w:eastAsia"), "黑体")
            first = False
        else:
            doc.add_paragraph(line)
    doc.save(DIR / f"{NAME}.docx")
    print(f"已导出 {len(parts)} 个部分，约 {len(txt):,} 字 -> {DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
