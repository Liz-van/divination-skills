#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""技能自检。硬问题（exit 2）必须拦住，软问题（warning）只提示。

用法：
  python scripts/precheck.py
  python scripts/precheck.py --data <别的 cards.json>     # 用来验证「坏数据确实被拦住」
  python scripts/precheck.py --json                        # 只输出 JSON（默认就是 JSON）
退出码：0 通过（可有 warning）；2 有硬错误；3 文件缺失/无法解析。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.dont_write_bytecode = True   # 动态载入 lookup 时不要留下 __pycache__

ROOT = Path(__file__).resolve().parent.parent

SUIT_ELEMENT = {"权杖": "火", "圣杯": "水", "宝剑": "风", "星币": "土"}
MAJOR_ELEMENTS = "风 风 水 土 火 土 风 水 火 土 火 风 水 水 火 土 火 风 水 火 火 土".split()
REQUIRED_FIELDS = ["name_zh", "name_en", "arcana", "element", "number_stage", "keywords_up",
                   "keywords_rev", "meaning_up", "meaning_rev", "love", "career", "advice",
                   "imagery", "aliases"]
ID_RE = re.compile(r"^(major-\d{2}|(wands|cups|swords|pentacles)-\d{2})$")
BARNUM = ["注意沟通", "保持平衡", "相信直觉", "顺其自然", "放平心态", "一切都会好起来",
          "跟随内心", "释放情绪", "拥抱变化", "你最近压力很大", "你是个矛盾的人"]
NEEDED_FILES = ["SKILL.md", "references/spreads.md", "references/interpretation.md",
                "data/cards.json", "data/spreads.json", "data/SOURCES.md",
                "scripts/build_data.py", "scripts/lookup.py", "scripts/deal.py"]


