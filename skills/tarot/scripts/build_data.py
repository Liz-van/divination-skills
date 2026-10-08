#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 data/parts/*.json 合并成 data/cards.json（78 张，固定顺序 + 别名索引）。

用法：
  python scripts/build_data.py            # 合并并写 data/cards.json
  python scripts/build_data.py --check    # 只校验，不写文件
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
PARTS = ROOT / "data" / "parts"
OUT = ROOT / "data" / "cards.json"

SUITS = ["权杖", "圣杯", "宝剑", "星币"]
SUIT_ELEMENT = {"权杖": "火", "圣杯": "水", "宝剑": "风", "星币": "土"}
SUIT_EN = {"权杖": "wands", "圣杯": "cups", "宝剑": "swords", "星币": "pentacles"}
MAJOR_ELEMENTS = "风 风 水 土 火 土 风 水 火 土 火 风 水 水 火 土 火 风 水 火 火 土".split()

SUIT_ALIASES = {
    "权杖": ["权杖", "魔杖", "杖", "wands", "wand"],
    "圣杯": ["圣杯", "杯", "cups", "cup"],
    "宝剑": ["宝剑", "剑", "swords", "sword"],
    "星币": ["星币", "金币", "钱币", "五芒星", "圆盘", "pentacles", "pentacle", "coins", "coin"],
}
RANK_ZH = {
    1: ["首牌", "一", "A", "Ace"],
    2: ["二", "2", "Two"], 3: ["三", "3", "Three"], 4: ["四", "4", "Four"],
    5: ["五", "5", "Five"], 6: ["六", "6", "Six"], 7: ["七", "7", "Seven"],
    8: ["八", "8", "Eight"], 9: ["九", "9", "Nine"], 10: ["十", "10", "Ten"],
    11: ["侍从", "侍者", "学徒", "仆从", "侍", "Page", "Jack"],
    12: ["骑士", "骑手", "骑", "Knight"],
    13: ["皇后", "王后", "女王", "后", "Queen"],
    14: ["国王", "王", "King"],
}
RANK_EN = {1: "ace", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven",
           8: "eight", 9: "nine", 10: "ten", 11: "page", 12: "knight", 13: "queen", 14: "king"}
RANK_NUM = {v: k for k, v in RANK_EN.items()}

MAJOR_ALIASES = {
    0: ["愚人", "愚者牌", "0号"],
    1: ["魔法师", "术士", "魔术师牌"],
    2: ["女教皇", "高阶女祭司", "女祭司牌"],
    3: ["女皇牌", "大地母亲"],
    4: ["皇帝牌", "父"],
    5: ["法皇", "主教", "祭司", "教皇牌"],
    6: ["情侣", "爱人"],
    7: ["战车"],
    8: ["力", "坚忍"],
    9: ["隐者", "老人"],
    10: ["命运轮", "轮", "命运之轮"],
    11: ["公道", "正义牌"],
    12: ["吊人", "倒吊者", "吊死者"],
    13: ["死亡", "死神牌"],
    14: ["节制牌", "调和"],
    15: ["魔鬼", "恶魔牌"],
    16: ["塔", "高塔牌", "雷击塔"],
    17: ["星", "希望之星", "星星牌"],
    18: ["月", "月亮牌"],
    19: ["日", "太阳牌"],
    20: ["最后审判", "审判日", "审判牌"],
    21: ["宇宙", "地球", "世界牌"],
}

REQUIRED = ["id", "order", "name_zh", "name_en", "arcana", "suit", "element", "number_stage",
            "keywords_up", "keywords_rev", "meaning_up", "meaning_rev", "love", "career",
            "advice", "imagery", "aliases"]


