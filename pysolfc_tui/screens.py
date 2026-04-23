"""Modal screens: variant picker, help, win."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import ListItem, ListView, Static

from . import engine as E


_HELP_TEXT = """\
[b]pysolfc-tui — controls[/b]

[b yellow]Cursor[/b yellow]
  ←/→        Move cursor to next/prev stack
  ↑/↓        Move between top row and tableau
  Tab        Cycle through stacks

[b yellow]Actions[/b yellow]
  Enter /    Pick up cards / drop held cards
  Space      (empty stack + held cards → drop)
  Esc        Cancel current selection
  a          Auto-send top cards to foundations
  s          Flip stock → waste (or recycle)
  u          Undo last move
  n          Deal a new game of the current variant
  v          Open variant picker
  ?          This help screen
  q          Quit

[b yellow]Mouse[/b yellow]
  Click a card       Select that card + any legal
                     stack of cards above it.
  Click another      Drop held cards onto that stack.
                     Same stack = deselect.

[b yellow]Variants supported[/b yellow]
  Klondike       Turn 1 from stock; A→K suit on foundations.
  FreeCell       All face-up; 4 cells + 4 foundations.
  Spider (2s.)   Build K→A same-suit runs; 10 columns, 2 decks.
  Yukon          Klondike without stock; all rows face-up.
  Freecell-1     Like FreeCell but 1 cell (harder).
  Easthaven      Spider-ish but 7 rows, deal-one to all.
  Golf           Tableau → one waste; rank-adjacent only.

[dim]Press any key to close.[/dim]
"""


class HelpScreen(ModalScreen[None]):
    BINDINGS = [Binding("escape", "dismiss", show=False),
                Binding("q", "dismiss", show=False),
                Binding("?", "dismiss", show=False)]

    DEFAULT_CSS = """
    HelpScreen {
        align: center middle;
    }
    #help-box {
        width: 70%;
        max-width: 90;
        height: auto;
        max-height: 90%;
        border: round rgb(255,220,120);
        background: rgb(12,28,16);
        padding: 1 2;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="help-box"):
            yield Static(_HELP_TEXT)

    def on_key(self, event) -> None:  # dismiss on any key
        self.dismiss()


class VariantScreen(ModalScreen[str]):
    BINDINGS = [Binding("escape", "dismiss(None)", show=False),
                Binding("enter", "select", show=False)]

    DEFAULT_CSS = """
    VariantScreen {
        align: center middle;
    }
    #variant-box {
        width: 50%;
        max-width: 60;
        height: auto;
        border: round rgb(255,220,120);
        background: rgb(12,28,16);
        padding: 1 2;
    }
    ListView {
        height: auto;
        max-height: 20;
    }
    ListItem {
        padding: 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="variant-box"):
            yield Static("[b]Choose variant[/b]   (enter = select, esc = cancel)")
            items = [ListItem(Static(name)) for name in E.VARIANTS]
            self._list = ListView(*items, id="variant-list")
            yield self._list

    def action_select(self) -> None:
        idx = self._list.index or 0
        names = list(E.VARIANTS.keys())
        if 0 <= idx < len(names):
            self.dismiss(names[idx])
        else:
            self.dismiss(None)

    def on_list_view_selected(self, message: ListView.Selected) -> None:
        self.action_select()


class WinScreen(ModalScreen[bool]):
    """Celebrate a win. Press `n` to new-game, esc to dismiss."""

    BINDINGS = [Binding("escape", "dismiss(False)", show=False),
                Binding("n", "dismiss(True)", show=False),
                Binding("enter", "dismiss(True)", show=False)]

    DEFAULT_CSS = """
    WinScreen {
        align: center middle;
    }
    #win-box {
        width: 50%;
        max-width: 50;
        height: auto;
        border: heavy rgb(255,220,120);
        background: rgb(28,40,22);
        padding: 2 3;
    }
    #win-title {
        text-align: center;
        color: rgb(255,220,120);
        text-style: bold;
    }
    """

    def __init__(self, game: E.Game) -> None:
        super().__init__()
        self._game = game

    def compose(self) -> ComposeResult:
        stars = "✦  ✦  ✦  ✦  ✦"
        body = (
            f"{stars}\n\n"
            f"[b]YOU WON {self._game.name}![/b]\n\n"
            f"Moves: {self._game.moves_made}\n"
            f"Seed:  {self._game.seed}\n\n"
            f"{stars}\n\n"
            f"[dim]enter / n — new game\n"
            f"esc — dismiss[/dim]"
        )
        with Vertical(id="win-box"):
            yield Static(body, id="win-title")
