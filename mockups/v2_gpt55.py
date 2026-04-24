from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Iterable


WIDTH = 140
HEIGHT = 42

BG = "#06180e"
BG_DEEP = "#031007"
RAIL = "#082b17"
RAIL_DARK = "#051f10"
FELT_LINE = "#194c2a"
FELT_SOFT = "#2f5f39"
MUTED = "#6f8766"
TEXT = "#cfd6c2"
GOLD = "#ffd35c"
GOLD_DARK = "#8f6d23"
CREAM = "#eee8d8"
INK = "#102016"
RED = "#ef5350"
CARD_EDGE = "#1a2a1e"
CARD_SHADE = "#d7cfbd"
PURPLE_DARK = "#2b1138"
PURPLE_MID = "#511d66"
PURPLE_LIT = "#bc82db"
PURPLE_EDGE = "#d4a1ee"


@dataclass(frozen=True)
class CellStyle:
    fg: str | None = TEXT
    bg: str | None = BG
    bold: bool = False
    dim: bool = False

    def rich(self) -> str:
        parts: list[str] = []
        if self.bold:
            parts.append("bold")
        if self.dim:
            parts.append("dim")
        if self.fg:
            parts.append(self.fg)
        if self.bg:
            parts.append(f"on {self.bg}")
        return " ".join(parts)

    def ansi(self) -> str:
        return ""


DEFAULT = CellStyle(TEXT, BG)


