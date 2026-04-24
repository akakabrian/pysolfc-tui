"""Textual app — solitaire TUI (large-card mockup layout).

Layout:
    ┌─ top HUD ──────────────────────────────────────────────┐
    │  ◆ KLONDIKE ◆    MOVES: N     STOCK: N  WASTE: X        │
    ├─ tableau canvas ───────────────────────────────────────┤
    │  [stock][waste]          [F][F][F][F]                   │
    │  col0 col1 col2 col3 col4 col5 col6                     │
    ├─ holding pill ─────────────────────────────────────────┤
    │              Holding: 1 card from #5 (9♥)               │
    ├─ context action ───────────────────────────────────────┤
    │                  Enter: drop 9♥ on 8♠                   │
    └────────────────────────────────────────────────────────┘

Controls live in the `?` help modal. Cursor selects a stack;
enter/space picks up / drops. Mouse clicks do the same.
"""

from __future__ import annotations

import time
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
from textual.widgets import RichLog, Static

from . import engine as E
from . import render as R
from .music import MusicPlayer
from .screens import HelpScreen, VariantScreen, WinScreen

MIN_COL_GAP = 2
MAX_COL_GAP = 8
LABEL_H = 1
TOP_CARD_Y = LABEL_H                                   # cards sit below the label band
TABLEAU_TOP = LABEL_H + R.CARD_H_TOP + 1               # +1 gap between top row and tableau


@dataclass
class StackSlot:
    sid: int
    col: int
    row: int
    x: int
    y: int


