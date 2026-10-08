#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""查牌义。按牌名（中英文、别名、模糊）取出结构化牌义，并顺手算好牌面分布。

用法：
  python scripts/lookup.py --list
  python scripts/lookup.py --name 权杖三
  python scripts/lookup.py --name moon --orientation 逆位
  python scripts/lookup.py --spread three --cards "权杖三:正位,月亮:逆位,星币侍从:正位"
  python scripts/lookup.py --spread three --cards "权杖三,月亮,星币侍从"        # 默认正位
输出：UTF-8 JSON（牌义、位置、分布统计）。查不到时给出候选建议并以退出码 3 结束。
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CARDS = ROOT / "data" / "cards.json"
DEFAULT_SPREADS = ROOT / "data" / "spreads.json"

REVERSED_WORDS = {"逆位", "逆", "倒", "反", "reversed", "rev", "r", "upside-down", "upsidedown"}
UPRIGHT_WORDS = {"正位", "正", "up", "upright", "u"}

# 数字写法归一：英文数词 / 宫廷英文 / 中文数字，都换成阿拉伯数字，这样
# "3 of wands"、"three of wands"、"权杖三"、"wands 3" 会落到同一个 key 上。
EN_NUM = {"ace": "1", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
          "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
          "page": "11", "jack": "11", "knight": "12", "queen": "13", "king": "14"}
ZH_NUM = {"一": "1", "二": "2", "三": "3", "四": "4", "五": "5", "六": "6",
          "七": "7", "八": "8", "九": "9", "十": "10"}


def norm(text: str) -> str:
    s = unicodedata.normalize("NFKC", str(text)).strip().lower()
    s = s.replace("的牌", "").replace("牌", "")
    for word, digit in EN_NUM.items():
        s = re.sub(rf"\b{word}\b", digit, s)
    s = re.sub(r"\b(of|the)\b", "", s)
    for zh, digit in ZH_NUM.items():
        s = s.replace(zh, digit)
    s = re.sub(r"[\s·・._\-/()（）\[\]【】,，、:：]", "", s)
    return s


def load_json(path: Path):
    if not path.exists():
        print(json.dumps({"error": f"文件不存在：{path}，先运行 python scripts/build_data.py"},
                         ensure_ascii=False, indent=2))
        raise SystemExit(3)
    return json.loads(path.read_text(encoding="utf-8"))


def build_index(cards: list[dict]) -> dict[str, list[int]]:
    index: dict[str, list[int]] = {}
    for card in cards:
        for alias in card["aliases"]:
            key = norm(alias)
            if not key:
                continue
            index.setdefault(key, [])
            if card["order"] not in index[key]:
                index[key].append(card["order"])
        for extra in (card["name_zh"], card["name_en"]):
            key = norm(extra)
            index.setdefault(key, [])
            if card["order"] not in index[key]:
                index[key].append(card["order"])
    return index


def all_keys(index: dict[str, list[int]]) -> list[str]:
    return list(index.keys())


def resolve(name: str, cards: list[dict], index: dict[str, list[int]]):
    key = norm(name)
    hits = index.get(key, [])
    if len(hits) == 1:
        return cards[hits[0]], None
    if len(hits) > 1:
        return None, {"error": "牌名有歧义，请说明花色", "input": name,
                      "candidates": [cards[o]["name_zh"] for o in hits]}
    close = difflib.get_close_matches(key, all_keys(index), n=6, cutoff=0.6)
    candidates = sorted({cards[o]["name_zh"] for k in close for o in index[k]})[:8]
    return None, {"error": "查不到这张牌", "input": name, "suggestions": candidates}


def parse_cards_arg(spec: str) -> list[tuple[str, str]]:
    out = []
    for raw in spec.split(","):
        raw = raw.strip()
        if not raw:
            continue
        if ":" in raw or "：" in raw:
            name, orient = re.split(r"[:：]", raw, maxsplit=1)
            orient = orient.strip()
        else:
            name, orient = raw, "正位"
        out.append((name.strip(), orient.strip() or "正位"))
    return out


def orientation_of(word: str) -> str | None:
    w = norm(word)
    if w in {norm(x) for x in REVERSED_WORDS}:
        return "逆位"
    if w in {norm(x) for x in UPRIGHT_WORDS}:
        return "正位"
    return None


def render(card: dict, orientation: str, position: str | None, given: str) -> dict:
    rev = orientation == "逆位"
    return {
        "position": position,
        "input": given,
        "matched": card["name_zh"],
        "id": card["id"],
        "name_zh": card["name_zh"],
        "name_en": card["name_en"],
        "arcana": card["arcana"],
        "suit": card["suit"],
        "element": card["element"],
        "number_stage": card["number_stage"],
        "orientation": orientation,
        "keywords": card["keywords_rev"] if rev else card["keywords_up"],
        "meaning": card["meaning_rev"] if rev else card["meaning_up"],
        "love": card["love"],
        "career": card["career"],
        "advice": card["advice"],
        "imagery": card["imagery"],
    }


