"""Hot-path benchmarks. Run: `python -m tests.perf`."""

from __future__ import annotations

import asyncio
import time

from pysolfc_tui.app import PysolApp


async def main() -> None:
    app = PysolApp(variant="Klondike", seed=42)
    async with app.run_test(size=(140, 45)) as pilot:
        await pilot.pause()
        tv = app.tableau
        assert tv is not None
        # full render (all rows)
        t0 = time.perf_counter()
        n_rows = tv._canvas_h
        for y in range(n_rows):
            tv.render_line(y)
        t1 = time.perf_counter()
        print(f"render_line × {n_rows:>3} rows: {(t1 - t0)*1000:7.2f} ms "
              f"({(t1 - t0)*1000/max(n_rows,1):.3f} ms/row)")

        # cursor move → full repaint (simulates arrow press)
        t0 = time.perf_counter()
        for _ in range(50):
            tv.move_cursor(+1)
            for y in range(n_rows):
                tv.render_line(y)
        t1 = time.perf_counter()
        print(f"50× cursor move + full repaint: {(t1 - t0)*1000:7.2f} ms "
              f"({(t1 - t0)*1000/50:.2f} ms each)")

        # stock flip (x 10)
        t0 = time.perf_counter()
        for _ in range(10):
            app.game.flip_stock()
        t1 = time.perf_counter()
        print(f"flip_stock × 10:               {(t1 - t0)*1000:7.2f} ms")


if __name__ == "__main__":
    asyncio.run(main())
