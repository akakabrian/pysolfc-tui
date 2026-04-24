# /tmp/pysolfc-mockup-v2.py
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Static


BG = "#07190f"
PANEL = "#0b2416"
LINE = "#6f845f"
LINE_DIM = "#50664a"
SAGE = "#7f936f"
CREAM = "#eee8d8"
GOLD = "#f1c84c"
RED = "#e05a56"
RED2 = "#ff6b67"
BLACK_CARD = "#1d2b1f"
PURPLE = "#bc82db"
PURPLE_DARK = "#31113f"
SELECT_BG = "#12351d"


def fit_block(text: str, width: int, height: int) -> str:
    lines = text.splitlines()
    lines = [ln[:width].ljust(width) for ln in lines[:height]]
    while len(lines) < height:
        lines.append(" " * width)
    return "\n".join(lines)


class CardFace(Static):
    def __init__(self, rank: str, suit: str, color: str = "black", selected: bool = False, id: str | None = None):
        super().__init__("", id=id)
        self.rank = rank
        self.suit = suit
        self.card_color = color
        self.selected = selected

    def on_mount(self) -> None:
        pip = self.suit
        text = "\n".join(
            [
                f"{self.rank:<2}      {pip}",
                "",
                f"   {pip}   {pip}",
                "",
                f"{pip}      {self.rank:>2}",
            ]
        )
        self.update(fit_block(text, 8, 5))
        self.set_class(self.card_color == "red", "red")
        if self.selected:
            self.add_class("selected")


class CardBack(Static):
    def __init__(self, mode: str = "full", id: str | None = None):
        super().__init__("", id=id)
        self.mode = mode

    def on_mount(self) -> None:
        if self.mode == "full":
            text = "\n".join(
                [
                    "▒▓▓▒▒▓▓▒",
                    "▓▒▒▓▓▒▒▓",
                    "▒▓▓▒▒▓▓▒",
                    "▓▒▒▓▓▒▒▓",
                    "▒▓▓▒▒▓▓▒",
                ]
            )
            self.update(fit_block(text, 8, 5))
        else:
            self.update("")


class Lip(Static):
    def __init__(self, text: str = "", full: bool = False, id: str | None = None):
        super().__init__(text, id=id)
        self.full = full

    def on_mount(self) -> None:
        if self.full:
            self.add_class("full_lip")
        else:
            self.add_class("lip")


class Slot(Static):
    def __init__(self, suit: str, suit_class: str = "", id: str | None = None):
        super().__init__(suit, id=id)
        if suit_class:
            self.add_class(suit_class)


