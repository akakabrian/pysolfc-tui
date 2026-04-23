"""End-to-end playtest driver.

Boots PysolApp in the Textual test pilot (no real pty needed — Textual's
`run_test` gives us a deterministic screenshot-capable simulator), walks
through the full user-facing flow, and saves sequential screenshots to
`tests/out/playtest_*.svg`.

    python -m tests.playtest
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from pysolfc_tui import engine as E
from pysolfc_tui.app import PysolApp

OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)


async def main() -> int:
    app = PysolApp(variant="Klondike", seed=42)
    steps: list[tuple[str, str]] = []

    async with app.run_test(size=(140, 45)) as pilot:
        await pilot.pause()
        tv = app.tableau
        assert tv is not None
        g = app.game

        # 1. initial deal
        app.save_screenshot(str(OUT / "playtest_01_deal.svg"))
        steps.append(("deal", f"talon={len(g.talon.cards) if g.talon else 0}"))

        # 2. flip stock
        await pilot.press("s")
        await pilot.pause()
        app.save_screenshot(str(OUT / "playtest_02_flip_stock.svg"))
        assert g.waste is not None and len(g.waste.cards) == 1
        steps.append(("flip_stock", f"waste={len(g.waste.cards)}"))

        # 3. click a card — plant a known playable move and exercise it.
        # Put an Ace of Spades on row 0 so auto-send can target a foundation.
        g.rows[0].cards = [E.Card(E.SPADE, 0, face_up=True, cid=9001)]
        tv.load_game(g)
        await pilot.pause()
        app.save_screenshot(str(OUT / "playtest_03_planted_ace.svg"))

        # 4. auto-send → Ace(s) go to foundation
        spade_f = next(f for f in g.foundations if getattr(f, "suit", None) == E.SPADE)
        before_spade = len(spade_f.cards)
        await pilot.press("a")
        await pilot.pause()
        assert len(spade_f.cards) >= before_spade + 1, \
            f"expected ≥{before_spade + 1} on spade foundation, got {len(spade_f.cards)}"
        app.save_screenshot(str(OUT / "playtest_04_auto_send.svg"))
        steps.append(("auto_send", f"spade_f={len(spade_f.cards)}"))

        # 5. undo — reverses the last auto-send move only (one card).
        cards_before_undo = len(spade_f.cards)
        await pilot.press("u")
        await pilot.pause()
        assert len(spade_f.cards) == cards_before_undo - 1
        app.save_screenshot(str(OUT / "playtest_05_undo.svg"))
        steps.append(("undo", f"spade_f={len(spade_f.cards)}"))

        # 6. variant switch: open picker, then dismiss (esc) to keep current.
        await pilot.press("v")
        await pilot.pause()
        app.save_screenshot(str(OUT / "playtest_06_variant_picker.svg"))
        await pilot.press("escape")
        await pilot.pause()
        steps.append(("variant_picker", "opened+dismissed"))

        # 7. help modal
        await pilot.press("question_mark")
        await pilot.pause()
        app.save_screenshot(str(OUT / "playtest_07_help.svg"))
        await pilot.press("escape")
        await pilot.pause()
        steps.append(("help", "opened+dismissed"))

        # 8. quit (press q but don't let the test harness unwind before screenshot)
        app.save_screenshot(str(OUT / "playtest_08_final.svg"))
        steps.append(("quit", "ready"))

    print("playtest steps:")
    for name, detail in steps:
        print(f"  [OK] {name:<16} {detail}")
    print(f"screenshots saved to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
