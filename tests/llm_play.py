"""LLM-play harness — an OpenRouter cheap model plays Klondike solitaire.

Serializes game state as ASCII, asks the model for a JSON move, applies
via the engine API (bypassing the Textual layer so we're testing pure
game logic, not UI). Loops until: won, 3 consecutive illegal/stuck
moves, give_up, or 50 turns.

    .venv/bin/python -m tests.llm_play
    .venv/bin/python -m tests.llm_play --variant FreeCell --model openai/gpt-5-mini

Key at ~/.config/llm-keys/env (OPENROUTER_API_KEY).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

import urllib.request

from pysolfc_tui import engine as E


def load_key() -> str:
    env = Path.home() / ".config/llm-keys/env"
    if not env.exists():
        sys.exit(f"no key file at {env}")
    for line in env.read_text().splitlines():
        m = re.match(r"(?:export\s+)?OPENROUTER_API_KEY=['\"]?([^'\"]+)['\"]?", line)
        if m:
            return m.group(1).strip()
    sys.exit("OPENROUTER_API_KEY not found in " + str(env))


def describe_state(g: E.Game) -> str:
    lines = [f"VARIANT: {g.name}  MOVES: {g.moves_made}"]
    if g.talon is not None:
        lines.append(f"STOCK (sid={g.talon.sid}): {len(g.talon.cards)} cards face-down")
    if g.waste is not None:
        top = g.waste.cards[-1] if g.waste.cards else None
        tip = f"{top.rank_label}{top.glyph}" if top else "empty"
        lines.append(f"WASTE (sid={g.waste.sid}): {tip}  ({len(g.waste.cards)} total)")
    for i, f in enumerate(g.foundations):
        top = f.cards[-1] if f.cards else None
        tip = f"{top.rank_label}{top.glyph}" if top else "empty"
        suit = E.SUIT_GLYPHS.get(getattr(f, "suit", -1), "?")
        lines.append(f"FOUNDATION {suit} (sid={f.sid}): {tip}  ({len(f.cards)}/13)")
    for i, c in enumerate(g.cells):
        top = c.cards[-1] if c.cards else None
        tip = f"{top.rank_label}{top.glyph}" if top else "empty"
        lines.append(f"CELL {i + 1} (sid={c.sid}): {tip}")
    for i, r in enumerate(g.rows):
        hidden = sum(1 for c in r.cards if not c.face_up)
        visible = [f"{c.rank_label}{c.glyph}" for c in r.cards if c.face_up]
        lines.append(f"ROW {i + 1} (sid={r.sid}): {hidden} hidden + {' '.join(visible) or '(empty)'}")
    return "\n".join(lines)


SYSTEM_PROMPT = """You are a Klondike solitaire player. Every turn you receive the current board state and respond with a single JSON object — no prose, no markdown fences.

Allowed actions:
  {"src": <sid>, "dst": <sid>, "n": <int>, "note": "..."}        -- move n cards from src stack to dst stack
  {"action": "flip_stock", "note": "..."}                         -- draw next card from stock to waste
  {"action": "auto_send", "note": "..."}                          -- send every legal card to foundations in one pass
  {"action": "give_up", "note": "..."}                            -- admit defeat

Klondike rules:
  - Foundations build up by suit from A to K.
  - Tableau builds down by rank, alternating color (red/black).
  - Only a K or a multi-card run starting with K can move onto an empty tableau row.
  - Waste top is the only playable waste card.

Prefer moves that reveal a face-down card. Clear tableau rows for kings. When stuck, flip_stock.
"""


def ask_llm(key: str, model: str, state_text: str) -> dict:
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": state_text},
        ],
        # gpt-5-mini burns ~800 tokens on hidden reasoning before it
        # even starts writing content. Give it plenty of headroom.
        "max_tokens": 2500,
        "temperature": 0.3,
    }
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/akakabrian/pysolfc-tui",
            "X-Title": "pysolfc-tui LLM playtest",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    choice = data.get("choices", [{}])[0]
    raw = (choice.get("message") or {}).get("content") or ""
    if not raw:
        return {"action": "give_up", "note": f"empty response: {json.dumps(data)[:200]}"}
    m = re.search(r"\{[^{}]*\}", raw, re.DOTALL)
    if not m:
        return {"action": "give_up", "note": f"unparseable: {raw[:120]}"}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError as e:
        return {"action": "give_up", "note": f"bad json ({e}): {m.group(0)[:120]}"}


def apply_move(g: E.Game, mv: dict) -> tuple[bool, str]:
    action = mv.get("action")
    if action == "flip_stock":
        return g.flip_stock(), "flip_stock"
    if action == "auto_send":
        sent = 0
        pool = [s for s in (g.waste, *g.rows, *g.cells) if s is not None]
        for s in pool:
            if g.auto_send(s) is not None:
                sent += 1
        return bool(sent), f"auto_send x{sent}"
    if action == "give_up":
        return False, "give_up"
    src_sid = mv.get("src")
    dst_sid = mv.get("dst")
    n = int(mv.get("n", 1))
    if src_sid is None or dst_sid is None:
        return False, f"bad mv {mv}"
    if not (0 <= src_sid < len(g.stacks)) or not (0 <= dst_sid < len(g.stacks)):
        return False, f"sid oob {mv}"
    src, dst = g.stacks[src_sid], g.stacks[dst_sid]
    ok = g.move(src, dst, n)
    return ok, f"move {n} from #{src_sid} to #{dst_sid}"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--variant", default="Klondike", choices=list(E.VARIANTS))
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--model", default="openai/gpt-5-mini")
    p.add_argument("--max-turns", type=int, default=30)
    args = p.parse_args()

    key = load_key()
    g = E.VARIANTS[args.variant](seed=args.seed)
    print(f"# {args.model} playing {args.variant} (seed={args.seed})")

    illegal_streak = 0
    for turn in range(1, args.max_turns + 1):
        state = describe_state(g)
        try:
            mv = ask_llm(key, args.model, state)
        except Exception as e:
            print(f"turn {turn}: LLM error: {e}")
            break
        ok, desc = apply_move(g, mv)
        print(f"turn {turn:>2}: {desc}  -> {'ok' if ok else 'ILLEGAL'}  | {mv.get('note', '')[:60]}")
        if mv.get("action") == "give_up":
            break
        if ok:
            illegal_streak = 0
        else:
            illegal_streak += 1
            if illegal_streak >= 3:
                print("aborting: 3 illegal moves in a row")
                break
        if g.is_won():
            print("WON")
            break

    print("\n# final")
    print(f"moves={g.moves_made}")
    print(f"foundations={sum(len(f.cards) for f in g.foundations)}/52")
    print(f"won={g.is_won()}")


if __name__ == "__main__":
    main()
