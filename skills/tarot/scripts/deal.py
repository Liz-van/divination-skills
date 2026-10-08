#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""盲抽牌：洗好 78 张牌藏进一个局（state），用户报编号后翻开。

为什么有这个东西：塔罗的选牌权归用户。用户手里没有实体牌时，用「编号盲抽」——
先由脚本真随机洗好 78 张（secrets.SystemRandom）、藏起来不显示，用户报 1–78 的数字，
再翻牌。这样既保证用户自己在选，也不是 AI 现编牌面。

用法：
  python scripts/deal.py --new --spread three
  python scripts/deal.py --reveal <state_id> --picks 12,45,7
  python scripts/deal.py --reveal <state_id> --picks 12,45,7 --reversed 45 --upright 12
  python scripts/deal.py --state <state_id>            # 看这局的状态（不泄露牌面）
  python scripts/deal.py --list                        # 列出本机所有局
  python scripts/deal.py --auto --spread three --confirm-user-asked   # 仅当用户明说「你帮我抽」

说明：--new 只输出「要报几个数字」，绝不输出任何牌名；牌面只在 --reveal 时出现。
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import time
import uuid
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CARDS = ROOT / "data" / "cards.json"
DEFAULT_SPREADS = ROOT / "data" / "spreads.json"
DEFAULT_STATE = Path(os.environ.get("TAROT_STATE_DIR") or (ROOT / "state"))


def load_json(path: Path, hint: str):
    if not path.exists():
        print(json.dumps({"error": f"文件不存在：{path}", "hint": hint}, ensure_ascii=False, indent=2))
        raise SystemExit(3)
    return json.loads(path.read_text(encoding="utf-8"))


def state_dir(args) -> Path:
    d = Path(args.state_dir) if args.state_dir else DEFAULT_STATE
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(json.dumps({"error": f"建不了 state 目录：{d}（{exc}）",
                          "fix": "设环境变量 TAROT_STATE_DIR 指到可写目录，或用 --state-dir 指定"},
                         ensure_ascii=False, indent=2))
        raise SystemExit(3)
    return d


def cmd_new(args, cards, spreads) -> int:
    if args.spread not in spreads:
        print(json.dumps({"error": f"没有这个牌阵：{args.spread}", "available": list(spreads)},
                         ensure_ascii=False, indent=2))
        return 3
    spread = spreads[args.spread]
    count = spread["count"]

    rng = secrets.SystemRandom()
    pool = [{"card_id": c["id"], "orientation": "逆位" if rng.random() < 0.5 else "正位"} for c in cards]
    rng.shuffle(pool)

    sid = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:4]
    payload = {
        "state_id": sid,
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        "spread": args.spread,
        "spread_name_zh": spread.get("name_zh"),
        "positions": spread["positions"],
        "count": count,
        "pool": pool,
        "picks": [],
        "revealed": False,
        "mode": "blind",
    }
    path = state_dir(args) / f"{sid}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    print(json.dumps({
        "state_id": sid,
        "spread": args.spread,
        "spread_name_zh": spread.get("name_zh"),
        "positions": spread["positions"],
        "picks_needed": count,
        "pool_size": len(pool),
        "instruction": f"请你报 {count} 个 1–{len(pool)} 之间、互不重复的数字（顺序对应上面的位置）。"
                       "不要问我牌是什么，数字由你定。报完我立刻翻牌。",
        "next": f"python scripts/deal.py --reveal {sid} --picks <你的数字,逗号隔开>",
        "note": "洗牌用的是操作系统级随机（secrets.SystemRandom）；牌面已藏进 state 文件，翻牌前不会出现。",
    }, ensure_ascii=False, indent=2))
    return 0


def find_state(args, sid: str) -> Path:
    d = state_dir(args)
    path = d / f"{sid}.json"
    if path.exists():
        return path
    hits = sorted(d.glob(f"*{sid}*.json"))
    if len(hits) == 1:
        return hits[0]
    if not hits:
        print(json.dumps({"error": f"找不到这一局：{sid}", "state_dir": str(d)}, ensure_ascii=False, indent=2))
        raise SystemExit(3)
    print(json.dumps({"error": "有多个局匹配，写全 state_id", "candidates": [p.stem for p in hits]},
                     ensure_ascii=False, indent=2))
    raise SystemExit(3)


def parse_picks(raw: str, size: int, count: int):
    try:
        picks = [int(x) for x in raw.replace("，", ",").split(",") if x.strip()]
    except ValueError:
        return None, {"error": "编号必须是整数", "input": raw}
    if len(set(picks)) != len(picks):
        return None, {"error": "编号不能重复", "picks": picks}
    bad = [p for p in picks if not (1 <= p <= size)]
    if bad:
        return None, {"error": f"编号超出范围 1–{size}", "bad": bad}
    if len(picks) != count:
        return None, {"error": f"这一局要 {count} 个编号，收到 {len(picks)} 个", "picks": picks}
    return picks, None


