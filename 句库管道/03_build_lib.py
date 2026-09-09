# -*- coding: utf-8 -*-
"""03_build_lib.py —— 把 work/selected/*.jsonl 审定条目落成句库成品。

输入每条（JSON）：
  dim   主维度：外貌/神态/情绪/动作/打斗/环境/心理
  tags  子标签（可选，用 | 分隔多个）
  text  收录文本（可含语境多行，\n 分隔）
  src   "book:line.blk"（book 为龙蛇演义 slug 等；回查 clean 索引补全书名/章节）
  note  ≤一句话：可迁移机制
输出：
  data/descriptions.jsonl/.csv  全条目（含 id/source/title/chapter）
  分维/<维名>.md               人读例句库
  README.md / _meta/corpus.json
"""
import csv
import io
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
CLEAN = ROOT / "work" / "clean"
SEL = ROOT / "work" / "selected"
DATA = ROOT / "data"
FEN = ROOT / "分维"

BOOK_NAME = {
    "longshe": "《龙蛇演义》", "foben": "《佛本是道》",
}
DIM_ORDER = ["情绪", "神态", "心理", "动作", "打斗", "环境", "外貌"]


def load_clean_index():
    """(book,line) -> (title, chapter)；短篇 chapter 存篇名于 title。"""
    idx = {}
    for f in sorted(CLEAN.glob("*.jsonl")):
        with io.open(f, encoding="utf-8") as fh:
            for ln in fh:
                d = json.loads(ln)
                key = (d["book"], d["line"])
                if key not in idx:
                    idx[key] = (d.get("title", ""), d.get("chapter", ""))
    return idx


def fmt_src(src, idx):
    """把 book:line.blk 转成可读出处；回查失败则原样返回。"""
    m = re.match(r"^(.*?):(\d+)(?:\.(\d+))?$", src)
    if not m:
        return src
    book, line = m.group(1), int(m.group(2))
    info = idx.get((book, line))
    if book in BOOK_NAME:  # 玄幻：书名·章名
        base = BOOK_NAME[book]
        ch = re.sub(r"^\s*正文\s*", "", info[1]).strip() if info and info[1] else ""
        return f"{base}·{ch}" if ch else f"{base}(行{line})"
    # 短篇：用文件名去序号当篇名
    short_name = re.sub(r"^\d+-", "", book)
    return f"《{short_name}》"


def esc_md(t):
    return t.replace("|", "\\|")


MOOD_TITLES = [
    ("怒", "怒"), ("惧", "惧·慌"), ("哀", "哀·伤"), ("喜", "喜·甜"),
    ("冷", "恨·冷"), ("惊", "惊·愣"), ("羞", "羞·窘"), ("忧", "忧·倦"),
    ("藏", "藏·不直写"),
]
MOOD_DESC = ("按主情绪分节（怒/惧/哀/喜/恨冷/惊/羞/忧 八种 + 「藏」：收表里反差、忍、伪装、强撑这类"
             "不直接写情绪的写法，内里情绪写在子标签里）。每组内先叙述句、后带对白句。")


def _is_dialogue(text):
    return "「" in text or "“" in text


def _entry_md(r, lvl=3):
    h = "#" * lvl
    s = f"{h} {r['id']} {r['tags']}\n\n"
    s += f"```text\n{r['text']}\n```\n\n"
    s += f"- 出处：{r['source']}\n"
    s += f"- 学什么：{r['note']}\n\n"
    return s


def build_mooded(f, rows):
    by = {c: [] for c, _ in MOOD_TITLES}
    leftover = []
    for r in rows:
        m = r.get("mood")
        if m in by:
            by[m].append(r)
        else:
            leftover.append(r)
    for code, label in MOOD_TITLES:
        group = by[code]
        if not group:
            continue
        plains = [r for r in group if not _is_dialogue(r["text"])]
        quotes = [r for r in group if _is_dialogue(r["text"])]
        f.write(f"## {label}\n\n")
        if plains:
            f.write("### 叙述：把情绪落在身体/物件上，不喊情绪名\n\n")
            for r in plains:
                f.write(_entry_md(r, 4))
        if quotes:
            f.write("### 对白：话里的情绪，或话不说尽\n\n")
            for r in quotes:
                f.write(_entry_md(r, 4))
    if leftover:
        f.write("## 未归类\n\n")
        for r in leftover:
            f.write(_entry_md(r))


def main():
    idx = load_clean_index()
    entries = []
    for f in sorted(SEL.glob("*.jsonl")):
        with io.open(f, encoding="utf-8") as fh:
            for ln in fh:
                ln = ln.strip()
                if ln:
                    entries.append(json.loads(ln))
    if not entries:
        print("没有 selected 条目，先跑初筛并落 selected/*.jsonl。")
        return

    # 去重（按 text）
    seen, uniq = set(), []
    for e in entries:
        if e["text"] in seen:
            continue
        seen.add(e["text"])
        uniq.append(e)
    entries = uniq

    counts = defaultdict(int)
    out_rows = []
    for e in entries:
        dim = e["dim"]
        counts[dim] += 1
        rid = f"{dim}-{counts[dim]:03d}"
        src_txt = fmt_src(e["src"], idx)
        out_rows.append({
            "id": rid, "dim": dim, "mood": e.get("mood", ""),
            "tags": e.get("tags", ""),
            "text": e["text"], "source": src_txt,
            "loc": e["src"], "note": e.get("note", ""),
        })

    # data/descriptions.jsonl + csv
    DATA.mkdir(exist_ok=True)
    with io.open(DATA / "descriptions.jsonl", "w", encoding="utf-8") as f:
        for r in out_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with io.open(DATA / "descriptions.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "dim", "mood", "tags", "text", "source", "loc", "note"])
        w.writeheader()
        for r in out_rows:
            w.writerow(r)

    # 分维 md
    FEN.mkdir(exist_ok=True)
    FNAME = {"情绪": "00_情绪反应", "神态": "01_神态表情", "心理": "02_心理活动",
             "动作": "03_肢体动作", "打斗": "04_打斗动作", "环境": "05_环境场景",
             "外貌": "06_人物外貌"}
    for dim in DIM_ORDER:
        rows = [r for r in out_rows if r["dim"] == dim]
        if not rows:
            continue
        with io.open(FEN / f"{FNAME[dim]}.md", "w", encoding="utf-8") as f:
            f.write(f"# {dim}描写例句\n\n")
            f.write(f"> {len(rows)} 条例句，出自现有语料原文。写法机制见各条「学什么」。\n")
            if dim in ("情绪", "神态"):
                f.write(f"> 组织：{MOOD_DESC}\n")
            f.write("\n")
            if dim in ("情绪", "神态"):
                build_mooded(f, rows)
            else:
                for r in rows:
                    f.write(_entry_md(r))
    print("已写", DATA)
    print("已写", FEN)
    print("维度分布:", dict(counts), "共", len(entries))


if __name__ == "__main__":
    main()
