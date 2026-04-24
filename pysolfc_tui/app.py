"""Textual app — solitaire TUI.

Layout:
    ┌─ tableau ─────────────┬─ status ─┐
    │  [stock][waste]  [F][F][F][F]    │
    │                                  │
    │  col0 col1 col2 col3 col4 col5 col6
    │                         │ legend │
    │                         │        │
    └─────────────────────────┴────────┘
                    │          log     │
                    └──────────────────┘

Cursor selects a stack; enter/space picks up the top card (or a legal
group); second enter drops onto the cursor's current stack. Mouse clicks
do the same — click on a card stack to select/drop. `s` flips stock,
`u` undoes, `n` deals a new game, `v` opens the variant picker.
"""

from __future__ import annotations

from dataclasses import dataclass

from rich.segment import Segment
from rich.style import Style
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.geometry import Size
from textual.reactive import reactive
from textual.scroll_view import ScrollView
from textual.strip import Strip
from textual.widgets import Footer, Header, RichLog, Static

from . import engine as E
from . import render as R
from .screens import HelpScreen, VariantScreen, WinScreen

# --- layout constants ---
COL_W = R.CARD_W + 1       # 1-col gap between cards
COL_H_MARGIN = 1           # blank row between top row (stock/found) and tableau
TABLEAU_TOP = R.CARD_H + COL_H_MARGIN


@dataclass
class StackSlot:
    """Where a stack lives on the tableau canvas."""
    sid: int
    col: int    # grid column (0..)
    row: int    # grid row (0 = top, 1 = tableau)
    x: int      # pixel (char) origin x
    y: int      # pixel (char) origin y