def cmd_reveal(args, cards, state_path: Path) -> int:
    state = json.loads(state_path.read_text(encoding="utf-8"))
    by_id = {c["id"]: c for c in cards}
    picks, err = parse_picks(args.picks, len(state["pool"]), state["count"])
    if err:
        print(json.dumps(err, ensure_ascii=False, indent=2))
        return 3

    force_rev = {int(x) for x in (args.reversed or "").replace("，", ",").split(",") if x.strip().isdigit()}
    force_up = {int(x) for x in (args.upright or "").replace("，", ",").split(",") if x.strip().isdigit()}
    for n in force_rev | force_up:
        if n not in picks:
            print(json.dumps({"error": f"--reversed/--upright 里的 {n} 不在你这次报的编号里", "picks": picks},
                             ensure_ascii=False, indent=2))
            return 3

    out, lookup_args = [], []
    for i, p in enumerate(picks):
        entry = state["pool"][p - 1]
        card = by_id.get(entry["card_id"])
        if card is None:
            print(json.dumps({"error": f"state 里的 {entry['card_id']} 不在 cards.json 中，数据版本对不上"},
                             ensure_ascii=False, indent=2))
            return 3
        orientation = "逆位" if p in force_rev else ("正位" if p in force_up else entry["orientation"])
        position = state["positions"][i] if i < len(state["positions"]) else None
        out.append({"position": position, "pick": p, "name_zh": card["name_zh"], "name_en": card["name_en"],
                    "orientation": orientation, "arcana": card["arcana"], "suit": card["suit"],
                    "element": card["element"],
                    "note": "用户手动指定逆位" if p in force_rev else ("用户手动指定正位" if p in force_up else "洗牌时决定")})
        lookup_args.append(f"{card['name_zh']}:{orientation}")

    state["picks"] = picks
    state["revealed"] = True
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")

    print(json.dumps({
        "state_id": state["state_id"],
        "spread": state["spread"],
        "positions": state["positions"],
        "cards": out,
        "next": f'python scripts/lookup.py --spread {state["spread"]} --cards "{",".join(lookup_args)}"',
        "reminder": "先照牌面事实说（哪张、正逆位、落在哪个位置），再解读，最后给可执行建议。",
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_auto(args, cards, spreads) -> int:
    if not args.confirm_user_asked:
        print(json.dumps({
            "error": "--auto 会替你选牌，默认禁止（选牌权归用户）",
            "how_to": '只有用户本人在对话里明说「你帮我抽」之后，才能加 --confirm-user-asked 重跑：'
                      "python scripts/deal.py --auto --spread three --confirm-user-asked",
        }, ensure_ascii=False, indent=2))
        return 4
    rc = cmd_new(args, cards, spreads)
    if rc != 0:
        return rc
    d = state_dir(args)
    latest = max(d.glob("*.json"), key=lambda p: p.stat().st_mtime)
    sid = latest.stem
    rng = secrets.SystemRandom()
    picks = sorted(rng.sample(range(1, len(cards) + 1), spreads[args.spread]["count"]))
    args.picks = ",".join(str(p) for p in picks)
    rc = cmd_reveal(args, cards, latest)
    if rc == 0:
        print(json.dumps({"warning": f"这一局是脚本替你抽的（state {sid}），用户本人没有选牌。",
                          "note": "只在用户明说「你帮我抽」时才能这样用，解读时要说明这一点。"},
                         ensure_ascii=False, indent=2))
    return rc


def cmd_state(args, state_path: Path) -> int:
    state = json.loads(state_path.read_text(encoding="utf-8"))
    public = {k: v for k, v in state.items() if k != "pool"}
    public["pool_size"] = len(state["pool"])
    public["pool_hidden"] = True
    print(json.dumps(public, ensure_ascii=False, indent=2))
    return 0


def cmd_list(args) -> int:
    d = state_dir(args)
    rows = []
    for p in sorted(d.glob("*.json")):
        try:
            s = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        rows.append({"state_id": s.get("state_id", p.stem), "created": s.get("created"),
                     "spread": s.get("spread"), "revealed": s.get("revealed"), "mode": s.get("mode")})
    print(json.dumps({"state_dir": str(d), "states": rows}, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="盲抽牌（选牌权归用户）")
    ap.add_argument("--new", action="store_true", help="开一局：洗好 78 张藏起来，等你报编号")
    ap.add_argument("--reveal", metavar="STATE_ID", help="按 state_id 翻开用户报的编号")
    ap.add_argument("--picks", help="用户报的编号，逗号隔开，如 12,45,7")
    ap.add_argument("--reversed", help="强制某些编号为逆位，如 45")
    ap.add_argument("--upright", help="强制某些编号为正位，如 12")
    ap.add_argument("--auto", action="store_true", help="脚本代选（默认禁止，需 --confirm-user-asked）")
    ap.add_argument("--confirm-user-asked", action="store_true", help="确认用户本人明说「你帮我抽」")
    ap.add_argument("--state", metavar="STATE_ID", help="看这一局的状态（不含牌面）")
    ap.add_argument("--list", action="store_true", help="列出本机所有局")
    ap.add_argument("--spread", default="three", help="牌阵名，默认 three")
    ap.add_argument("--cards", default=str(DEFAULT_CARDS), help="cards.json 路径")
    ap.add_argument("--spreads", default=str(DEFAULT_SPREADS), help="spreads.json 路径")
    ap.add_argument("--state-dir", help="state 存放目录（默认 <skill>/state 或 $TAROT_STATE_DIR）")
    args = ap.parse_args()

    if args.list:
        return cmd_list(args)

    cards = load_json(Path(args.cards), "先运行 python scripts/build_data.py 生成 cards.json")
    spreads = load_json(Path(args.spreads), "data/spreads.json 缺失")

    if args.new:
        return cmd_new(args, cards, spreads)
    if args.auto:
        return cmd_auto(args, cards, spreads)
    if args.reveal:
        return cmd_reveal(args, cards, find_state(args, args.reveal))
    if args.state:
        return cmd_state(args, find_state(args, args.state))

    print(json.dumps({"error": "没说干什么", "usage": [
        "python scripts/deal.py --new --spread three",
        "python scripts/deal.py --reveal <state_id> --picks 12,45,7",
        'python scripts/deal.py --auto --spread three --confirm-user-asked']}, ensure_ascii=False, indent=2))
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
