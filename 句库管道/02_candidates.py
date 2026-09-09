# -*- coding: utf-8 -*-
"""02_candidates.py —— 从 clean 的句块里按 7 维信号词粗筛候选。

不做精判（那由人工/LLM 精筛时定夺），只负责：打疑似维度标签、滤垃圾、
按维度均匀采样成可控大小的候选池，并对"对白块"附上邻块上下文
（玄幻取同段前后块；短篇取相邻行），供判断"情绪×对白"用。
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
OUT = ROOT / "work" / "candidates.jsonl"
SEED = 20260909

# ------- 信号词表（宽松，精筛时重判） -------
FACE = "容貌 长相 五官 面容 面庞 脸庞 脸型 相貌 模样 打扮 穿着 身着 一袭 肌肤 肤 眉 眸 唇 腮 颈 身形 个子 眉眼".split()
SHEN = ("神色 神情 表情 眼神 目光 眼色 脸色 眉 皱 挑 眯 瞪 撇嘴 咬唇 嘴角 笑 面无表情 "
        "垂眸 抬眼 瞥 凝视 怔怔 愣愣 僵硬 淡然 平静 沉").split()
QING = ("怒 恨 惊 慌 怕 羞 恼 急 气 心 颤 抖 忍 攥 拳 咬 牙 眼眶 红 酸 泪 哽咽 咽 喉 "
        "嗓 呼吸 喘 紧张 心虚 不安 心虚 冷漠 冷淡 漠然 软 笑").split()
DONG = ("走 站 坐 蹲 弯腰 起身 转身 回头 伸手 抬手 放下 抓 拿 拍 推 拉 抱 扶 挡 退 "
        "靠 扑 跪 低头 抬头 侧身 顿住 停住 踩 踏 迈 掀 拨 敛 收").split()
DOU = ("拳 掌 指 腿 招 剑 刀 枪 劲 罡 轰 击 劈 斩 刺 削 扫 崩 撞 杀 血 闪 躲 避 翻身 "
        "凌空 跃 冲 扑 缠斗 交手 对撞 威压 气势 元神 法宝 飞剑 真气 内劲").split()
ENV = ("夜色 月光 天空 天边 风 雨 雪 雷 云 山 林 树 江 湖 海 街 巷 房 灯 阳光 空气 "
        "雾 烟 味 寂静 安静 沉默 斑驳 光影 斜阳 黄昏 清晨 昏暗 灯火 冷清").split()
XIN = ("想 觉得 以为 认为 暗想 心道 心想 念头 盘算 琢磨 忐忑 担心 怕 忍不住 感叹 羡慕 "
        "嫉妒 不满 怀疑 犹豫 挣扎 豁然 恍然 意识到 反应").split()

DIMS = {
    "外貌": FACE, "神态": SHEN, "情绪": QING, "动作": DONG,
    "打斗": DOU, "环境": ENV, "心理": XIN,
}

SIZE_RANGE = (8, 96)
PER_DIM = 400      # 每维采样上限
QUOTE_N = 900      # 对白块采样上限
QUOTE_MAXLEN = 150


def load_blocks():
    """读取全部 clean jsonl，返回 (blocks, index)。
    blocks: [{book,kind,line,blk,text,dims}]（顺序遍历，天然按 line/blk 排序）
    index: {(book,line): [(blk, text)]}，玄幻段内邻块取用。
    """
    blocks = []
    idx = defaultdict(list)
    for f in sorted(CLEAN.glob("*.jsonl")):
        with io.open(f, encoding="utf-8") as fh:
            for ln in fh:
                d = json.loads(ln)
                dims = sorted({name for name, ws in DIMS.items() if any(w in d["text"] for w in ws)})
                d["dims"] = dims
                blocks.append(d)
                idx[(d["book"], d["line"])].append((d["blk"], d["text"]))
    return blocks, idx


def is_quote(t):
    return t.startswith("“") or t.startswith("「")


def make_ctx(d, idx):
    """对白块的邻块上下文。玄幻:同段前后块;短篇:相邻行首块。"""
    if not is_quote(d["text"]):
        return None, None
    cells = idx.get((d["book"], d["line"]), [])
    if len(cells) > 1:  # 玄幻：段内多块
        pos = next((i for i, (b, _) in enumerate(cells) if b == d["blk"]), None)
        if pos is None:
            return None, None
        pre = cells[pos - 1][1] if pos > 0 else None
        post = cells[pos + 1][1] if pos + 1 < len(cells) else None
        return pre, post
    # 短篇：相邻行
    pre = post = None
    if d["kind"] == "short":
        for delta, slot in ((-1, "pre"), (1, "post")):
            hits = idx.get((d["book"], d["line"] + delta))
            if hits:
                if slot == "pre":
                    pre = hits[0][1]
                else:
                    post = hits[0][1]
    return pre, post


def sample_pool(blocks):
    rng = random.Random(SEED)
    seen = set()
    quote_seen = set()

    def uniq(bucket):
        out = []
        for d in bucket:
            if d["text"] in seen:
                continue
            seen.add(d["text"])
            out.append(d)
        return out

    buckets = {name: [] for name in DIMS}
    quotes = []
    for d in blocks:
        t = d["text"]
        if not (SIZE_RANGE[0] <= len(t) <= SIZE_RANGE[1]):
            continue
        if re.search(r"(?:^[。，、…]|。。|站力地|北级熊|得不得|方丈室)", t):
            continue
        if is_quote(t):
            if len(t) <= QUOTE_MAXLEN:
                quotes.append(d)
            continue
        for name in d["dims"]:
            buckets[name].append(d)
    pool = []
    for name, bucket in buckets.items():
        bucket = uniq(bucket)
        rng.shuffle(bucket)
        for d in bucket[:PER_DIM]:
            pool.append(d)
    q = uniq(quotes)
    rng.shuffle(q)
    for d in q[:QUOTE_N]:
        pool.append(d)
    return pool


def main():
    blocks, idx = load_blocks()
    dim_count = defaultdict(int)
    quote_count = 0
    for d in blocks:
        t = d["text"]
        if not (SIZE_RANGE[0] <= len(t) <= SIZE_RANGE[1]):
            continue
        if is_quote(t):
            quote_count += 1
            continue
        for name in d["dims"]:
            dim_count[name] += 1
    print("== 全量命中统计（块 8-96 字）==")
    for name in DIMS:
        print(f"{name}: {dim_count[name]}")
    print(f"对白块: {quote_count}")
    pool = sample_pool(blocks)
    with io.open(OUT, "w", encoding="utf-8") as f:
        for d in pool:
            pre, post = make_ctx(d, idx)
            rec = {k: d[k] for k in ("book", "kind", "title", "chapter", "line", "blk", "text")}
            rec["is_quote"] = is_quote(d["text"])
            rec["dims"] = d["dims"]
            if pre:
                rec["pre"] = pre
            if post:
                rec["post"] = post
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"\n候选池写入 {OUT}：{len(pool)} 条")


if __name__ == "__main__":
    main()
