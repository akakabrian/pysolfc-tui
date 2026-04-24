"""
Large-card Klondike solitaire UI prototype for Textual.

Install:
    pip install textual

Run:
    python mockups/large_card_ui.py

UI/layout prototype, not a full rules engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Static, Footer
from textual.reactive import reactive


RED_SUITS = {"♥", "♦"}
BLACK_SUITS = {"♠", "♣"}


@dataclass(frozen=True)
class Card:
    rank: str
    suit: str
    face_up: bool = True

    @property
    def red(self) -> bool:
        return self.suit in RED_SUITS

    @property
    def label(self) -> str:
        return f"{self.rank}{self.suit}"


class HelpScreen(ModalScreen[None]):
    BINDINGS = [
        ("escape", "dismiss", "Close"),
        ("question_mark", "dismiss", "Close"),
        ("q", "dismiss", "Close"),
    ]

    def compose(self) -> ComposeResult:
        yield Container(
            Static("KLONDIKE CONTROLS", id="help-title"),
            Static(
                """
Navigation
  ← / →          previous / next stack
  ↑ / ↓          top row / tableau
  Tab            cycle stacks

Actions
  Enter / Space  pick up / drop
  Esc            cancel held card
  s              flip stock → waste
  a              auto-send to foundation
  u              undo last move
  n              new game
  v              variant picker
  ?              show / hide help