class TableauView(ScrollView):
    """Main game canvas. Renders cards via `render_line`."""

    # Keep the selection reactive so status panel can react.
    cursor_sid: reactive[int] = reactive(0)
    selected_sid: reactive[int | None] = reactive(None)
    selected_from: reactive[int] = reactive(0)  # idx inside stack

    def __init__(self) -> None:
        super().__init__()
        self.game: E.Game | None = None
        self.slots: list[StackSlot] = []
        # sid → slot lookup
        self._slot_for: dict[int, StackSlot] = {}
        # canvas dims
        self._canvas_w = 10
        self._canvas_h = 10

    # -- setup --
    def load_game(self, game: E.Game) -> None:
        self.game = game
        self._layout_slots()
        self.virtual_size = Size(self._canvas_w, self._canvas_h)
        # Default cursor on first row (stock if present, else first row).
        self.cursor_sid = self.slots[0].sid if self.slots else 0
        self.selected_sid = None
        self.refresh()

    def _layout_slots(self) -> None:
        """Compute slot positions for the current game's stacks."""
        assert self.game is not None
        g = self.game
        slots: list[StackSlot] = []
        # Row 0: stock, waste, gap, foundations OR cells, foundations.
        #  Klondike: [stock][waste] ... [F][F][F][F]
        #  FreeCell: [c][c][c][c] [F][F][F][F]
        #  Spider:   [F*8] ...... [stock]
        col = 0
        top_stacks: list[E.Stack | None] = []
        if isinstance(g, E.Spider):
            # Foundations on the left, stock on the right.
            top_stacks.extend(g.foundations)
            top_stacks.append(g.talon)
        elif isinstance(g, E.FreeCell):
            top_stacks.extend(g.cells)
            top_stacks.extend(g.foundations)
        else:  # Klondike-like
            top_stacks.append(g.talon)
            top_stacks.append(g.waste)
            top_stacks.append(None)  # spacer
            top_stacks.extend(g.foundations)

        for s in top_stacks:
            if s is None:
                col += 1
                continue
            slot = StackSlot(sid=s.sid, col=col, row=0,
                             x=col * COL_W + 1, y=0)
            slots.append(slot)
            col += 1

        top_cols = col

        # Row 1: tableau rows
        for i, s in enumerate(g.rows):
            slot = StackSlot(sid=s.sid, col=i, row=1,
                             x=i * COL_W + 1, y=TABLEAU_TOP)
            slots.append(slot)

        self.slots = slots
        self._slot_for = {sl.sid: sl for sl in slots}

        # Canvas dims
        max_col = max(top_cols, len(g.rows))
        self._canvas_w = max_col * COL_W + 2
        # Tallest tableau column determines height.
        tallest = max((R.stack_height(s) for s in g.rows), default=R.CARD_H)
        self._canvas_h = TABLEAU_TOP + tallest + 2

    # -- rendering --
    def render_line(self, y: int) -> Strip:
        """Render one row of the canvas, cropped to the viewport."""
        if self.game is None:
            return Strip.blank(self.size.width)

        scroll_x, scroll_y = self.scroll_offset
        canvas_y = y + int(scroll_y)
        width = self.size.width

        # Build a list of (x, text, style) paintings covering canvas_y.
        # Simpler: paint a fixed-length char buffer.
        buf_w = self._canvas_w
        chars = [" "] * buf_w
        styles: list[Style | None] = [None] * buf_w
        bg_default = Style.parse(f"on {R.COL_BG_DARK}")

        for slot in self.slots:
            self._paint_slot(slot, canvas_y, chars, styles)

        # Crop to viewport
        start = int(scroll_x)
        end = min(buf_w, start + width)
        segments: list[Segment] = []
        cur_style: Style | None = None
        cur_text = ""
        for i in range(start, end):
            st = styles[i] if styles[i] is not None else bg_default
            if st == cur_style:
                cur_text += chars[i]
            else:
                if cur_text:
                    segments.append(Segment(cur_text, cur_style))
                cur_text = chars[i]
                cur_style = st
        if cur_text:
            segments.append(Segment(cur_text, cur_style))

        # Pad to full width
        rendered_w = end - start
        if rendered_w < width:
            segments.append(Segment(" " * (width - rendered_w), bg_default))

        return Strip(segments)

    def _paint_slot(self, slot: StackSlot, canvas_y: int,
                    chars: list[str], styles: list[Style | None]) -> None:
        """Paint the stack at `slot` into the chars/styles buffer if it
        intersects canvas_y."""
        assert self.game is not None
        stack = self.game.stacks[slot.sid]
        sel_from = self._selected_from_for(slot.sid)
        cursor_here = (slot.sid == self.cursor_sid)

        if not stack.cards:
            # Empty slot — 4 rows tall.
            local_y = canvas_y - slot.y
            if 0 <= local_y < R.CARD_H:
                label = _empty_label(stack)
                rows = R.empty_slot_rows(label, selected=cursor_here)
                text, style = rows[local_y]
                self._write_at(slot.x, text, style, chars, styles)
            return

        # Top-row stacks (stock/waste/foundation/cell) render as a single
        # stacked footprint — only the top card is visible.
        if slot.row == 0:
            local_y = canvas_y - slot.y
            if not (0 <= local_y < R.CARD_H):
                return
            card = stack.cards[-1]
            is_sel = (sel_from is not None and (len(stack.cards) - 1) >= sel_from)
            if card.face_up:
                rows = R.card_face_rows(card, selected=is_sel or cursor_here)
            else:
                rows = R.card_back_rows(selected=is_sel or cursor_here)
            text, style = rows[local_y]
            self._write_at(slot.x, text, style, chars, styles)
            return

        # Tableau row: fanned.
        y0 = slot.y
        offsets: list[tuple[int, int]] = []  # (card_idx, y0_of_card)
        cy = y0
        for i, _c in enumerate(stack.cards[:-1]):
            offsets.append((i, cy))
            cy += R.FAN_OFFSET
        offsets.append((len(stack.cards) - 1, cy))

        # Non-top cards contribute exactly 2 rows; full face is visible
        # only on the topmost card.
        for i, cy in offsets[:-1]:
            card = stack.cards[i]
            local = canvas_y - cy
            if not (0 <= local < R.FAN_OFFSET):
                continue
            is_sel = (sel_from is not None and i >= sel_from)
            # Cursor highlight only applies to the topmost card (handled
            # below); non-top fanned cards show selection only when the
            # player has actually picked them up.
            if card.face_up:
                rows = R.card_face_rows(card, selected=is_sel)
            else:
                rows = R.card_back_rows(selected=is_sel)
            text, style = rows[local]
            self._write_at(slot.x, text, style, chars, styles)

        # Topmost card (full 4 rows).
        i_top, cy_top = offsets[-1]
        card = stack.cards[i_top]
        local = canvas_y - cy_top
        if not (0 <= local < R.CARD_H):
            return
        is_sel = (sel_from is not None and i_top >= sel_from)
        highlight = cursor_here
        if card.face_up:
            rows = R.card_face_rows(card, selected=is_sel or highlight)
        else:
            rows = R.card_back_rows(selected=is_sel or highlight)
        text, style = rows[local]
        self._write_at(slot.x, text, style, chars, styles)

    def _write_at(self, x: int, text: str, style: Style,
                  chars: list[str], styles: list[Style | None]) -> None:
        for i, ch in enumerate(text):
            xi = x + i
            if 0 <= xi < len(chars):
                chars[xi] = ch
                styles[xi] = style

    def _selected_from_for(self, sid: int) -> int | None:
        if self.selected_sid is None or self.selected_sid != sid:
            return None
        return self.selected_from

    def _has_selection(self) -> bool:
        return self.selected_sid is not None

    # -- input: cursor navigation --
    def move_cursor(self, dsid: int) -> None:
        # Find slot order in a grid-friendly way. Simplest: list slots,
        # jump by 1. "Right/left" = next/prev in list order; "up/down" =
        # toggle between row 0 and the nearest column on row 1.
        if not self.slots:
            return
        cur = self._slot_for.get(self.cursor_sid)
        if cur is None:
            self.cursor_sid = self.slots[0].sid
            self.refresh()
            return
        if dsid == +1 or dsid == -1:
            idx = self.slots.index(cur)
            nxt = (idx + dsid) % len(self.slots)
            self.cursor_sid = self.slots[nxt].sid
        elif dsid == +2 or dsid == -2:
            # up/down: swap row, keep column closest.
            target_row = 1 if cur.row == 0 and dsid == +2 else (
                0 if cur.row == 1 and dsid == -2 else cur.row)
            if target_row == cur.row:
                # no same-row movement
                return
            candidates = [s for s in self.slots if s.row == target_row]
            if not candidates:
                return
            # Nearest column
            candidates.sort(key=lambda s: abs(s.col - cur.col))
            self.cursor_sid = candidates[0].sid
        self.refresh()

    # -- input: mouse --
    def on_click(self, event: events.Click) -> None:
        """Translate click coords into a stack + card-index."""
        if self.game is None:
            return
        x = event.x + int(self.scroll_offset.x)
        y = event.y + int(self.scroll_offset.y)
        hit = self._hit_test(x, y)
        if hit is None:
            return
        sid, card_idx = hit
        self.cursor_sid = sid
        self.post_message(self.StackActivated(sid, card_idx))

    def _hit_test(self, x: int, y: int) -> tuple[int, int] | None:
        """Return (sid, card_index) for canvas coord (x, y), or None."""
        assert self.game is not None
        # Check row-1 (tableau) slots first so they don't get shadowed by
        # top-row slots that happen to share a column.
        ordered = sorted(self.slots, key=lambda s: -s.row)
        for slot in ordered:
            if not (slot.x <= x < slot.x + R.CARD_W):
                continue
            stack = self.game.stacks[slot.sid]
            if not stack.cards:
                if slot.y <= y < slot.y + R.CARD_H:
                    return (slot.sid, 0)
                continue
            if slot.row == 0:
                # Stacked footprint: 4 rows total.
                if slot.y <= y < slot.y + R.CARD_H:
                    return (slot.sid, len(stack.cards) - 1)
                continue
            # Tableau (fanned). Walk cards.
            cy = slot.y
            for i, _c in enumerate(stack.cards[:-1]):
                if cy <= y < cy + R.FAN_OFFSET:
                    return (slot.sid, i)
                cy += R.FAN_OFFSET
            # Topmost card, full 4 rows.
            if cy <= y < cy + R.CARD_H:
                return (slot.sid, len(stack.cards) - 1)
        return None

    class StackActivated(events.Event):
        def __init__(self, sid: int, card_idx: int) -> None:
            super().__init__()
            self.sid = sid
            self.card_idx = card_idx


