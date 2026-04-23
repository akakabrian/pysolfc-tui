"""Headless QA driver for pysolfc-tui.

Each scenario runs a fresh `PysolApp` under `App.run_test()`. Screenshots
are saved to tests/out/<name>.PASS.svg or .FAIL.svg.

    python -m tests.qa            # run all
    python -m tests.qa cursor     # run scenarios whose name matches "cursor"

Exit code is the number of failing scenarios.
"""

from __future__ import annotations

import asyncio
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable

from pysolfc_tui import engine as E
from pysolfc_tui.app import PysolApp

OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)

TERM_SIZE = (140, 45)


@dataclass
class Scenario:
    name: str
    fn: Callable[[PysolApp, "object"], Awaitable[None]]
    variant: str = "Klondike"
    seed: int = 42


# ---------- helpers ----------

def find_playable_card(game: E.Game, rank: int) -> tuple[E.Stack, int] | None:
    for s in game.stacks:
        for i, c in enumerate(s.cards):
            if c.face_up and c.rank == rank and s.can_drag(i):
                return (s, i)
    return None


# ---------- scenarios ----------

async def s_mount_clean(app, pilot):
    assert app.tableau is not None
    assert app.status_panel is not None
    assert app.log_widget is not None
    assert app.game is not None
    assert app.game.name == "Klondike"


async def s_deal_shape(app, pilot):
    g = app.game
    assert [len(r) for r in g.rows] == [1, 2, 3, 4, 5, 6, 7]
    assert len(g.talon.cards) == 24
    assert len(g.waste.cards) == 0
    assert all(len(f.cards) == 0 for f in g.foundations)
    # Only the top of each tableau column is face-up.
    for row in g.rows:
        for i, c in enumerate(row.cards):
            want_up = (i == len(row.cards) - 1)
            assert c.face_up == want_up, f"card {i}/{len(row.cards)} face_up={c.face_up}"


async def s_cursor_starts_at_stock(app, pilot):
    # Slot 0 is the stock for Klondike.
    assert app.tableau.cursor_sid == app.game.talon.sid


async def s_cursor_moves_right(app, pilot):
    start = app.tableau.cursor_sid
    await pilot.press("right", "right", "right")
    assert app.tableau.cursor_sid != start
    # Wraps around, so it's not equal to some specific sid; just confirm change.


async def s_cursor_down_to_tableau(app, pilot):
    await pilot.press("down")
    # Should land on a row-1 slot (one of the tableau rows).
    slot = app.tableau._slot_for[app.tableau.cursor_sid]
    assert slot.row == 1, f"slot.row={slot.row}"


async def s_stock_flip_puts_card_on_waste(app, pilot):
    g = app.game
    assert len(g.waste.cards) == 0
    await pilot.press("s")
    assert len(g.waste.cards) == 1
    assert g.waste.cards[-1].face_up


async def s_legal_move_detected(app, pilot):
    """Construct a known legal move and assert it applies."""
    g = app.game
    # Simplest check: find a row with an Ace on top, move to empty foundation.
    # With seed=42 it may or may not have one; so do a synthetic setup.
    # Clear row 0 and put an Ace of Spades on it.
    g.rows[0].cards = []
    g.rows[0].cards.append(E.Card(E.SPADE, 0, face_up=True, cid=999))
    # Find the spade foundation.
    spade_f = next(f for f in g.foundations if getattr(f, "suit", None) == E.SPADE)
    assert g.move(g.rows[0], spade_f, 1), "Ace-on-foundation should succeed"
    assert len(spade_f.cards) == 1
    assert spade_f.cards[0].rank == E.ACE


async def s_illegal_move_rejected(app, pilot):
    g = app.game
    # Try to put a 5 on an empty foundation — must fail.
    g.rows[0].cards = [E.Card(E.HEART, 4, face_up=True, cid=888)]
    heart_f = next(f for f in g.foundations if getattr(f, "suit", None) == E.HEART)
    assert not g.move(g.rows[0], heart_f, 1), "5 onto empty foundation should fail"
    assert len(heart_f.cards) == 0


async def s_undo_works(app, pilot):
    g = app.game
    before_talon = len(g.talon.cards)
    before_waste = len(g.waste.cards)
    await pilot.press("s")  # flip one
    assert len(g.waste.cards) == before_waste + 1
    await pilot.press("u")  # undo
    # Undo of the flip reverses the move; the card is back on talon with
    # face_up restored. Check sizes match.
    assert len(g.talon.cards) == before_talon
    assert len(g.waste.cards) == before_waste


async def s_pickup_and_drop_flow(app, pilot):
    """Simulate picking up a card and dropping on an illegal target, then cancel."""
    g = app.game
    # Put a Queen of Hearts on row 1 top, King of Spades on row 2 top.
    g.rows[1].cards = [E.Card(E.HEART, 11, face_up=True, cid=777)]
    g.rows[2].cards = [E.Card(E.SPADE, 12, face_up=True, cid=776)]
    app.tableau.load_game(g)
    # Cursor to row 1 slot.
    target_row1_sid = g.rows[1].sid
    app.tableau.cursor_sid = target_row1_sid
    await pilot.press("enter")  # pickup
    assert app.tableau.selected_sid == target_row1_sid
    # Move cursor to row 2 (King of Spades) — Q on K, alternate colors OK.
    app.tableau.cursor_sid = g.rows[2].sid
    await pilot.press("enter")  # drop
    assert len(g.rows[1].cards) == 0
    assert len(g.rows[2].cards) == 2
    assert g.rows[2].cards[-1].rank == 11