def distribution(picked: list[dict]) -> dict:
    majors = [c for c in picked if c["arcana"] == "major"]
    minors = [c for c in picked if c["arcana"] == "minor"]
    suits: dict[str, int] = {}
    elements: dict[str, int] = {}
    for c in picked:
        if c["suit"]:
            suits[c["suit"]] = suits.get(c["suit"], 0) + 1
        elements[c["element"]] = elements.get(c["element"], 0) + 1
    numbers = []
    for c in picked:
        tail = c["id"].split("-")[-1]
        numbers.append(int(tail))
    oppositions = []
    major_ids = {int(c["id"].split("-")[-1]) for c in majors}
    for n in sorted(major_ids):
        if 21 - n in major_ids and n < 21 - n:
            oppositions.append([n, 21 - n])
    total = len(picked) or 1
    return {
        "total": len(picked),
        "major_count": len(majors),
        "major_ratio": round(len(majors) / total, 2),
        "minor_count": len(minors),
        "reversed_count": sum(1 for c in picked if c["orientation"] == "逆位"),
        "suits": suits,
        "court_cards": [c["name_zh"] for c in minors if int(c["id"].split("-")[-1]) >= 11],
        "elements": elements,
        "numbers": numbers,
        "opposition_pairs": oppositions,
        "notes": "大阿卡纳占比 >50% 主题重大；30–50% 主题在成型；<30% 多在日常层面。",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="查牌义")
    ap.add_argument("--name", help="单张牌名，如 权杖三 / moon")
    ap.add_argument("--orientation", default="正位", help="正位 或 逆位")
    ap.add_argument("--cards", help='多张牌，如 "权杖三:正位,月亮:逆位"')
    ap.add_argument("--spread", help="牌阵名（见 data/spreads.json），用于给位置命名并校验张数")
    ap.add_argument("--data", default=str(DEFAULT_CARDS), help="cards.json 路径")
    ap.add_argument("--spreads", default=str(DEFAULT_SPREADS), help="spreads.json 路径")
    ap.add_argument("--list", action="store_true", help="列出 78 张牌与编号")
    args = ap.parse_args()

    cards = load_json(Path(args.data))
    index = build_index(cards)

    if args.list:
        print(json.dumps({"total": len(cards),
                          "cards": [{"order": c["order"], "id": c["id"], "name_zh": c["name_zh"],
                                     "name_en": c["name_en"], "arcana": c["arcana"], "suit": c["suit"],
                                     "element": c["element"]} for c in cards]},
                         ensure_ascii=False, indent=1))
        return 0

    if not args.name and not args.cards:
        print(json.dumps({"error": "要么给 --name，要么给 --cards", "examples":
                          ['--name 权杖三', '--spread three --cards "权杖三:正位,月亮:逆位,星币侍从:正位"']},
                         ensure_ascii=False, indent=2))
        return 3

    spread_name, positions = None, []
    if args.spread:
        spreads = load_json(Path(args.spreads))
        if args.spread not in spreads:
            print(json.dumps({"error": f"没有这个牌阵：{args.spread}", "available": list(spreads)},
                             ensure_ascii=False, indent=2))
            return 3
        spread_name = args.spread
        positions = list(spreads[args.spread]["positions"])

    if args.name:
        pairs = [(args.name, args.orientation)]
    else:
        pairs = parse_cards_arg(args.cards)

    if spread_name and len(pairs) != len(positions):
        print(json.dumps({"error": f"牌阵 {spread_name} 需要 {len(positions)} 张牌，收到 {len(pairs)} 张",
                          "positions": positions}, ensure_ascii=False, indent=2))
        return 3

    picked, problems = [], []
    for i, (name, orient_word) in enumerate(pairs):
        card, err = resolve(name, cards, index)
        if err:
            problems.append(err)
            continue
        orientation = orientation_of(orient_word)
        if orientation is None:
            problems.append({"error": "正逆位写错了，只能写 正位/逆位", "input": orient_word})
            continue
        position = positions[i] if positions and i < len(positions) else None
        picked.append(render(card, orientation, position, name))

    if problems:
        print(json.dumps({"error": "有牌没解析成功", "problems": problems, "resolved": [c["name_zh"] for c in picked],
                          "tips": ["花色要写清楚：皇后 有四个，得写 权杖皇后",
                                   "别名表见 data/cards.json 的 aliases 字段"]},
                         ensure_ascii=False, indent=2))
        return 3

    print(json.dumps({"spread": spread_name, "positions": positions, "cards": picked,
                      "distribution": distribution(picked)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