class MockupApp(App):
    CSS = f"""
    Screen {{
        background: {BG};
        color: {CREAM};
        layout: vertical;
    }}

    #root {{
        width: 100%;
        height: 100%;
        background: {BG};
        padding: 1;
    }}

    .rule {{
        height: 1;
        color: {LINE};
        background: {BG};
    }}

    #hud {{
        height: 3;
        border: tall {LINE};
        background: {PANEL};
        layout: horizontal;
        padding: 0 2;
        content-align: center middle;
    }}

    .hud_cell {{
        width: 1fr;
        content-align: center middle;
        color: {CREAM};
        text-style: bold;
    }}

    #title {{
        color: {GOLD};
        content-align: left middle;
    }}

    #score {{
        content-align: right middle;
    }}

    .sep {{
        width: 7;
        content-align: center middle;
        color: {SAGE};
    }}

    #zones {{
        height: 12;
        layout: horizontal;
        margin-top: 1;
    }}

    .zone {{
        height: 100%;
        border: tall {LINE};
        background: {BG};
        margin-right: 1;
        padding: 1 2;
    }}

    #draw_zone {{
        width: 41;
    }}

    #foundation_zone {{
        width: 1fr;
        margin-right: 0;
    }}

    .zone_title {{
        dock: top;
        height: 1;
        color: {SAGE};
        text-style: bold;
        content-align: center middle;
    }}

    .zone_body {{
        layout: horizontal;
        height: 1fr;
        margin-top: 1;
    }}

    .stack_wrap {{
        width: 16;
        height: 100%;
        layout: vertical;
    }}

    .stack_label {{
        height: 1;
        color: {SAGE};
        text-style: bold;
        margin-left: 2;
    }}

    .stack_area {{
        height: 8;
        width: 12;
        margin-top: 1;
        margin-left: 1;
    }}

    .slot_box {{
        width: 12;
        height: 8;
        border: dashed {LINE};
        content-align: center middle;
        color: {CREAM};
    }}

    .slot_red {{
        color: {RED2};
    }}

    .rail {{
        width: 3;
        color: {LINE};
        content-align: center middle;
        padding-top: 4;
    }}

    #tableau_title {{
        height: 2;
        layout: horizontal;
        content-align: center middle;
        margin-top: 1;
    }}

    .rule_fill {{
        width: 1fr;
        height: 1;
        background: {BG};
        color: {LINE};
    }}

    #tableau_title_text {{
        width: 13;
        content-align: center middle;
        color: {SAGE};
        text-style: bold;
    }}

    #tableau {{
        height: 18;
        layout: horizontal;
        margin-top: 1;
    }}

    .col {{
        width: 1fr;
        height: 100%;
        layout: vertical;
        align: center top;
    }}

    .stack {{
        width: 12;
        height: 13;
        layout: vertical;
        align: center top;
    }}

    .selected_stack {{
        background: {SELECT_BG};
    }}

    .card {{
        width: 10;
        height: 6;
        border: tall #4f5544;
        background: {CREAM};
        color: {BLACK_CARD};
        padding: 0 1;
    }}

    .card.red {{
        color: {RED};
    }}

    .card.selected {{
        border: double {GOLD};
    }}

    .back {{
        width: 10;
        height: 6;
        border: tall {PURPLE};
        background: {PURPLE_DARK};
        color: {PURPLE};
        padding: 0 1;
    }}

    .lip {{
        width: 10;
        height: 1;
        border-top: tall {PURPLE};
        border-left: tall {PURPLE};
        border-right: tall {PURPLE};
        background: {PURPLE_DARK};
        color: {PURPLE};
        padding: 0 1;
        margin-bottom: 0;
    }}

    .full_lip {{
        width: 10;
        height: 2;
        border-top: tall #4f5544;
        border-left: tall #4f5544;
        border-right: tall #4f5544;
        background: {CREAM};
        color: {BLACK_CARD};
        padding: 0 1;
        margin-bottom: 0;
    }}

    .col_label {{
        height: 1;
        color: {SAGE};
        text-style: bold;
        content-align: center middle;
        margin-top: 1;
    }}

    #bottom_wrap {{
        margin-top: 2;
        height: 6;
        layout: vertical;
    }}

    #held_bar {{
        height: 3;
        border: tall {LINE};
        background: {PANEL};
        content-align: center middle;
    }}

    #held_badge {{
        width: 24;
        height: 3;
        border: tall {GOLD};
        background: #20321c;
        color: {GOLD};
        text-style: bold;
        content-align: center middle;
    }}

    #help_bar {{
        height: 3;
        border: tall {LINE};
        background: {BG};
        color: {SAGE};
        content-align: center middle;
        margin-top: 1;
    }}
    """

    def compose(self) -> ComposeResult:
        with Container(id="root"):
            with Horizontal(id="hud"):
                yield Static("◆ KLONDIKE ◆", id="title", classes="hud_cell")
                yield Static("TIME 0:00", classes="hud_cell")
                yield Static("···", classes="sep")
                yield Static("MOVES 0", classes="hud_cell")
                yield Static("···", classes="sep")
                yield Static("SCORE 0/52", id="score", classes="hud_cell")

            with Horizontal(id="zones"):
                with Vertical(id="draw_zone", classes="zone"):
                    yield Static("DRAW", classes="zone_title")
                    with Horizontal(classes="zone_body"):
                        with Vertical(classes="stack_wrap"):
                            yield Static("STOCK 24", classes="stack_label")
                            with Container(classes="stack_area"):
                                back = CardBack(mode="full")
                                back.add_class("back")
                                yield back
                        with Vertical(classes="stack_wrap"):
                            yield Static("WASTE", classes="stack_label")
                            with Container(classes="stack_area"):
                                slot = Slot("♦")
                                slot.add_class("slot_box")
                                yield slot

                with Vertical(id="foundation_zone", classes="zone"):
                    yield Static("FOUNDATIONS", classes="zone_title")
                    with Horizontal(classes="zone_body"):
                        s1 = Slot("♠")
                        s1.add_class("slot_box")
                        yield s1
                        yield Static("│", classes="rail")
                        s2 = Slot("♥", "slot_red")
                        s2.add_class("slot_box")
                        yield s2
                        yield Static("│", classes="rail")
                        s3 = Slot("♦", "slot_red")
                        s3.add_class("slot_box")
                        yield s3
                        yield Static("│", classes="rail")
                        s4 = Slot("♣")
                        s4.add_class("slot_box")
                        yield s4

            with Horizontal(id="tableau_title"):
                yield Static("─" * 30, classes="rule_fill")
                yield Static("TABLEAU", id="tableau_title_text")
                yield Static("─" * 30, classes="rule_fill")

            with Horizontal(id="tableau"):
                yield self.make_col("1", [], CardFace("2", "♣"))
                yield self.make_col("2", [Lip()], CardFace("2", "♠"))
                yield self.make_col("3", [Lip(), Lip()], CardFace("3", "♥", color="red"))
                yield self.make_col("4", [Lip(), Lip(), Lip()], CardFace("9", "♦", color="red", selected=True), selected=True)
                yield self.make_col("5", [Lip(), Lip(), Lip(), Lip()], CardFace("J", "♣"))
                yield self.make_col("6", [Lip(), Lip(), Lip(), Lip(), Lip()], CardFace("K", "♠"))
                yield self.make_col("7", [Lip(), Lip(), Lip(), Lip(), Lip(), Lip()], CardFace("4", "♣"))

            with Vertical(id="bottom_wrap"):
                with Container(id="held_bar"):
                    yield Static("HELD  9♦  from #9", id="held_badge")
                yield Static("Enter: drop   •   Esc: cancel   •   ← →: cycle legal drops", id="help_bar")

    def make_col(self, num: str, lips: list[Lip], face: CardFace, selected: bool = False) -> Vertical:
        col = Vertical(classes="col")
        stack = Vertical(classes="stack")
        if selected:
            stack.add_class("selected_stack")
        for lip in lips:
            stack.mount(lip)
        face.add_class("card")
        stack.mount(face)
        col.mount(stack)
        col.mount(Static(f"#{num}", classes="col_label"))
        return col


if __name__ == "__main__":
    MockupApp().run()