def _empty_label(stack: E.Stack) -> str:
    if stack.kind == "talon":
        return "▶"
    if stack.kind == "waste":
        return "◆"
    if stack.kind == "foundation":
        # Use suit glyph if it's a typed foundation.
        suit = getattr(stack, "suit", None)
        if suit is not None:
            return E.SUIT_GLYPHS[suit]
        return "★"
    if stack.kind == "reserve":
        return "·"
    return " "


# -------------- side panels --------------

class StatusPanel(Static):
    def __init__(self) -> None:
        super().__init__("", id="status-panel")
        self.border_title = "Status"

    def refresh_status(self, app: "PysolApp") -> None:
        g = app.game
        tv = app.tableau
        if tv is None:
            return
        lines = [
            f"[b]{g.name}[/b]",
            f"Seed: {g.seed}",
            f"Moves: {g.moves_made}",
            f"Won:  {'YES' if g.is_won() else 'no'}",
        ]
        # Show selection
        if tv.selected_sid is not None:
            s = g.stacks[tv.selected_sid]
            n = len(s.cards) - tv.selected_from
            lines.append(f"Holding: {n} card(s) from #{s.sid}")
        else:
            cur = g.stacks[tv.cursor_sid]
            if cur.cards:
                top = cur.cards[-1]
                face = "?" if not top.face_up else f"{top.rank_label}{top.glyph}"
                lines.append(f"Cursor: #{cur.sid} ({cur.kind}) top={face}")
            else:
                lines.append(f"Cursor: #{cur.sid} ({cur.kind}) [empty]")
        self.update("\n".join(lines))


