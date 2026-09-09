# -*- coding: utf-8 -*-
"""01_clean.py —— 把原文 txt 清洗并切成「句/引号块」级 jsonl。

切分单位是"句块"而非段落：一条闭合对话引号（“…”/「…」）整体成一块，
引号外的文本按句界 [。！？…] 切开。这样龙蛇演义的规整段与佛本是道的
千字长段都能处理，且对白不会被句号切断。
"""
import io
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "work" / "clean"
WORK.mkdir(parents=True, exist_ok=True)

DUPHUAN = Path("D:/DPH/玄幻语料")
CWNS = Path("D:/ai-tone-refs/Chinese-WebNovel-Skill")

SENT_BOUND = re.compile(r"[。！？!?…]+")
QUOTE_RE = re.compile(r"[“「][^”」]*[”」]")
JUNK = re.compile(
    r"^(?:[=—\-*·\s.。]{4,}|第[0-9一二三四五六七八九十百千]+[章卷]目录.*)$"
    r"|(?:www\.|http|@|qq群|Q群|书友群|加入我们|更多章节|小说中转|请收藏|求(?:收藏|票|订阅)|未完待续)"
)
CHAPTER_PAT = [
    re.compile(r"^正文\s*第[0-9一二三四五六七八九十百千]+[章卷回集篇]"),  # 龙蛇
    re.compile(r"^第[0-9一二三四五六七八九十百千]+[章卷回集篇]"),          # 佛本/通用
]


def _split_plain(text):
    out = []
    for s in SENT_BOUND.split(text):
        s = s.strip().strip("，,、；;：: \"' ")
        if len(s) >= 4:
            out.append(s)
    return out


def split_line(text):
    """一行 -> 若干块：引号块整体保留，引号外按句界切。"""
    blocks = []
    pos = 0
    for m in QUOTE_RE.finditer(text):
        plain = text[pos:m.start()]
        blocks.extend(_split_plain(plain))
        q = m.group().strip()
        if len(q) >= 4:
            blocks.append(q)
        pos = m.end()
    blocks.extend(_split_plain(text[pos:]))
    return blocks


def unbalanced(line):
    o = line.count("“") + line.count("「")
    c = line.count("”") + line.count("」")
    return o != c


def clean_xuanhuan(path, book):
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("utf-16-le", errors="ignore")
    out = []
    lines = text.splitlines()
    in_body = False
    cur_ch = ""
    unb = 0
    for i, ln in enumerate(lines, 1):
        t = ln.replace("\u3000", " ").strip()
        if not in_body:
            if any(p.match(t) for p in CHAPTER_PAT):
                in_body = True
            else:
                continue
        if any(p.match(t) for p in CHAPTER_PAT):
            cur_ch = t
            continue
        if JUNK.search(t) or len(t) < 4:
            continue
        if unbalanced(t):
            unb += 1
        for k, b in enumerate(split_line(t)):
            out.append({"book": book, "kind": "xuanhuan", "title": "", "chapter": cur_ch,
                        "line": i, "blk": k, "text": b})
    return out, unb


def clean_short(paths):
    out = []
    for p in paths:
        text = p.read_text(encoding="utf-8-sig", errors="ignore")
        lines = text.splitlines()
        if not lines:
            continue
        title = lines[0].strip()
        title = re.split(r"[;；]", title)[0]
        for i, ln in enumerate(lines[1:], 2):
            t = ln.strip()
            if not t or re.fullmatch(r"\d+[.、]?", t) or len(t) < 3:
                continue
            if unbalanced(t):
                pass
            for k, b in enumerate(split_line(t)):
                out.append({"book": p.stem, "kind": "short", "title": title, "chapter": "",
                            "line": i, "blk": k, "text": b})
    return out


def main():
    sources = []
    unb_total = 0
    for slug, fn in [("longshe", "027.龙蛇演义.txt"), ("foben", "029.佛本是道.txt")]:
        rows, unb = clean_xuanhuan(DUPHUAN / fn, slug)
        sources.append((slug, rows))
        unb_total += unb
        print(f"[玄幻] {fn}: 正文块 {len(rows)}，未配对引号行 {unb}")

    short_files = sorted(CWNS.glob("data/articles/*.txt"))[:30]
    rows = clean_short(short_files)
    sources.append(("short30", rows))
    print(f"[短篇] 前 {len(short_files)} 篇: 块 {len(rows)}")

    for slug, rows in sources:
        with io.open(WORK / f"{slug}.jsonl", "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("已写入", WORK)
    print("未配对引号行总计", unb_total)


if __name__ == "__main__":
    main()