class Grid:
    def __init__(self, width: int = WIDTH, height: int = HEIGHT) -> None:
        self.width = width
        self.height = height
        self.chars = [[" " for _ in range(width)] for _ in range(height)]
        self.styles = [[DEFAULT for _ in range(width)] for _ in range(height)]

    def put(
        self,
        x: int,
        y: int,
        text: str,
        fg: str | None = TEXT,
        bg: str | None = BG,
        *,
        bold: bool = False,
        dim: bool = False,
    ) -> None:
        if y < 0 or y >= self.height:
            return
        style = CellStyle(fg, bg, bold, dim)
        for offset, char in enumerate(text):
            xx = x + offset
            if 0 <= xx < self.width:
                self.chars[y][xx] = char
                self.styles[y][xx] = style

    def fill(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        char: str = " ",
        fg: str | None = TEXT,
        bg: str | None = BG,
        *,
        bold: bool = False,
        dim: bool = False,
    ) -> None:
        for yy in range(y, y + height):
            self.put(x, yy, char * width, fg, bg, bold=bold, dim=dim)

    def center(
        self,
        y: int,
        text: str,
        fg: str | None = TEXT,
        bg: str | None = BG,
        *,
        bold: bool = False,
        dim: bool = False,
    ) -> None:
        self.put((self.width - len(text)) // 2, y, text, fg, bg, bold=bold, dim=dim)

    def lines(self) -> Iterable[list[tuple[str, CellStyle]]]:
        for row, style_row in zip(self.chars, self.styles):
            yield list(zip(row, style_row))

    def plain(self) -> str:
        return "\n".join("".join(row).rstrip() for row in self.chars)


def draw_box(
    grid: Grid,
    x: int,
    y: int,
    width: int,
    height: int,
    *,
    fg: str,
    bg: str,
    fill_bg: str | None = None,
    dashed: bool = False,
) -> None:
    fill = bg if fill_bg is None else fill_bg
    grid.fill(x, y, width, height, " ", fg, fill)
    h = "┄" if dashed else "─"
    v = "┆" if dashed else "│"
    grid.put(x, y, "┌" + h * (width - 2) + "┐", fg, fill)
    for yy in range(y + 1, y + height - 1):
        grid.put(x, yy, v, fg, fill)
        grid.put(x + width - 1, yy, v, fg, fill)
    grid.put(x, y + height - 1, "└" + h * (width - 2) + "┘", fg, fill)


def draw_shadow(grid: Grid, x: int, y: int, width: int = 10, height: int = 6) -> None:
    grid.fill(x + 1, y + 1, width, height, " ", BG_DEEP, BG_DEEP)


def draw_back(grid: Grid, x: int, y: int) -> None:
    draw_shadow(grid, x, y)
    grid.fill(x, y, 10, 6, " ", PURPLE_LIT, PURPLE_DARK)
    grid.put(x, y, "╭────────╮", PURPLE_EDGE, PURPLE_DARK, bold=True)
    pattern = [
        "│░▒▓▒░░▓│",
        "│▒▓░░▓▒░│",
        "│░▓▒▒▓░▒│",
        "│▒░▓░▒▓░│",
    ]
    for row, line in enumerate(pattern, start=1):
        grid.put(x, y + row, line, PURPLE_LIT, PURPLE_DARK, bold=True)
    grid.put(x, y + 5, "╰────────╯", PURPLE_EDGE, PURPLE_DARK, bold=True)
    grid.put(x + 3, y + 2, "◆", GOLD, PURPLE_DARK, bold=True)
    grid.put(x + 6, y + 3, "◆", GOLD, PURPLE_DARK, bold=True)


def draw_empty_slot(grid: Grid, x: int, y: int, suit: str, *, hot: bool = False) -> None:
    is_red = suit in {"♥", "♦"}
    suit_fg = RED if is_red else CREAM
    draw_box(grid, x, y, 10, 6, fg=GOLD_DARK if hot else FELT_SOFT, bg=BG, dashed=True)
    grid.put(x + 1, y + 1, suit, suit_fg, BG, bold=True)
    grid.put(x + 8, y + 4, suit, suit_fg, BG, bold=True)
    grid.put(x + 4, y + 2, suit, suit_fg, BG, bold=True)
    grid.put(x + 3, y + 4, "ACE", MUTED, BG, dim=True)
    if hot:
        grid.put(x + 4, y + 6, "◆", GOLD, BG, bold=True)


def suit_color(suit: str) -> str:
    return RED if suit in {"♥", "♦"} else INK


def draw_face(
    grid: Grid,
    x: int,
    y: int,
    rank: str,
    suit: str,
    *,
    highlight: bool = False,
    ghost: bool = False,
) -> None:
    draw_shadow(grid, x, y)
    edge = GOLD if highlight else CARD_EDGE
    card_bg = CREAM if not ghost else CARD_SHADE
    grid.fill(x, y, 10, 6, " ", INK, card_bg)
    grid.put(x, y, "╭────────╮", edge, card_bg, bold=highlight)
    for yy in range(y + 1, y + 5):
        grid.put(x, yy, "│", edge, card_bg, bold=highlight)
        grid.put(x + 9, yy, "│", edge, card_bg, bold=highlight)
    grid.put(x, y + 5, "╰────────╯", edge, card_bg, bold=highlight)

    fg = suit_color(suit)
    rank_text = f"{rank}{suit}"
    grid.put(x + 1, y + 1, rank_text[:8].ljust(8), fg, card_bg, bold=True)
    grid.put(x + 3, y + 2, suit * 2 if rank not in {"A", "J", "Q", "K"} else suit, fg, card_bg, bold=True)
    grid.put(x + 4, y + 3, suit * 2 if rank in {"4", "9"} else suit, fg, card_bg, bold=True)
    grid.put(x + 1, y + 4, rank_text[:8].rjust(8), fg, card_bg, bold=True)


def draw_waste_stack(grid: Grid, x: int, y: int) -> None:
    draw_shadow(grid, x + 1, y + 1, 10, 6)
    draw_box(grid, x + 1, y + 1, 10, 6, fg=CARD_EDGE, bg=CARD_SHADE, fill_bg=CARD_SHADE)
    draw_face(grid, x, y, "2", "♣")


def draw_foundation_bar(grid: Grid) -> None:
    grid.put(82, 4, "FOUNDATIONS", MUTED, BG, bold=True)
    grid.put(114, 4, "0/52", GOLD, BG, bold=True)
    for x, suit in zip([74, 89, 104, 119], ["♠", "♥", "♦", "♣"]):
        draw_empty_slot(grid, x, 6, suit, hot=suit == "♦")


def draw_header(grid: Grid) -> None:
    grid.fill(0, 0, WIDTH, 2, " ", TEXT, RAIL_DARK)
    grid.put(3, 0, "◆ KLONDIKE", GOLD, RAIL_DARK, bold=True)
    grid.put(17, 0, "pysolfc-tui", MUTED, RAIL_DARK)
    grid.center(0, "TIME 00:00     MOVES 0", TEXT, RAIL_DARK, bold=True)
    grid.put(WIDTH - 18, 0, "SCORE 0/52", TEXT, RAIL_DARK, bold=True)
    grid.put(0, 1, "╞" + "═" * (WIDTH - 2) + "╡", FELT_LINE, RAIL_DARK)
    grid.fill(0, 2, WIDTH, 1, " ", TEXT, BG)


def draw_top_bank(grid: Grid) -> None:
    grid.put(6, 4, "STOCK 24", MUTED, BG, bold=True)
    draw_back(grid, 6, 6)
    grid.put(25, 4, "WASTE", MUTED, BG, bold=True)
    draw_waste_stack(grid, 24, 6)
    draw_foundation_bar(grid)
    grid.put(0, 13, " " * WIDTH, TEXT, BG)
    grid.put(6, 13, "╾" + "─" * 126 + "╼", FELT_LINE, BG)


def draw_tableau(grid: Grid) -> None:
    xs = [6, 26, 46, 66, 86, 106, 126]
    piles = [
        [("face", "2", "♣")],
        [("back", "", ""), ("face", "2", "♠")],
        [("back", "", ""), ("back", "", ""), ("face", "3", "♥")],
        [("back", "", ""), ("back", "", ""), ("back", "", ""), ("face", "9", "♦")],
        [("back", "", ""), ("back", "", ""), ("back", "", ""), ("back", "", ""), ("face", "J", "♣")],
        [("back", "", ""), ("back", "", ""), ("back", "", ""), ("back", "", ""), ("back", "", ""), ("face", "K", "♠")],
        [("back", "", ""), ("back", "", ""), ("back", "", ""), ("back", "", ""), ("back", "", ""), ("back", "", ""), ("face", "4", "♣")],
    ]
    for idx, (x, pile) in enumerate(zip(xs, piles), start=1):
        y = 15
        for card_index, card in enumerate(pile):
            kind, rank, suit = card
            top = card_index == len(pile) - 1
            if kind == "back":
                draw_back(grid, x, y)
                y += 1
            else:
                draw_face(grid, x, y, rank, suit, highlight=(rank, suit) == ("9", "♦"))
                y += 6 if top else 2
        label = f"#{idx}"
        grid.put(x + 4, 35, label, MUTED, BG, bold=True)

    grid.put(90, 34, "◆", GOLD, BG, bold=True)


def draw_bottom_dock(grid: Grid) -> None:
    grid.fill(0, 37, WIDTH, 5, " ", TEXT, RAIL_DARK)
    grid.put(0, 37, "╞" + "═" * (WIDTH - 2) + "╡", FELT_LINE, RAIL_DARK)
    pill = "╭─ HELD  9♦  from #9 ─╮"
    x = (WIDTH - len(pill)) // 2
    grid.put(x, 38, pill, GOLD, RAIL, bold=True)
    grid.put(x + 9, 38, "9♦", RED, RAIL, bold=True)
    hint = "Enter / Esc cancel      9♦ held      ← → cycle legal drops      F move to foundation"
    grid.center(40, hint, MUTED, RAIL_DARK)


def build_grid() -> Grid:
    grid = Grid()
    draw_header(grid)
    draw_top_bank(grid)
    draw_tableau(grid)
    draw_bottom_dock(grid)
    return grid


def render_rich_text():
    from rich.text import Text

    text = Text(no_wrap=True, overflow="crop")
    for y, row in enumerate(build_grid().lines()):
        index = 0
        while index < len(row):
            char, style = row[index]
            chars = [char]
            index += 1
            while index < len(row) and row[index][1] == style:
                chars.append(row[index][0])
                index += 1
            text.append("".join(chars), style.rich())
        if y != HEIGHT - 1:
            text.append("\n")
    return text


try:
    from textual.app import App, ComposeResult
    from textual.widget import Widget
except ModuleNotFoundError:
    App = None
    ComposeResult = object
    Widget = object


if App is not None:

    class SolitaireBoard(Widget):
        DEFAULT_CSS = """
        SolitaireBoard {
            width: 140;
            height: 42;
            overflow: hidden hidden;
        }
        """

        def render(self):
            return render_rich_text()

    class PySolFCMockup(App):
        CSS = """
        Screen {
            background: #06180e;
            align: center middle;
        }
        """
        BINDINGS = [("q", "quit", "Quit"), ("escape", "quit", "Quit")]

        def compose(self) -> ComposeResult:
            yield SolitaireBoard()

    app = PySolFCMockup()


def main() -> None:
    if App is None:
        sys.stderr.write(
            "Textual is not installed. Install textual>=0.80, then run:\n"
            "  PYTHONPATH=/tmp python3 -m pysolfc-mockup-v2\n\n"
            "Plain grid preview follows:\n\n"
        )
        print(build_grid().plain())
        return
    PySolFCMockup().run()


if __name__ == "__main__":
    main()