Mouse
  click card      select stack/card
  click again     drop if legal
                """.strip(),
                id="help-body",
            ),
            id="help-dialog",
        )

    def action_dismiss(self) -> None:
        self.dismiss()


class CardWidget(Static):
    can_focus = True
    selected = reactive(False)

    def __init__(self, card: Optional[Card], *, placeholder: str = "", id: str | None = None) -> None:
        super().__init__(id=id)
        self.card = card
        self.placeholder = placeholder
        self.update_card()

    def watch_selected(self, selected: bool) -> None:
        self.set_class(selected, "selected")

    def update_card(self) -> None:
        if self.card is None:
            icon = self.placeholder or " "
            self.add_class("empty-card")
            self.update(
                "╭──────╮\n"
                "│      │\n"
                f"│  {icon}   │\n"
                "│      │\n"
                "╰──────╯"
            )
            return

        if not self.card.face_up:
            self.add_class("card-back")
            self.update(
                "╭──────╮\n"
                "│░░░░░░│\n"
                "│░▒▓▒░░│\n"
                "│░░░░░░│\n"
                "╰──────╯"
            )
            return

        self.add_class("face-card")
        self.set_class(self.card.red, "red-card")
        self.set_class(not self.card.red, "black-card")
        r = self.card.rank.ljust(2)
        s = self.card.suit
        self.update(
            f"╭──────╮\n"
            f"│{r}  {s} │\n"
            f"│  {s}   │\n"
            f"│ {s}  {r.strip():>2}│\n"
            f"╰──────╯"
        )


class StackWidget(Vertical):
    def __init__(self, cards: list[Card], *, stack_index: int, selected: bool = False) -> None:
        super().__init__(classes="tableau-stack")
        self.cards = cards
        self.stack_index = stack_index
        self.is_selected = selected

    def compose(self) -> ComposeResult:
        if not self.cards:
            yield CardWidget(None, placeholder="·")
            return

        hidden = [c for c in self.cards[:-1] if not c.face_up]
        visible = self.cards[-1]

        for _ in hidden[:5]:
            yield Static("╭──────╮", classes="compressed-back")

        card = CardWidget(visible)
        card.selected = self.is_selected
        yield card

        yield Static(f"   #{self.stack_index}", classes="stack-number")


class GameBoard(Container):
    def compose(self) -> ComposeResult:
        yield Horizontal(
            Static("◆ KLONDIKE ◆", id="title"),
            Static("MOVES: 2", id="moves"),
            Static("STOCK: 24   WASTE: 2♥", id="stock-waste"),
            id="top-hud",
        )

        yield Horizontal(
            CardWidget(Card("", "", False), id="stock"),
            CardWidget(Card("2", "♥"), id="waste"),
            Static("", id="top-spacer"),
            CardWidget(None, placeholder="♥", id="foundation-h"),
            CardWidget(None, placeholder="♦", id="foundation-d"),
            CardWidget(None, placeholder="♣", id="foundation-c"),
            CardWidget(None, placeholder="♠", id="foundation-s"),
            id="top-row",
        )

        stacks = [
            [Card("9", "♦")],
            [Card("J", "♦")],
            [Card("", "", False), Card("K", "♣")],
            [Card("", "", False), Card("", "", False), Card("8", "♠")],
            [Card("", "", False), Card("", "", False), Card("", "", False), Card("9", "♥")],
            [Card("", "", False), Card("", "", False), Card("", "", False), Card("", "", False), Card("2", "♠")],
            [Card("", "", False), Card("", "", False), Card("", "", False), Card("", "", False), Card("", "", False), Card("Q", "♠")],
        ]

        yield Horizontal(
            *(StackWidget(cards, stack_index=i + 1, selected=(i == 4)) for i, cards in enumerate(stacks)),
            id="tableau",
        )

        yield Static("Holding: 1 card from #5  (9♥)", id="holding-pill")

        yield Horizontal(
            Static("← →\nSelect", classes="hint"),
            Static("Enter\nPick / Drop", classes="hint primary-hint"),
            Static("Esc\nCancel", classes="hint"),
            Static("u\nUndo", classes="hint"),
            Static("s\nStock", classes="hint"),
            Static("?\nHelp", classes="hint"),
            id="command-strip",
        )

        yield Static("Enter: drop 9♥ on 8♠", id="context-action")


class SolitaireApp(App):
    CSS = r"""
    Screen {
        background: #07190f;
        color: #efe8d1;
    }

    GameBoard {
        width: 100%;
        height: 100%;
        padding: 1;
        border: round #375a2d;
        background: #07190f;
    }

    #top-hud {
        height: 3;
        border-bottom: solid #375a2d;
        margin-bottom: 1;
    }

    #title {
        width: 1fr;
        color: #ffd45a;
        text-style: bold;
        content-align: left middle;
    }

    #moves {
        width: 1fr;
        content-align: center middle;
        text-style: bold;
    }

    #stock-waste {
        width: 1fr;
        content-align: right middle;
        text-style: bold;
    }

    #top-row {
        height: 8;
        layout: horizontal;
        margin-bottom: 1;
    }

    #top-spacer {
        width: 1fr;
    }

    CardWidget {
        width: 10;
        height: 5;
        margin-right: 2;
        content-align: center middle;
        text-style: bold;
    }

    .face-card {
        color: #10170f;
        background: #eee8d8;
    }

    .red-card {
        color: #c83232;
    }

    .black-card {
        color: #112117;
    }

    .card-back {
        color: #bc82db;
        background: #31113f;
    }

    .empty-card {
        color: #355d31;
        background: #07190f;
    }

    .selected {
        border: heavy #ffd45a;
        tint: #ffd45a 10%;
    }

    #tableau {
        height: 1fr;
        width: 100%;
        align-horizontal: center;
    }

    .tableau-stack {
        width: 1fr;
        min-width: 10;
        max-width: 16;
        margin-right: 1;
        align-horizontal: center;
    }

    .compressed-back {
        width: 10;
        height: 1;
        color: #bc82db;
        background: #31113f;
        text-style: bold;
    }

    .stack-number {
        height: 1;
        color: #55754f;
        text-align: center;
    }

    #holding-pill {
        height: 3;
        width: 1fr;
        content-align: center middle;
        text-align: center;
        color: #efe8d1;
        background: #0e2414;
        border: round #375a2d;
        margin: 0 16 1 16;
    }

    #command-strip {
        height: 5;
        border: round #375a2d;
        background: #0a1d11;
        margin-bottom: 1;
    }

    .hint {
        width: 1fr;
        content-align: center middle;
        color: #efe8d1;
    }

    .primary-hint {
        color: #ffd45a;
        text-style: bold;
    }

    #context-action {
        height: 1;
        color: #efe8d1;
        text-align: center;
        text-style: bold;
    }

    Footer {
        display: none;
    }

    HelpScreen {
        align: center middle;
        background: #000000 60%;
    }

    #help-dialog {
        width: 64;
        height: auto;
        padding: 1 2;
        border: round #ffd45a;
        background: #07190f;
    }

    #help-title {
        height: 1;
        color: #ffd45a;
        text-style: bold;
        text-align: center;
        margin-bottom: 1;
    }

    #help-body {
        color: #efe8d1;
    }
    """

    BINDINGS = [
        ("question_mark", "help", "Help"),
        ("q", "quit", "Quit"),
        ("escape", "cancel", "Cancel"),
        ("u", "noop", "Undo"),
        ("s", "noop", "Stock"),
        ("enter", "noop", "Pick/Drop"),
        ("space", "noop", "Pick/Drop"),
    ]

    def compose(self) -> ComposeResult:
        yield GameBoard()
        yield Footer()

    def action_help(self) -> None:
        self.push_screen(HelpScreen())

    def action_cancel(self) -> None:
        pass

    def action_noop(self) -> None:
        pass


if __name__ == "__main__":
    SolitaireApp().run()
