# -*- coding: utf-8 -*-
"""inspect.py —— 分页 skim 候选池,辅助人工精筛挑句。

用法:
  python inspect.py --where quote|plain|dim=情绪 [--book longshe|foben|0001-零星]
                    [--start N] [--limit N]
打印每条一行：序号 | 维度 | book:line.blk | 章(短) | 文本（对白附上/下行语境）
"""
import io
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
POOL = ROOT / "work" / "candidates.jsonl"

W, S, L, B, K = "--where", "--start", "--limit", "--book", "--kind"
args = dict(zip(sys.argv[1::2], sys.argv[2::2]))
where = args.get(W, "quote")
start = int(args.get(S, "0"))
limit = int(args.get(L, "120"))
book = args.get(B)
kind = args.get(K, "")

if where.startswith("dim="):
    want = where.split("=", 1)[1]
else:
    want = where

rows = []
with io.open(POOL, encoding="utf-8") as f:
    for j, ln in enumerate(f):
        d = json.loads(ln)
        if kind and d["kind"] != kind:
            continue
        if book and d["book"] != book:
            continue
        if want == "quote" and not d["is_quote"]:
            continue
        if want == "plain" and d["is_quote"]:
            continue
        if want.startswith("dim"):
            if want not in d.get("dims", []):
                continue
        rows.append(d)

for d in rows[start:start + limit]:
    dims = ",".join(d.get("dims", [])) or "—"
    ch = (d.get("chapter") or d.get("title") or "")[:12].replace(" ", "")
    tag = "Q" if d["is_quote"] else "P"
    print(f"[{start + rows.index(d)}] {tag}|{dims}|{d['book']}:{d['line']}.{d['blk']}|{ch}|{d['text']}")
    if d["is_quote"]:
        if d.get("pre"):
            print(f"      ↑ {d['pre'][:90]}")
        if d.get("post"):
            print(f"      ↓ {d['post'][:90]}")
print(f"\n-- 命中 {len(rows)} 条,当前显示 {start}~{start + limit}")