class TableauView(ScrollView):
    cursor_sid: reactive[int] = reactive(0)
    selected_sid: reactive[int | None] = reactive(None)
    selected_from: reactive[int] = reactive(0)

    def __init__(self) -> None:
        super().__init__()
        self.game: E.Game | None = None
        self.slots: list[StackSlot] = []
        self._slot_for: dict[int, StackSlot] = {}
        self._canvas_w = 10
        self._canvas_h = 10
        self._col_w = R.CARD_W + MIN_COL_GAP
        self._x_offset = 1
        self._last_vp_w: int | None = None

    def load_game(self, game: E.Game) -> None:
        self.game = game
        self._layout_slots()
        self.virtual_size = Size(self._canvas_w, self._canvas_h)
        self.cursor_sid = self.slots[0].sid if self.slots else 0
        self.selected_sid = None
        self.refresh()

    def _layout_slots(self) -> None:
        assert self.game is not None
        g = self.game

        top_stacks: list[E.Stack | None] = []
        if isinstance(g, E.Spider):
            top_stacks.extend(g.foundations)
            top_stacks.append(g.talon)
        elif isinstance(g, E.FreeCell):
            top_stacks.extend(g.cells)
            top_stacks.extend(g.foundations)
        else:
            top_stacks.append(g.talon)
            top_stacks.append(g.waste)
            top_stacks.append(None)
            top_stacks.extend(g.foundations)

        num_cols = max(len(top_stacks), len(g.rows))
        self._col_w, self._x_offset, self._canvas_w = self._compute_metrics(num_cols)

        slots: list[StackSlot] = []
        col = 0
        for s in top_stacks:
            if s is None:
                col += 1
                continue
            slots.append(StackSlot(sid=s.sid, col=col, row=0,
                                   x=col * self._col_w + self._x_offset,
                                   y=TOP_CARD_Y))
            col += 1

        for i, s in enumerate(g.rows):
            slots.append(StackSlot(sid=s.sid, col=i, row=1,
                                   x=i * self._col_w + self._x_offset,
                                   y=TABLEAU_TOP))

        self.slots = slots
        self._slot_for = {sl.sid: sl for sl in slots}

        tallest = max((R.stack_height(s) for s in g.rows), default=R.CARD_H)
        self._canvas_h = TABLEAU_TOP + tallest + 2

    def _compute_metrics(self, num_cols: int) -> tuple[int, int, int]:
        """Pick col-width + x-offset that centers `num_cols` cards in the viewport."""
        vp_w = max(self.size.width or 0, R.CARD_W * num_cols + 4)
        gap = max(MIN_COL_GAP, (vp_w - num_cols * R.CARD_W) // max(1, num_cols))
        gap = min(MAX_COL_GAP, gap)
        col_w = R.CARD_W + gap
        used = num_cols * col_w - gap          # trailing gap is dead space
        x_offset = max(1, (vp_w - used) // 2)
        canvas_w = max(vp_w, used + x_offset + 1)
        return col_w, x_offset, canvas_w

    def on_resize(self, event: events.Resize) -> None:
        if self.game is None:
            return
        # Height-only changes (holding pill showing/hiding, scrollbar
        # flicker) shouldn't shift the column layout — the horizontal
        # metrics only depend on width.
        new_w = self.size.width
        if new_w == self._last_vp_w:
            return
        self._last_vp_w = new_w
        self._layout_slots()
        self.virtual_size = Size(self._canvas_w, self._canvas_h)
        self.refresh()

    def render_line(self, y: int) -> Strip:
        if self.game is None:
            return Strip.blank(self.size.width)

        scroll_x, scroll_y = self.scroll_offset
        canvas_y = y + int(scroll_y)
        width = self.size.width

        buf_w = self._canvas_w
        chars = [" "] * buf_w
        styles: list[Style | None] = [None] * buf_w
        bg_default = Style.parse(f"on {R.COL_BG_DARK}")

        for slot in self.slots:
            self._paint_slot(slot, canvas_y, chars, styles)

        # Label band above the top row + stack-number band at the bottom.
        self._paint_top_labels(canvas_y, chars, styles)
        self._paint_stack_numbers(canvas_y, chars, styles)

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

        rendered_w = end - start
        if rendered_w < width:
            segments.append(Segment(" " * (width - rendered_w), bg_default))

        return Strip(segments)

    def _paint_stack_numbers(self, canvas_y: int,
                             chars: list[str], styles: list[Style | None]) -> None:
        if canvas_y != self._canvas_h - 1:
            return
        style = Style.parse(f"{R.COL_EMPTY} on {R.COL_BG_DARK}")
        for slot in self.slots:
            if slot.row != 1:
                continue
            label = f"#{slot.col + 1}".center(R.CARD_W)
            self._write_at(slot.x, label, style, chars, styles)

    def _paint_top_labels(self, canvas_y: int,
                          chars: list[str], styles: list[Style | None]) -> None:
        if canvas_y != 0:
            return
        style = Style.parse(f"bold {R.COL_EMPTY} on {R.COL_BG_DARK}")
        assert self.game is not None
        for slot in self.slots:
            if slot.row != 0:
                continue
            stack = self.game.stacks[slot.sid]
            label = self._label_for_top_stack(stack)
            text = label.center(R.CARD_W)
            self._write_at(slot.x, text, style, chars, styles)

    def _label_for_top_stack(self, stack: E.Stack) -> str:
        # Only the stock count is worth a text label — waste/foundations
        # already carry their suit glyph on the card itself.
        if stack.kind == "talon":
            return f"STOCK {len(stack.cards)}"
        return ""

    def _paint_slot(self, slot: StackSlot, canvas_y: int,
                    chars: list[str], styles: list[Style | None]) -> None:
        assert self.game is not None
        stack = self.game.stacks[slot.sid]
        sel_from = self._selected_from_for(slot.sid)
        cursor_here = (slot.sid == self.cursor_sid)
        is_top_row = (slot.row == 0)
        card_h = R.CARD_H_TOP if is_top_row else R.CARD_H

        if not stack.cards:
            local_y = canvas_y - slot.y
            if 0 <= local_y < card_h:
                label = _empty_label(stack)
                rows = R.empty_slot_rows(label, selected=cursor_here, top=is_top_row)
                text, style = rows[local_y]
                self._write_at(slot.x, text, style, chars, styles)
            return

        if is_top_row:
            local_y = canvas_y - slot.y
            if not (0 <= local_y < card_h):
                return
            card = stack.cards[-1]
            is_sel = (sel_from is not None and (len(stack.cards) - 1) >= sel_from)
            if card.face_up:
                rows = R.card_face_rows(card, selected=is_sel or cursor_here, top=True)
            else:
                rows = R.card_back_rows(selected=is_sel or cursor_here, top=True)
            text, style = rows[local_y]
            self._write_at(slot.x, text, style, chars, styles)
            return

        # Tableau fan — per-card offsets (face-down: 1 row, face-up: 2 rows).
        cy = slot.y
        offsets: list[tuple[int, int]] = []
        for i, c in enumerate(stack.cards[:-1]):
            offsets.append((i, cy))
            cy += R.FAN_UP if c.face_up else R.FAN_DOWN
        offsets.append((len(stack.cards) - 1, cy))

        for i, cy in offsets[:-1]:
            card = stack.cards[i]
            local = canvas_y - cy
            this_offset = R.FAN_UP if card.face_up else R.FAN_DOWN
            if not (0 <= local < this_offset):
                continue
            is_sel = (sel_from is not None and i >= sel_from)
            if card.face_up:
                rows = R.card_face_rows(card, selected=is_sel)
            else:
                rows = R.card_back_rows(selected=is_sel)
            text, style = rows[local]
            self._write_at(slot.x, text, style, chars, styles)

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

    def move_cursor(self, dsid: int) -> None:
        if not self.slots:
            return
        cur = self._slot_for.get(self.cursor_sid)
        if cur is None:
            self.cursor_sid = self.slots[0].sid
            self.refresh()
            return

        # Restrict cursor to stacks we could actually drop the held run onto
        # (plus the source stack, so Enter-on-self still cancels).
        candidates = self._navigable_slots()
        if not candidates:
            return
        if cur not in candidates:
            candidates.sort(key=lambda s: (s.row != cur.row, abs(s.col - cur.col)))
            self.cursor_sid = candidates[0].sid
            self.refresh()
            return

        if dsid == +1 or dsid == -1:
            idx = candidates.index(cur)
            nxt = (idx + dsid) % len(candidates)
            self.cursor_sid = candidates[nxt].sid
        elif dsid == +2 or dsid == -2:
            target_row = 1 if cur.row == 0 and dsid == +2 else (
                0 if cur.row == 1 and dsid == -2 else cur.row)
            if target_row == cur.row:
                return
            row_cands = [s for s in candidates if s.row == target_row]
            if not row_cands:
                return
            row_cands.sort(key=lambda s: abs(s.col - cur.col))
            self.cursor_sid = row_cands[0].sid
        self.refresh()

    def _navigable_slots(self) -> list[StackSlot]:
        """All slots the cursor may land on right now. When holding a run,
        this is the source (for cancel) plus legal drop targets."""
        if self.selected_sid is None or self.game is None:
            return list(self.slots)
        src = self.game.stacks[self.selected_sid]
        held = src.cards[self.selected_from:]
        out: list[StackSlot] = []
        for slot in self.slots:
            if slot.sid == self.selected_sid:
                out.append(slot)
                continue
            dst = self.game.stacks[slot.sid]
            if dst.accepts(src, held):
                out.append(slot)
        return out

    def on_click(self, event: events.Click) -> None:
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
        assert self.game is not None
        ordered = sorted(self.slots, key=lambda s: -s.row)
        for slot in ordered:
            if not (slot.x <= x < slot.x + R.CARD_W):
                continue
            is_top_row = (slot.row == 0)
            card_h = R.CARD_H_TOP if is_top_row else R.CARD_H
            stack = self.game.stacks[slot.sid]
            if not stack.cards:
                if slot.y <= y < slot.y + card_h:
                    return (slot.sid, 0)
                continue
            if is_top_row:
                if slot.y <= y < slot.y + card_h:
                    return (slot.sid, len(stack.cards) - 1)
                continue
            cy = slot.y
            for i, c in enumerate(stack.cards[:-1]):
                off = R.FAN_UP if c.face_up else R.FAN_DOWN
                if cy <= y < cy + off:
                    return (slot.sid, i)
                cy += off
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
        suit = getattr(stack, "suit", None)
        if suit is not None:
            return E.SUIT_GLYPHS[suit]
        return "★"
    if stack.kind == "reserve":
        return "·"
    return " "


# -------------- chrome widgets --------------

class TopHUD(Horizontal):
    """Variant · elapsed time · moves · foundation progress."""

    def compose(self) -> ComposeResult:
        yield Static("◆ KLONDIKE ◆", id="hud-title")
        yield Static("TIME 0:00", id="hud-time")
        yield Static("MOVES 0", id="hud-moves")
        yield Static("SCORE 0/52", id="hud-score")

    def refresh_hud(self, app: "PysolApp") -> None:
        g = app.game
        self.query_one("#hud-title", Static).update(f"◆ {g.name.upper()} ◆")
        self.query_one("#hud-time", Static).update(f"TIME {app.elapsed_str()}")
        self.query_one("#hud-moves", Static).update(f"MOVES {g.moves_made}")

        on_fnd = sum(len(f.cards) for f in g.foundations)
        target = 13 * max(1, len(g.foundations))
        self.query_one("#hud-score", Static).update(f"SCORE {on_fnd}/{target}")


class StatusPanel(Static):
    """Hidden — kept for test compatibility. Mirrors the holding pill text."""

    def __init__(self) -> None:
        super().__init__("", id="status-panel")

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
        Binding("m", "toggle_music", "Music"),
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

    def __init__(self, variant: str = "Klondike", seed: int | None = None,
                 music: bool = True) -> None:
        super().__init__()
        self._variant = variant
        self._seed = seed
        self._music_enabled = music
        self.game: E.Game = E.VARIANTS[variant](seed=seed)
        self.tableau: TableauView | None = None  # type: ignore[assignment]
        self.top_hud: TopHUD | None = None  # type: ignore[assignment]
        self.status_panel: StatusPanel | None = None  # type: ignore[assignment]
        self.holding_pill: Static | None = None  # type: ignore[assignment]
        self.context_line: Static | None = None  # type: ignore[assignment]
        self.log_widget: RichLog | None = None  # type: ignore[assignment]
        # Legacy alias; some tests reach for flash_bar.
        self.flash_bar: Static | None = None  # type: ignore[assignment]
        self.score: int = 0
        self._transient_msg: str = ""
        self._start_time: float = time.monotonic()
        self.music = MusicPlayer(enabled=self._music_enabled)

    def elapsed_str(self) -> str:
        elapsed = int(time.monotonic() - self._start_time)
        m, s = divmod(elapsed, 60)
        h, m = divmod(m, 60)
        return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

    def compose(self) -> ComposeResult:
        self.top_hud = TopHUD(id="top-hud")
        yield self.top_hud

        self.tableau = TableauView()
        yield self.tableau

        self.holding_pill = Static("", id="holding-pill")
        yield self.holding_pill

        self.context_line = Static("", id="context-line")
        self.flash_bar = self.context_line
        yield self.context_line

        # Hidden widgets kept for test compatibility.
        self.status_panel = StatusPanel()
        self.status_panel.display = False
        yield self.status_panel

        self.log_widget = RichLog(id="log", max_lines=200, markup=True)
        self.log_widget.display = False
        yield self.log_widget

    async def on_mount(self) -> None:
        assert self.tableau is not None
        self.tableau.load_game(self.game)
        self._start_time = time.monotonic()
        self.set_interval(1.0, self._tick)
        self.music.start()
        self.refresh_all()
        self.log_msg(f"Dealt {self.game.name} (seed {self.game.seed})")

    async def on_unmount(self) -> None:
        self.music.stop()

    def action_toggle_music(self) -> None:
        playing = self.music.toggle()
        self.flash("Music on." if playing else "Music off.")

    def _tick(self) -> None:
        if self.top_hud is not None:
            self.top_hud.refresh_hud(self)

    # -- actions --
    def action_cursor(self, delta: int) -> None:
        if len(self.screen_stack) > 1:
            return
        assert self.tableau is not None
        self.tableau.move_cursor(delta)
        self.score = self.tableau.cursor_sid
        self.refresh_all()

    def action_activate(self) -> None:
        assert self.tableau is not None
        tv = self.tableau
        if tv.selected_sid is None:
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
        self.flash("Stock flipped." if ok else "No stock to flip.")
        self.refresh_all()

    def action_undo(self) -> None:
        self.flash("Undo." if self.game.undo() else "Nothing to undo.")
        self.refresh_all()

    def action_new_game(self) -> None:
        self.game = E.VARIANTS[self._variant]()
        assert self.tableau is not None
        self.tableau.load_game(self.game)
        self._start_time = time.monotonic()
        self.flash(f"New {self._variant} (seed {self.game.seed}).")
        self.refresh_all()

    def action_auto_send(self) -> None:
        assert self.tableau is not None
        sent = 0
        sources: list[E.Stack] = []
        if self.game.waste is not None:
            sources.append(self.game.waste)
        sources.extend(self.game.rows)
        sources.extend(self.game.cells)
        for s in sources:
            if self.game.auto_send(s) is not None:
                sent += 1
        self.flash(f"Auto-sent {sent} card(s)." if sent else "Nothing to auto-send.")
        self.refresh_all()

    def action_variant(self) -> None:
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
            self.action_flip_stock()
            return
        if not stack.cards:
            self.flash("Empty stack — nothing to pick up.")
            return
        if card_idx is None:
            idx = len(stack.cards) - 1
            best = idx
            for i in range(idx, -1, -1):
                if stack.can_drag(i):
                    best = i
                else:
                    break
            card_idx = best
        if not stack.can_drag(card_idx):
            self.flash("Can't pick up that card.")
            return
        assert self.tableau is not None
        self.tableau.selected_sid = sid
        self.tableau.selected_from = card_idx
        # The holding pill already shows the pickup — no transient flash needed.

    def _try_drop(self, dst_sid: int) -> None:
        assert self.tableau is not None
        tv = self.tableau
        src_sid = tv.selected_sid
        if src_sid is None:
            return
        if src_sid == dst_sid:
            tv.selected_sid = None
            return
        src = self.game.stacks[src_sid]
        dst = self.game.stacks[dst_sid]
        n = len(src.cards) - tv.selected_from
        if self.game.move(src, dst, n):
            self.flash(f"Moved {n} to #{dst_sid}.")
            tv.selected_sid = None
            if self.game.is_won():
                self.flash("You won! Press n for a new game.")
                self._celebrate_win()
        else:
            # Illegal mouse drop — ring the bell and revert the hold.
            self.bell()
            self.flash(f"Illegal move to #{dst_sid}.")
            tv.selected_sid = None

    def _celebrate_win(self) -> None:
        def _after(want_new: bool | None) -> None:
            if want_new:
                self.action_new_game()
        self.push_screen(WinScreen(self.game), _after)

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
        self._transient_msg = msg
        self.log_msg(msg)

    def _update_holding_pill(self) -> None:
        if self.holding_pill is None or self.tableau is None:
            return
        tv = self.tableau
        if tv.selected_sid is None:
            self.holding_pill.update("")
            self.holding_pill.display = False
            return
        s = self.game.stacks[tv.selected_sid]
        n = len(s.cards) - tv.selected_from
        card = s.cards[tv.selected_from]
        face = f"{card.rank_label}{card.glyph}" if card.face_up else "▒"
        suffix = f"  +{n - 1}" if n > 1 else ""
        self.holding_pill.update(f"HELD  {face} from #{s.sid}{suffix}")
        self.holding_pill.display = True

    def _update_context_line(self) -> None:
        if self.context_line is None or self.tableau is None:
            return
        if self._transient_msg:
            self.context_line.update(self._transient_msg)
            self._transient_msg = ""
            return
        tv = self.tableau
        cur = self.game.stacks[tv.cursor_sid]
        if tv.selected_sid is None:
            if cur.cards and cur.cards[-1].face_up:
                c = cur.cards[-1]
                self.context_line.update(
                    f"Enter: pick up {c.rank_label}{c.glyph} from #{cur.sid}   ·   ? Help   ·   n New   ·   u Undo"
                )
            else:
                self.context_line.update(
                    "← → Select   ·   Enter Pick/Drop   ·   s Stock   ·   ? Help"
                )
        else:
            src = self.game.stacks[tv.selected_sid]
            held = src.cards[tv.selected_from]
            held_face = f"{held.rank_label}{held.glyph}"
            if tv.cursor_sid == tv.selected_sid:
                self.context_line.update(
                    f"Enter / Esc: cancel {held_face}   ·   ← → cycle legal drops"
                )
                return
            target = f"#{cur.sid}" if not cur.cards else (
                f"{cur.cards[-1].rank_label}{cur.cards[-1].glyph} (#{cur.sid})"
                if cur.cards[-1].face_up else f"#{cur.sid}"
            )
            self.context_line.update(
                f"Enter: drop {held_face} on {target}   ·   Esc Cancel"
            )

    def refresh_all(self) -> None:
        if self.tableau is not None:
            self.tableau.refresh()
        if self.top_hud is not None:
            self.top_hud.refresh_hud(self)
        if self.status_panel is not None:
            self.status_panel.refresh_status(self)
        self._update_holding_pill()
        self._update_context_line()


def run(variant: str = "Klondike", seed: int | None = None,
        music: bool = True) -> None:
    app = PysolApp(variant=variant, seed=seed, music=music)
    try:
        app.run()
    finally:
        # Always kill the loop subprocess on exit — Textual crashes can
        # otherwise leave paplay running after the terminal returns.
        app.music.stop()