class LegendPanel(Static):
    def __init__(self) -> None:
        super().__init__(_LEGEND_TEXT, id="legend-panel")
        self.border_title = "Controls"


_LEGEND_TEXT = """\
[b]Navigation[/b]
  ←/→  next/prev stack
  ↑/↓  top row ↔ tableau
  Tab  cycle stacks

[b]Actions[/b]
  Enter/Space  pick up / drop
  Esc          cancel selection
  a            auto-send to foundation
  s            flip stock → waste
  u            undo last move
  n            new game
  v            variant picker

[b]Mouse[/b]
  click a card  select that card + any
                legal group above it
  click again   drop here (if legal)

[b]Suits[/b]
  [red]♥[/red] [red]♦[/red]  red
  ♠ ♣  black
"""


# -------------- app --------------

class PysolApp(App):
    CSS_PATH = "tui.tcss"
    TITLE = "pysolfc-tui"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("n", "new_game", "New"),
        Binding("u", "undo", "Undo"),
        Binding("s", "flip_stock", "Stock"),
        Binding("a", "auto_send", "Auto"),
        Binding("v", "variant", "Variant"),
        Binding("question_mark", "help", "Help"),
        Binding("escape", "cancel_select", "Cancel"),
        Binding("space", "activate", "Pick/Drop", show=False),
        Binding("enter", "activate", "Pick/Drop"),
        Binding("left", "cursor(-1)", show=False, priority=True),
        Binding("right", "cursor(1)", show=False, priority=True),
        Binding("up", "cursor(-2)", show=False, priority=True),
        Binding("down", "cursor(2)", show=False, priority=True),
        Binding("tab", "cursor(1)", show=False),
    ]

    def __init__(self, variant: str = "Klondike", seed: int | None = None) -> None:
        super().__init__()
        self._variant = variant
        self._seed = seed
        self.game: E.Game = E.VARIANTS[variant](seed=seed)
        self.tableau: TableauView | None = None  # type: ignore[assignment]
        self.status_panel: StatusPanel | None = None  # type: ignore[assignment]
        self.log_widget: RichLog | None = None  # type: ignore[assignment]
        self.flash_bar: Static | None = None  # type: ignore[assignment]
        # Dogfood-visible cursor state: mirrors tableau.cursor_sid so the
        # driver's state-hash changes on every arrow keypress.
        self.score: int = 0

    # -- compose --
    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Horizontal(id="body"):
            with Vertical(id="tableau-col"):
                self.tableau = TableauView()
                self.tableau.border_title = "Tableau"
                yield self.tableau
                self.flash_bar = Static("", id="flash-bar")
                yield self.flash_bar
                self.log_widget = RichLog(id="log", max_lines=200, markup=True)
                self.log_widget.border_title = "Log"
                yield self.log_widget
            with Vertical(id="side"):
                self.status_panel = StatusPanel()
                yield self.status_panel
                yield LegendPanel()
        yield Footer()

    async def on_mount(self) -> None:
        assert self.tableau is not None
        self.tableau.load_game(self.game)
        self.refresh_all()
        self.log_msg(f"Dealt {self.game.name} (seed {self.game.seed})")

    # -- actions --
    def action_cursor(self, delta: int) -> None:
        # Priority bindings also fire when modals (e.g. VariantScreen with
        # ListView) are open. Guard so arrows reach the modal's widgets.
        if len(self.screen_stack) > 1:
            return
        assert self.tableau is not None
        self.tableau.move_cursor(delta)
        # Keep score in sync so the dogfood driver can detect cursor changes.
        self.score = self.tableau.cursor_sid
        self.refresh_all()

    def action_activate(self) -> None:
        """Pick up from cursor, or drop selection at cursor."""
        assert self.tableau is not None
        tv = self.tableau
        if tv.selected_sid is None:
            # pick up topmost draggable from cursor stack
            self._try_pickup(tv.cursor_sid, None)
        else:
            self._try_drop(tv.cursor_sid)
        self.refresh_all()

    def action_cancel_select(self) -> None:
        assert self.tableau is not None
        self.tableau.selected_sid = None
        self.tableau.refresh()
        self.refresh_all()

    def action_flip_stock(self) -> None:
        ok = self.game.flip_stock()
        msg = "Stock flipped." if ok else "No stock to flip."
        self.log_msg(msg)
        self.refresh_all()

    def action_undo(self) -> None:
        if self.game.undo():
            self.log_msg("Undo.")
        else:
            self.log_msg("Nothing to undo.")
        self.refresh_all()

    def action_new_game(self) -> None:
        self.game = E.VARIANTS[self._variant]()
        assert self.tableau is not None
        self.tableau.load_game(self.game)
        self.log_msg(f"New {self._variant} (seed {self.game.seed}).")
        self.refresh_all()

    def action_auto_send(self) -> None:
        """Try to send every legal card to foundations (one pass)."""
        assert self.tableau is not None
        sent = 0
        # Try waste, tableau tops, freecells.
        sources: list[E.Stack] = []
        if self.game.waste is not None:
            sources.append(self.game.waste)
        sources.extend(self.game.rows)
        sources.extend(self.game.cells)
        for s in sources:
            if self.game.auto_send(s) is not None:
                sent += 1
        if sent:
            self.log_msg(f"Auto-sent {sent} card(s).")
        else:
            self.log_msg("Nothing to auto-send.")
        self.refresh_all()

    def action_variant(self) -> None:
        """Open a modal variant picker."""
        def _selected(result: str | None) -> None:
            if result and result in E.VARIANTS:
                self._variant = result
                self.action_new_game()
        self.push_screen(VariantScreen(), _selected)

    def action_help(self) -> None:
        self.push_screen(HelpScreen())

    # -- pick / drop --
    def _try_pickup(self, sid: int, card_idx: int | None) -> None:
        stack = self.game.stacks[sid]
        if stack.kind == "talon":
            # Tap on talon = flip stock.
            self.action_flip_stock()
            return
        if not stack.cards:
            self.log_msg("Empty stack — nothing to pick up.")
            return
        if card_idx is None:
            # Default: topmost draggable.
            idx = len(stack.cards) - 1
            # Walk up to find the deepest draggable start.
            best = idx
            for i in range(idx, -1, -1):
                if stack.can_drag(i):
                    best = i
                else:
                    break
            card_idx = best
        if not stack.can_drag(card_idx):
            self.log_msg("Can't pick up that card.")
            return
        assert self.tableau is not None
        self.tableau.selected_sid = sid
        self.tableau.selected_from = card_idx
        n = len(stack.cards) - card_idx
        self.flash(f"Picked up {n} card(s) from #{sid}.")

    def _try_drop(self, dst_sid: int) -> None:
        assert self.tableau is not None
        tv = self.tableau
        src_sid = tv.selected_sid
        if src_sid is None:
            return
        if src_sid == dst_sid:
            # Same stack — treat as cancel.
            tv.selected_sid = None
            return
        src = self.game.stacks[src_sid]
        dst = self.game.stacks[dst_sid]
        n = len(src.cards) - tv.selected_from
        if self.game.move(src, dst, n):
            self.log_msg(f"Moved {n} to #{dst_sid}.")
            tv.selected_sid = None
            if self.game.is_won():
                self.flash("You won! Press n for a new game.")
                self.log_msg("[bold yellow]Game won![/bold yellow]")
                self._celebrate_win()
        else:
            self.log_msg(f"Illegal move to #{dst_sid}.")
            tv.selected_sid = None

    def _celebrate_win(self) -> None:
        def _after(want_new: bool | None) -> None:
            if want_new:
                self.action_new_game()
        self.push_screen(WinScreen(self.game), _after)

    # -- mouse routing --
    def on_tableau_view_stack_activated(self, message: TableauView.StackActivated) -> None:
        assert self.tableau is not None
        tv = self.tableau
        if tv.selected_sid is None:
            self._try_pickup(message.sid, message.card_idx)
        else:
            self._try_drop(message.sid)
        self.refresh_all()

    # -- helpers --
    def log_msg(self, msg: str) -> None:
        if self.log_widget is not None:
            self.log_widget.write(msg)

    def flash(self, msg: str) -> None:
        if self.flash_bar is not None:
            self.flash_bar.update(msg)
        self.log_msg(msg)

    def refresh_all(self) -> None:
        if self.tableau is not None:
            self.tableau.refresh()
        if self.status_panel is not None:
            self.status_panel.refresh_status(self)


def run(variant: str = "Klondike", seed: int | None = None) -> None:
    PysolApp(variant=variant, seed=seed).run()