def load_lookup():
    spec = importlib.util.spec_from_file_location("tarot_lookup", ROOT / "scripts" / "lookup.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def main() -> int:
    ap = argparse.ArgumentParser(description="tarot skill 自检")
    ap.add_argument("--data", default=str(ROOT / "data" / "cards.json"))
    ap.add_argument("--spreads", default=str(ROOT / "data" / "spreads.json"))
    args = ap.parse_args()

    errors: list[str] = []
    warnings: list[str] = []
    stats: dict = {}

    missing = [f for f in NEEDED_FILES if not (ROOT / f).exists()]
    if missing:
        errors.append(f"缺文件：{missing}")

    data_path, spread_path = Path(args.data), Path(args.spreads)
    if not data_path.exists() or not spread_path.exists():
        print(json.dumps({"ok": False, "errors": errors + [f"数据文件缺失：{data_path} / {spread_path}"],
                          "warnings": warnings}, ensure_ascii=False, indent=2))
        return 3
    try:
        cards = json.loads(data_path.read_text(encoding="utf-8"))
        spreads = json.loads(spread_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(json.dumps({"ok": False, "errors": errors + [f"JSON 解析失败：{exc}"], "warnings": warnings},
                         ensure_ascii=False, indent=2))
        return 3

    stats["cards"] = len(cards)
    if len(cards) != 78:
        errors.append(f"牌数应为 78，实际 {len(cards)}")

    majors = [c for c in cards if c.get("arcana") == "major"]
    if len(majors) != 22:
        errors.append(f"大阿卡纳应为 22，实际 {len(majors)}")

    id_seen, name_seen, order_seen = set(), set(), set()
    alias_owner: dict[str, list[str]] = {}
    barnum_hits: list[str] = []
    short_ish: list[str] = []
    for c in cards:
        cid = str(c.get("id", "?"))
        for field in REQUIRED_FIELDS:
            if field not in c or c[field] in (None, "", [], {}):
                errors.append(f"{cid} 缺字段或为空：{field}")
        if not ID_RE.match(cid):
            errors.append(f"id 格式不合法：{cid}")
        if cid in id_seen:
            errors.append(f"id 重复：{cid}")
        id_seen.add(cid)
        if c.get("name_zh") in name_seen:
            errors.append(f"中文名重复：{c.get('name_zh')}")
        name_seen.add(c.get("name_zh"))
        if isinstance(c.get("order"), int):
            if c["order"] in order_seen:
                errors.append(f"order 重复：{c['order']}")
            order_seen.add(c["order"])

        if c.get("arcana") == "major":
            n = int(cid.split("-")[-1]) if cid.startswith("major-") else None
            if n is not None and 0 <= n <= 21 and c.get("element") != MAJOR_ELEMENTS[n]:
                errors.append(f"{cid} 元素应为 {MAJOR_ELEMENTS[n]}，实际 {c.get('element')}")
        elif c.get("arcana") == "minor":
            if c.get("suit") not in SUIT_ELEMENT:
                errors.append(f"{cid} suit 非法：{c.get('suit')}")
            elif c.get("element") != SUIT_ELEMENT[c["suit"]]:
                errors.append(f"{cid} 元素应为 {SUIT_ELEMENT[c['suit']]}，实际 {c.get('element')}")
        else:
            errors.append(f"{cid} arcana 非法：{c.get('arcana')}")

        for key in ("keywords_up", "keywords_rev"):
            v = c.get(key)
            if not isinstance(v, list) or not (3 <= len(v) <= 5):
                errors.append(f"{cid} {key} 应为 3–5 条，实际 {len(v) if isinstance(v, list) else v}")
        up = str(c.get("meaning_up", ""))
        rev = str(c.get("meaning_rev", ""))
        floor = 110 if c.get("arcana") == "major" else 100
        if len(up) < floor:
            errors.append(f"{cid} meaning_up 太短（{len(up)} 字，至少要 {floor}）")
        elif len(up) < 120:
            short_ish.append(f"{cid}({len(up)})")
        if len(rev) < 60:
            errors.append(f"{cid} meaning_rev 太短（{len(rev)} 字）")
        if len(str(c.get("advice", ""))) < 10:
            errors.append(f"{cid} advice 太短或太虚")
        if len(str(c.get("imagery", ""))) < 15:
            warnings.append(f"{cid} imagery 偏短，可能没照着 RWS 画面写")

        for alias in c.get("aliases", []) or []:
            alias_owner.setdefault(str(alias), []).append(c.get("name_zh"))
        for field in ("meaning_up", "meaning_rev", "advice", "love", "career"):
            text = str(c.get(field, ""))
            for phrase in BARNUM:
                if phrase in text:
                    barnum_hits.append(f"{cid}.{field} 命中巴纳姆句式「{phrase}」")

    orders = sorted(o for o in order_seen if isinstance(o, int))
    if orders and orders != list(range(len(orders))):
        errors.append("order 不是 0..77 的连续整数")

    ambiguous = {a: v for a, v in alias_owner.items() if len(set(v)) > 1}
    if ambiguous:
        warnings.append(f"有 {len(ambiguous)} 个别名指到多张牌（合法的歧义，如「皇后」）")
    if short_ish:
        warnings.append(f"有 {len(short_ish)} 张 meaning_up 在 100–119 字之间（可接受，扩写时优先补这些）："
                        + "、".join(short_ish[:8]) + ("…" if len(short_ish) > 8 else ""))
    if barnum_hits:
        warnings.append(f"巴纳姆句式命中 {len(barnum_hits)} 处")
    stats["ambiguous_aliases"] = len(ambiguous)
    stats["barnum_hits"] = len(barnum_hits)

    for name, sp in spreads.items():
        if not isinstance(sp.get("count"), int) or sp["count"] < 1:
            errors.append(f"牌阵 {name} 的 count 非法")
        elif len(sp.get("positions", [])) != sp["count"]:
            errors.append(f"牌阵 {name} 的 count({sp['count']}) 与 positions({len(sp.get('positions', []))}) 不一致")
    stats["spreads"] = list(spreads)

    spreads_md = ROOT / "references" / "spreads.md"
    if spreads_md.exists():
        text = spreads_md.read_text(encoding="utf-8")
        for name, sp in spreads.items():
            label = sp.get("name_zh") or name
            if label not in text and name not in text:
                errors.append(f"references/spreads.md 里没有写牌阵 {label}")
        for pos in {p for sp in spreads.values() for p in sp.get("positions", [])}:
            if pos not in text:
                warnings.append(f"spreads.md 里没出现位置名「{pos}」")

    skill_md = ROOT / "SKILL.md"
    if skill_md.exists():
        text = skill_md.read_text(encoding="utf-8")
        if not re.search(r"^name:\s*tarot\s*$", text, re.M):
            errors.append("SKILL.md frontmatter 缺 name: tarot")
        m = re.search(r"^description:\s*[\"']?(.+?)[\"']?\s*$", text, re.M)
        if not m:
            errors.append("SKILL.md frontmatter 缺 description")
        else:
            desc = m.group(1)
            if "$塔罗" not in desc:
                errors.append("description 里没有触发词 $塔罗")
            if len(desc) > 1024:
                errors.append(f"description 超过 1024 字符（{len(desc)}）")
        for must in ["选牌", "lookup.py", "deal.py", "precheck.py"]:
            if must not in text:
                errors.append(f"SKILL.md 里没有提到 {must}")
        lines = len(text.splitlines())
        stats["skill_md_lines"] = lines
        if lines > 500:
            warnings.append(f"SKILL.md 有 {lines} 行，偏长（建议长内容挪进 references/）")

    deal_py = ROOT / "scripts" / "deal.py"
    if deal_py.exists():
        src = deal_py.read_text(encoding="utf-8")
        if "confirm_user_asked" not in src:
            errors.append("deal.py 里缺少「必须用户明说才代选」的闸门逻辑")
        stats["deal_guard"] = "confirm_user_asked" in src

    if not missing:
        try:
            lk = load_lookup()
            index = lk.build_index(cards)
            bad = []
            for c in cards:
                for name in (c["name_zh"], c["name_en"]):
                    hit, err = lk.resolve(name, cards, index)
                    if err or hit is None or hit["id"] != c["id"]:
                        bad.append(f"{c['id']}/{name}")
            if bad:
                errors.append(f"lookup 反查失败 {len(bad)} 处：{bad[:8]}")
            stats["lookup_roundtrip"] = f"{len(cards) * 2 - len(bad)}/{len(cards) * 2}"
        except Exception as exc:  # noqa: BLE001
            errors.append(f"lookup 反查时出错：{type(exc).__name__}: {exc}")

    ok = not errors
    print(json.dumps({"ok": ok, "errors": errors, "warnings": warnings,
                      "barnum_samples": barnum_hits[:6], "stats": stats},
                     ensure_ascii=False, indent=2))
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
