# -*- coding: utf-8 -*-
"""04_scan_mood.py —— 按主情绪的"直给反应"信号词，从 clean 全量补扫候选。

目标：补 惊/惧/怒/喜/羞/忧（及少量哀/冷）的经典身体反应句。
输出 work/candidates_mood.jsonl：{mood, book, line, text}，每主情绪去重后随机取样限 260。
"""
import io
import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
CLEAN = ROOT / "work" / "clean"
OUT = ROOT / "work" / "candidates_mood.jsonl"

MOOD_SIG = {
    "惊": "瞳孔 瞪大 倒吸 一怔 一呆 一愣 呆住 愣住 僵住 浑身一僵 凉气 傻眼 发懵 瞠目 难以置信 不敢置信 回神 愕然 惊愕 心猛一跳",
    "惧": "冷汗 心狂跳 心跳加速 心提到 心一沉 心头一紧 腿软 腿一软 发软 发抖 哆嗦 发颤 颤声 声音发颤 煞白 惨白 刷白 手抖 手心 冒汗 背后发凉 毛骨悚然 不寒而栗 胆寒 吓得",
    "怒": "青筋 铁青 拍桌 拍案 一拍桌子 猛地一拍 砸 摔门 怒喝 怒吼 怒斥 咬牙 咬紧牙 攥拳 攥紧 握拳 拳头 冒火 火冒三丈 血涌 气血上涌 暴跳 怒目 横眉 愤然 气得发抖 火起",
    "喜": "眉开眼笑 笑意 眼角 眼里有光 眼睛一亮 眼底有光 嘴角上扬 勾起嘴角 压不住 笑出声 哼着歌 哼起 雀跃 心花怒放 乐得 喜上眉梢 满脸堆笑 眼里亮 亮晶晶 喜滋滋 忍不住笑",
    "羞": "脸红 耳根 耳尖 发烫 发红 烫 低下头 垂眼 绞着手指 绞着衣角 捏着衣角 难为情 不好意思 害羞 窘 赧然 羞涩 耳朵烧 脸颊发烫",
    "忧": "叹了 叹气 眉心 眉头紧锁 锁着眉 皱紧眉 疲惫 满脸倦 落寞 出神 发呆 无精打采 怅然 心事重重 低气压 闷闷不乐 眼神空 怔怔出神",
}

SIZE = 260
SIGS = {m: s.split() for m, s in MOOD_SIG.items()}


def main():
    buckets = defaultdict(list)
    seen = defaultdict(set)
    for f in sorted(CLEAN.glob("*.jsonl")):
        with io.open(f, encoding="utf-8") as fh:
            for ln in fh:
                d = json.loads(ln)
                t = d["text"]
                if not (8 <= len(t) <= 80):
                    continue
                for mood, words in SIGS.items():
                    if any(w in t for w in words):
                        if t not in seen[mood]:
                            seen[mood].add(t)
                            buckets[mood].append({"mood": mood, "book": d["book"],
                                                  "line": d["line"], "text": t})
    rng = random.Random(7)
    with io.open(OUT, "w", encoding="utf-8") as f:
        for mood, rows in buckets.items():
            rng.shuffle(rows)
            for r in rows[:SIZE]:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    for mood in SIGS:
        print(f"{mood}: 命中 {len(buckets[mood])}，取样 min(260)")


if __name__ == "__main__":
    main()