def load_parts() -> dict[str, list[dict]]:
    majors, minors = [], []
    for f in sorted(PARTS.glob("*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise SystemExit(f"硬失败：{f.name} 不是 JSON 数组")
        for card in data:
            if card.get("arcana") == "major":
                majors.append(card)
            elif card.get("arcana") == "minor":
                minors.append(card)
            else:
                raise SystemExit(f"硬失败：{f.name} 里 {card.get('name_zh')} 的 arcana 非法")
    return {"major": majors, "minor": minors}


def rank_of(card: dict) -> int:
    cid = str(card.get("id", ""))
    tail = cid.split("-")[-1]
    if not tail.isdigit():
        raise SystemExit(f"硬失败：小阿卡纳 id 需要形如 wands-01，收到 {cid!r}")
    return int(tail)


def minor_aliases(card: dict, rank: int) -> list[str]:
    suit = card["suit"]
    out: list[str] = []
    for s in SUIT_ALIASES[suit]:
        for r in RANK_ZH[rank]:
            out.append(f"{s}{r}")
        out.append(f"{s} of {RANK_EN[rank]}")
        out.append(f"{s}{rank}")
    en = SUIT_EN[suit]
    out += [f"{RANK_EN[rank]} of {en}", f"{en} {RANK_EN[rank]}", f"{en} {rank}",
            f"{en} of {RANK_EN[rank]}"]
    # 光说点数/宫廷名（如「皇后」「五」）时，故意做成多张牌共有 → 查牌工具会回一串候选让用户说清花色
    out += list(RANK_ZH[rank])
    return out


def build() -> list[dict]:
    parts = load_parts()
    if len(parts["major"]) != 22:
        raise SystemExit(f"硬失败：大阿卡纳应为 22 张，实际 {len(parts['major'])}")
    if len(parts["minor"]) != 56:
        raise SystemExit(f"硬失败：小阿卡纳应为 56 张，实际 {len(parts['minor'])}")

    order = 0
    cards: list[dict] = []

    for card in sorted(parts["major"], key=lambda c: int(c["id"])):
        n = int(card["id"])
        rec = {
            "order": order,
            "id": f"major-{n:02d}",
            "name_zh": card["name_zh"],
            "name_en": card["name_en"],
            "arcana": "major",
            "suit": None,
            "element": card.get("element") or MAJOR_ELEMENTS[n],
            "number_stage": card["number_stage"],
            "keywords_up": card["keywords_up"],
            "keywords_rev": card["keywords_rev"],
            "meaning_up": card["meaning_up"],
            "meaning_rev": card["meaning_rev"],
            "love": card["love"],
            "career": card["career"],
            "advice": card["advice"],
            "imagery": card["imagery"],
            "aliases": [],
        }
        if rec["element"] != MAJOR_ELEMENTS[n]:
            raise SystemExit(f"硬失败：{rec['name_zh']} 元素应为 {MAJOR_ELEMENTS[n]}，实际 {rec['element']}")
        rec["aliases"] = sorted({rec["name_zh"], rec["name_en"], card["name_en"].lower(),
                                 card["name_en"].lower().replace("the ", "")}
                                | set(MAJOR_ALIASES.get(n, [])))
        cards.append(rec)
        order += 1

    by_key = {(c["suit"], rank_of(c)): c for c in parts["minor"]}
    for suit in SUITS:
        for rank in range(1, 15):
            card = by_key.get((suit, rank))
            if card is None:
                raise SystemExit(f"硬失败：缺牌 {suit} {rank}")
            rec = {
                "order": order,
                "id": f"{SUIT_EN[suit]}-{rank:02d}",
                "name_zh": card["name_zh"],
                "name_en": card["name_en"],
                "arcana": "minor",
                "suit": suit,
                "element": SUIT_ELEMENT[suit],
                "number_stage": card["number_stage"],
                "keywords_up": card["keywords_up"],
                "keywords_rev": card["keywords_rev"],
                "meaning_up": card["meaning_up"],
                "meaning_rev": card["meaning_rev"],
                "love": card["love"],
                "career": card["career"],
                "advice": card["advice"],
                "imagery": card["imagery"],
                "aliases": [],
            }
            if card.get("element") and card["element"] != SUIT_ELEMENT[suit]:
                raise SystemExit(f"硬失败：{rec['name_zh']} 元素应为 {SUIT_ELEMENT[suit]}，实际 {card['element']}")
            rec["aliases"] = sorted({rec["name_zh"], rec["name_en"], card["name_en"].lower()}
                                    | set(minor_aliases(rec, rank)))
            cards.append(rec)
            order += 1

    if len(cards) != 78:
        raise SystemExit(f"硬失败：合并后应为 78 张，实际 {len(cards)}")
    return cards


def main() -> int:
    ap = argparse.ArgumentParser(description="合并牌义数据")
    ap.add_argument("--check", action="store_true", help="只校验不写文件")
    args = ap.parse_args()

    cards = build()
    dup = {}
    for c in cards:
        for a in c["aliases"]:
            dup.setdefault(a, []).append(c["name_zh"])
    ambiguous = {a: v for a, v in dup.items() if len(v) > 1}

    if not args.check:
        OUT.write_text(json.dumps(cards, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({
        "ok": True,
        "cards": len(cards),
        "written": None if args.check else str(OUT),
        "ambiguous_aliases": len(ambiguous),
        "ambiguous_sample": dict(list(ambiguous.items())[:8]),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
