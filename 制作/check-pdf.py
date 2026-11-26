"""检查交付 PDF 的字体是否一致、校验值是否与 SHA256SUMS 相符。

用法：python 制作/check-pdf.py   （需要 pymupdf）
退出码 0 = 通过；1 = 有问题（逐条说明怎样修）。
"""
import hashlib
import pathlib
import sys

import pymupdf

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "交付"
ALLOWED = ("Noto", "Symbol")  # Symbol 只用于列表圆点


def main() -> int:
    probs = []
    doc = pymupdf.open(OUT / "中国政治是怎么运转的.pdf")
    stray = {}
    for i, page in enumerate(doc):
        for b in page.get_text("dict")["blocks"]:
            for line in b.get("lines", []):
                for s in line["spans"]:
                    if not s["font"].startswith(ALLOWED):
                        stray.setdefault(s["font"], (i + 1, s["text"][:20]))
    for font, (pg, text) in stray.items():
        probs.append(f"第{pg}页「{text}」用了 {font}：样式里还有主题字体属性，或 BOOK_SANS/BOOK_SERIF "
                     "与本机字体家族名不符（Windows 是 Noto Sans SC / Noto Serif SC），改好后重新导出")
    sums = OUT / "SHA256SUMS"
    for line in sums.read_text(encoding="utf-8").splitlines():
        digest, name = line.split(maxsplit=1)
        actual = hashlib.sha256((OUT / name).read_bytes()).hexdigest()
        if actual != digest:
            probs.append(f"{name} 与 SHA256SUMS 不符：重新导出后要重算校验值")
    print(f"PDF {len(doc)} 页")
    for p in probs:
        print(" - " + p)
    print("通过" if not probs else f"{len(probs)} 个问题")
    return 1 if probs else 0


if __name__ == "__main__":
    sys.exit(main())
