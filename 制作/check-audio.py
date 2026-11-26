"""核对听书版与底稿：数字、人名是否丢失，是否还有不适合朗读的符号。

用法：python 制作/check-audio.py [文件名片段 ...]
不给参数则检查 听书版/ 下所有已改写的章节。
退出码 0 = 全部通过；1 = 有问题（逐条列出，并说明怎样修）。
"""
import collections
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
BASE = ROOT / "听书版" / "底稿"
OUT = ROOT / "听书版"
INDEX = ROOT / "书稿" / "附录B-人物与机构索引.md"

# 朗读时会被念出来或打断理解的符号
BAD = {
    "（": "全角括号", "）": "全角括号", "(": "括号", ")": "括号",
    "→": "箭头", "—": "破折号", "…": "省略号", "|": "表格竖线",
    "[^": "注释标记", "http": "网址", "**": "加粗记号", "/": "斜杠",
}
VISUAL = ["如下表", "见下表", "见图", "图中", "注释", "见附录", "上文", "本节"]


def names() -> set[str]:
    out = set()
    if not INDEX.exists():
        return out
    for line in INDEX.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|") or "---" in line:
            continue
        cell = line.split("|")[1]
        cell = re.sub(r"（[^）]*）", "", cell)
        for n in re.split(r"[、；，,\s]+", cell):
            if 2 <= len(n) <= 4 and re.fullmatch(r"[一-鿿]+", n):
                if n not in ("人物", "机构"):
                    out.add(n)
    return out


def nums(text: str, keep_meta: bool = False) -> collections.Counter:
    # 去掉版本号（v0.2、v1.1）和题号（行首“1.”），只比较作为事实的数字；一位数不比较
    text = re.sub(r"v\d+(\.\d+)*", "", text)
    text = re.sub(r"^\s*\d+[.、]", "", text, flags=re.M)
    text = re.sub(r"^#.*$", "", text, flags=re.M)  # 标题行
    if not keep_meta:
        text = re.sub(r"^>.*$", "", text, flags=re.M)  # 元信息行
    text = re.sub(r"注\d+(—\d+)?", "", text)  # 注释编号
    return collections.Counter(n for n in re.findall(r"\d+", text) if len(n) > 1)


def check(base_f: pathlib.Path, out_f: pathlib.Path, people: set[str]) -> list[str]:
    b = base_f.read_text(encoding="utf-8")
    o = out_f.read_text(encoding="utf-8")
    probs = []
    ratio = len(o) / max(len(b), 1)
    if ratio < 0.8:
        probs.append(f"篇幅只有底稿的 {ratio:.0%}，可能删掉了内容：对照底稿补回被合并或省略的段落")
    nb, no = nums(b), nums(o)
    missing = sorted({n for n in nb if no[n] == 0}, key=lambda x: (len(x), x))
    if missing:
        probs.append("底稿中的数字在改写稿里完全没有出现：" + "、".join(missing[:40])
                     + " —— 找到底稿相应句子，确认日期或数量没有被删掉或改成汉字")
    nb_all = nums(b, keep_meta=True)  # 元信息里的日期允许出现在改写稿里
    extra = sorted({n for n in no if nb_all[n] == 0}, key=lambda x: (len(x), x))
    if extra:
        probs.append("改写稿出现了底稿没有的数字：" + "、".join(extra[:40])
                     + " —— 核对是否新增了事实，或把汉字数目改成了数字")
    lost = sorted(n for n in people if n in b and n not in o)
    if lost:
        probs.append("底稿中出现的人名在改写稿里消失了：" + "、".join(lost) + " —— 补回相关句子")
    for sym, what in BAD.items():
        c = o.count(sym)
        if c:
            probs.append(f"还有 {c} 处{what}「{sym}」 —— 改成口语句子")
    for w in VISUAL:
        if w in o:
            probs.append(f"出现视觉指称「{w}」 —— 改成“前面讲过”之类的说法")
    if re.search(r"^\s*[-*]\s", o, re.M) or re.search(r"^\s*\d+[.、]\s", o, re.M):
        probs.append("还有列表条目 —— 改成连贯句子")
    if re.search(r"v1\.[0-9]", o):
        probs.append("还在念版本号 v1.x —— 改成自然叙述")
    return probs


def main(argv: list[str]) -> int:
    people = names()
    files = sorted(p for p in OUT.glob("*.md") if (BASE / p.name).exists())
    if argv:
        files = [f for f in files if any(a in f.name for a in argv)]
    bad = 0
    for f in files:
        probs = check(BASE / f.name, f, people)
        status = "通过" if not probs else f"{len(probs)} 个问题"
        print(f"== {f.name}：{status}")
        for p in probs:
            print("   - " + p)
        bad += bool(probs)
    print(f"共 {len(files)} 个文件，{bad} 个有问题")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
