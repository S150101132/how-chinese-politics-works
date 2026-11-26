"""从书稿生成听书版底稿：去掉注释、来源链接、图和编辑元信息。

用法：python 制作/make-audio-base.py
输出：听书版/底稿/*.md（表格保留，留给改写步骤转成口语）。
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "书稿"
OUT = ROOT / "听书版" / "底稿"
# 听书版不收：人物索引、延伸阅读书目、记录表、版本说明
SKIP = ("附录B", "附录D", "附录E", "附录F")


def strip(text: str) -> str:
    lines = text.splitlines()
    out = []
    in_code = False
    for i, line in enumerate(lines):
        if line.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        if re.match(r"^\[\^[^\]]+\]:", line):  # 注释定义
            continue
        if re.match(r"^\s{2,}\S", line) and out and out[-1] == "":
            # 注释定义的续行（缩进）——上一行若已被删，这里也删
            pass
        if re.match(r"^#{1,6}\s*注释\s*$", line):
            continue
        if line.strip() == "---":
            continue
        if line.startswith("!["):
            continue
        # 标题下方的版本、日期说明
        if i < 8 and (line.startswith("*《") or line.startswith("*修订") or line.startswith("*资料")
                      or line.startswith("*成稿") or line.startswith("版本：")):
            continue
        out.append(line)
    s = "\n".join(out)
    s = re.sub(r"\[\^[^\]]+\]", "", s)                      # 注释引用
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", s)               # 图片
    s = re.sub(r"\[([^\]]+)\]\((?:https?:|/|\.|#)[^)]*\)", r"\1", s)  # 链接留文字
    s = re.sub(r"\*\*([^*]+)\*\*", r"\1", s)                  # 加粗
    s = re.sub(r"(?<![*\w])\*([^*\n]+)\*(?![*\w])", r"\1", s)  # 斜体
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip() + "\n"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    n = 0
    for f in sorted(SRC.glob("*.md")):
        if f.name.startswith(SKIP):
            continue
        body = strip(f.read_text(encoding="utf-8"))
        if "[^" in body or "http" in body:
            print(f"警告：{f.name} 仍含注释标记或网址，请检查 strip 规则", file=sys.stderr)
        (OUT / f.name).write_text(body, encoding="utf-8")
        n += 1
    print(f"已生成 {n} 个底稿 -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
