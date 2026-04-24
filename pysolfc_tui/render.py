"""Card → Rich Text rendering primitives.

Cards render as 5-wide × 4-tall bordered glyphs:

    ╭───╮
    │ K♠│
    │ ♠ │
    ╰───╯

Fan stacks (tableau rows) overlap vertically — non-top cards expose only
their top 2 rows, while the topmost card shows all 4 rows. Face-down
cards render as a shaded back. Stock, waste, foundations all share the
same 5×4 footprint.
"""

from __future__ import annotations

from rich.style import Style

from .engine import Card, Stack

CARD_W = 5
CARD_H = 4
FAN_OFFSET = 2  # tableau fan step (rows for every non-top card)

# Palette
COL_BG_DARK = "rgb(18,28,18)"
COL_CARD_BG = "rgb(248,244,230)"    # cream parchment
COL_CARD_BACK = "rgb(70,30,90)"
COL_RED = "rgb(200,40,40)"
COL_BLACK = "rgb(20,20,20)"
COL_BORDER = "rgb(40,35,30)"
COL_EMPTY = "rgb(60,60,60)"
COL_SELECT = "rgb(255,220,80)"
COL_HIGHLIGHT = "rgb(100,200,120)"
COL_CURSOR = "rgb(80,200,255)"

STYLE_CARD_RED = Style.parse(f"bold {COL_RED} on {COL_CARD_BG}")
STYLE_CARD_BLACK = Style.parse(f"bold {COL_BLACK} on {COL_CARD_BG}")
STYLE_CARD_BORDER = Style.parse(f"{COL_BORDER} on {COL_CARD_BG}")
STYLE_BACK = Style.parse(f"{COL_CARD_BACK} on rgb(40,20,55)")
STYLE_EMPTY = Style.parse(f"{COL_EMPTY} on {COL_BG_DARK}")
STYLE_SELECT = Style.parse(f"bold {COL_SELECT} on {COL_CARD_BG}")
STYLE_HIGHLIGHT = Style.parse(f"bold {COL_HIGHLIGHT}")
STYLE_CURSOR = Style.parse(f"bold {COL_CURSOR}")


def _rank_label(card: Card) -> str:
    """2-character right-justified rank (' A', '10', ' K')."""
    r = card.rank_label
    return r if len(r) == 2 else (" " + r)


def _card_sprite_rows(card: Card | None) -> tuple[str, str, str, str]:
    """Return the 4 text rows for a card face or a card back sprite."""
    if card is None:
        return ("╭───╮", "│▒▒▒│", "│▒▒▒│", "╰───╯")
    rank = _rank_label(card)
    glyph = card.glyph
    return ("╭───╮", f"│{rank}{glyph}│", f"│ {glyph} │", "╰───╯")


def card_face_rows(card: Card, selected: bool = False) -> list[tuple[str, Style]]:
    """Return 4 rows × (text, style) for a face-up card."""
    bcolor = COL_SELECT if selected else COL_BORDER
    border_style = Style.parse(f"bold {bcolor} on {COL_CARD_BG}")
    suit_style = STYLE_CARD_RED if card.is_red else STYLE_CARD_BLACK
    sprite = _card_sprite_rows(card)
    return [
        (sprite[0], border_style),
        (sprite[1], suit_style),
        (sprite[2], suit_style),
        (sprite[3], border_style),
    ]


def card_back_rows(selected: bool = False) -> list[tuple[str, Style]]:
    bcolor = COL_SELECT if selected else COL_CARD_BACK
    border_style = Style.parse(f"bold {bcolor} on rgb(40,20,55)")
    body_style = Style.parse("rgb(150,90,170) on rgb(50,25,70)")
    sprite = _card_sprite_rows(None)
    return [
        (sprite[0], border_style),
        (sprite[1], body_style),
        (sprite[2], body_style),
        (sprite[3], border_style),
    ]


def empty_slot_rows(label: str = "", selected: bool = False) -> list[tuple[str, Style]]:
    """Rendering for an empty stack — dashed outline, optional 1-char hint."""
    bcolor = COL_SELECT if selected else COL_EMPTY
    border_style = Style.parse(f"{bcolor} on {COL_BG_DARK}")
    ch = label[:1].center(3) if label else "   "
    return [
        ("┌╌╌╌┐", border_style),
        ("╎   ╎", border_style),
        (f"╎{ch}╎", border_style),
        ("└╌╌╌┘", border_style),
    ]


# Height helpers for fanned stacks.
def stack_height(stack: Stack) -> int:
    """How many rows this stack consumes when rendered fanned."""
    if not stack.cards:
        return CARD_H
    # Each non-top card contributes FAN_OFFSET rows; topmost shows full CARD_H.
    return (len(stack.cards) - 1) * FAN_OFFSET + CARD_H