async def s_new_game_resets(app, pilot):
    g_before = app.game
    await pilot.press("s")
    await pilot.press("n")
    g_after = app.game
    assert g_after is not g_before
    assert [len(r) for r in g_after.rows] == [1, 2, 3, 4, 5, 6, 7]


async def s_win_detection(app, pilot):
    g = app.game
    # Rig a won state: every foundation filled A..K of its suit.
    for f in g.foundations:
        suit = getattr(f, "suit", 0)
        f.cards = [E.Card(suit, r, face_up=True, cid=1000 + r) for r in range(13)]
    assert g.is_won()


async def s_render_line_non_empty(app, pilot):
    """Smoke: render_line produces non-blank output in the tableau range."""
    tv = app.tableau
    strip = tv.render_line(0)
    # Collect displayed text
    text = "".join(seg.text for seg in strip)
    assert len(text.strip()) > 0


async def s_freecell_deal_shape(app, pilot):
    # Special: start a fresh FreeCell via action_variant + new_game.
    # Simpler: swap game directly.
    app._variant = "FreeCell"
    app.action_new_game()
    g = app.game
    assert g.name == "FreeCell"
    assert [len(r) for r in g.rows] == [7, 7, 7, 7, 6, 6, 6, 6]
    assert len(g.cells) == 4
    assert sum(len(r) for r in g.rows) == 52


async def s_spider_deal_shape(app, pilot):
    app._variant = "Spider (2-suit)"
    app.action_new_game()
    g = app.game
    assert isinstance(g, E.Spider)
    assert [len(r) for r in g.rows] == [6, 6, 6, 6, 5, 5, 5, 5, 5, 5]
    assert len(g.talon.cards) == 50


SCENARIOS: list[Scenario] = [
    Scenario("mount_clean", s_mount_clean),
    Scenario("deal_shape", s_deal_shape),
    Scenario("cursor_starts_at_stock", s_cursor_starts_at_stock),
    Scenario("cursor_moves_right", s_cursor_moves_right),
    Scenario("cursor_down_to_tableau", s_cursor_down_to_tableau),
    Scenario("stock_flip_puts_card_on_waste", s_stock_flip_puts_card_on_waste),
    Scenario("legal_move_detected", s_legal_move_detected),
    Scenario("illegal_move_rejected", s_illegal_move_rejected),
    Scenario("undo_works", s_undo_works),
    Scenario("pickup_and_drop_flow", s_pickup_and_drop_flow),
    Scenario("new_game_resets", s_new_game_resets),
    Scenario("win_detection", s_win_detection),
    Scenario("render_line_non_empty", s_render_line_non_empty),
    Scenario("freecell_deal_shape", s_freecell_deal_shape),
    Scenario("spider_deal_shape", s_spider_deal_shape),
]


async def run_scenario(scn: Scenario) -> tuple[str, bool, str]:
    app = PysolApp(variant=scn.variant, seed=scn.seed)
    try:
        async with app.run_test(size=TERM_SIZE) as pilot:
            await pilot.pause()
            try:
                await scn.fn(app, pilot)
                app.save_screenshot(str(OUT / f"{scn.name}.PASS.svg"))
                return (scn.name, True, "")
            except AssertionError as e:
                app.save_screenshot(str(OUT / f"{scn.name}.FAIL.svg"))
                return (scn.name, False, f"AssertionError: {e}")
            except Exception as e:
                app.save_screenshot(str(OUT / f"{scn.name}.FAIL.svg"))
                tb = traceback.format_exc()
                return (scn.name, False, f"{type(e).__name__}: {e}\n{tb}")
    except Exception as e:
        tb = traceback.format_exc()
        return (scn.name, False, f"Harness error: {e}\n{tb}")


async def main(pattern: str | None = None) -> int:
    matched = [s for s in SCENARIOS if pattern is None or pattern in s.name]
    if not matched:
        print(f"No scenarios match pattern {pattern!r}")
        return 1
    results = []
    for scn in matched:
        name, ok, msg = await run_scenario(scn)
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}" + (f"  — {msg.splitlines()[0]}" if msg else ""))
        if not ok and msg:
            # Indent full traceback for readability.
            for line in msg.splitlines()[1:]:
                print("      " + line)
        results.append((name, ok))
    failed = sum(1 for _, ok in results if not ok)
    total = len(results)
    print(f"\n{total - failed}/{total} scenarios passed")
    return failed


if __name__ == "__main__":
    pat = sys.argv[1] if len(sys.argv) > 1 else None
    sys.exit(asyncio.run(main(pat)))
