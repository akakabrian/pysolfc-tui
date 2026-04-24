"""Card → Rich Text rendering primitives.

Two sprite sizes for visual hierarchy:
    - Tableau (10 × 6)       large, playfield-dominant
    - Top row (10 × 4)       compact stock/waste/foundation footprint

Fan stacks (tableau rows) overlap vertically:
    - Face-down card: 1-row lip only (compressed deck look)
    - Face-up non-top: 2-row lip + rank/suit row (readable run)
    - Topmost card:    full CARD_H
"""

from __future__ import annotations

from rich.style import Style

from .engine import Card, Stack

CARD_W = 10
CARD_H = 6            # card height (uniform across top row + tableau)
CARD_H_TOP = CARD_H   # kept as an alias for layout math
FAN_UP = 2            # rows exposed per fanned face-up card
FAN_DOWN = 1          # rows exposed per fanned face-down card
# Back-compat alias (older callers); default to the face-up offset.
FAN_OFFSET = FAN_UP

# Palette (mockup-aligned)
COL_BG_DARK = "rgb(7,25,15)"
COL_CARD_BG = "rgb(238,232,216)"
COL_CARD_BACK = "rgb(188,130,219)"
COL_BACK_FILL = "rgb(49,17,63)"
COL_RED = "rgb(200,50,50)"
COL_BLACK = "rgb(17,33,23)"
COL_BORDER = "rgb(40,35,30)"
COL_EMPTY = "rgb(85,117,79)"
COL_SELECT = "rgb(255,212,90)"
COL_LEGAL = "rgb(130,220,140)"          # glow for legal drop targets
COL_LEGAL_FILL = "rgb(18,45,22)"        # subtle inner wash so it reads as active
COL_HINT_RED = "rgb(230,110,110)"       # bright empty-foundation suit
COL_HINT_BLACK = "rgb(210,210,200)"     # bright empty-foundation suit (clubs/spades)
COL_HIGHLIGHT = "rgb(100,200,120)"
COL_CURSOR = "rgb(120,220,255)"

STYLE_CARD_RED = Style.parse(f"bold {COL_RED} on {COL_CARD_BG}")
STYLE_CARD_BLACK = Style.parse(f"bold {COL_BLACK} on {COL_CARD_BG}")
STYLE_CARD_BORDER = Style.parse(f"{COL_BORDER} on {COL_CARD_BG}")
STYLE_BACK = Style.parse(f"{COL_CARD_BACK} on {COL_BACK_FILL}")
STYLE_EMPTY = Style.parse(f"{COL_EMPTY} on {COL_BG_DARK}")
STYLE_SELECT = Style.parse(f"bold {COL_SELECT} on {COL_CARD_BG}")
STYLE_HIGHLIGHT = Style.parse(f"bold {COL_HIGHLIGHT}")
STYLE_CURSOR = Style.parse(f"bold {COL_CURSOR}")


def _rank_pair(card: Card) -> tuple[str, str]:
    """(left-justified, right-justified) 2-char rank labels."""
    r = card.rank_label
    return r.ljust(2), r.rjust(2)


def _face_sprite_tableau(card: Card) -> tuple[str, str, str, str, str, str]:
    rl, rr = _rank_pair(card)
    g = card.glyph
    return (
        "╭────────╮",
        f"│{rl}     {g}│",
        f"│   {g}{g}   │",
        f"│   {g}{g}   │",
        f"│{g}     {rr}│",
        "╰────────╯",
    )


_BACK_SPRITE_TABLEAU = (
    "╭────────╮",
    "│▒▓████▓▒│",
    "│░▒▓██▓▒░│",
    "│░▒▓██▓▒░│",
    "│▒▓████▓▒│",
    "╰────────╯",
)


def _pick_border_color(selected: bool, legal_drop: bool,
                       default: str) -> str:
    if selected:
        return COL_SELECT
    if legal_drop:
        return COL_LEGAL
    return default


def card_face_rows(card: Card, selected: bool = False, legal_drop: bool = False,
                   top: bool = False) -> list[tuple[str, Style]]:
    del top
    bcolor = _pick_border_color(selected, legal_drop, COL_BORDER)
    border_style = Style.parse(f"bold {bcolor} on {COL_CARD_BG}")
    suit_style = STYLE_CARD_RED if card.is_red else STYLE_CARD_BLACK
    s = _face_sprite_tableau(card)
    return [
        (s[0], border_style),
        (s[1], suit_style),
        (s[2], suit_style),
        (s[3], suit_style),
        (s[4], suit_style),
        (s[5], border_style),
    ]


def card_back_rows(selected: bool = False, legal_drop: bool = False,
                   top: bool = False) -> list[tuple[str, Style]]:
    del top
    bcolor = _pick_border_color(selected, legal_drop, COL_CARD_BACK)
    border_style = Style.parse(f"bold {bcolor} on {COL_BACK_FILL}")
    body_style = Style.parse(f"{COL_CARD_BACK} on {COL_BACK_FILL}")
    rows: list[tuple[str, Style]] = []
    for i, row in enumerate(_BACK_SPRITE_TABLEAU):
        style = border_style if i == 0 or i == len(_BACK_SPRITE_TABLEAU) - 1 else body_style
        rows.append((row, style))
    return rows


_SUIT_HINT_COLOR = {
    "♥": COL_HINT_RED,
    "♦": COL_HINT_RED,
    "♣": COL_HINT_BLACK,
    "♠": COL_HINT_BLACK,
}


def empty_slot_rows(label: str = "", selected: bool = False,
                    legal_drop: bool = False,
                    top: bool = False) -> list[tuple[str, Style]]:
    del top
    bcolor = _pick_border_color(selected, legal_drop, COL_EMPTY)
    bg = COL_LEGAL_FILL if legal_drop else COL_BG_DARK
    border_style = Style.parse(f"{bcolor} on {bg}")
    ch = (label[:1] if label else " ")
    # Brighten the glyph row so foundation suits + special placeholders
    # actually read on dark felt.
    glyph_color = _SUIT_HINT_COLOR.get(ch, COL_HINT_BLACK if ch in ("▶", "◆", "★", "·") else COL_EMPTY)
    glyph_style = Style.parse(f"bold {glyph_color} on {bg}")
    middle = ch.center(8)
    return [
        ("┌╌╌╌╌╌╌╌╌┐", border_style),
        ("╎        ╎", border_style),
        ("╎        ╎", border_style),
        (f"╎{middle}╎", glyph_style),
        ("╎        ╎", border_style),
        ("└╌╌╌╌╌╌╌╌┘", border_style),
    ]


def stack_height(stack: Stack) -> int:
    """How many rows a fanned tableau stack consumes with per-card offsets."""
    if not stack.cards:
        return CARD_H
    h = 0
    for c in stack.cards[:-1]:
        h += FAN_UP if c.face_up else FAN_DOWN
    h += CARD_H
    return h
