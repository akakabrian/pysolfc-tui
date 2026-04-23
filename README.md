# pysolfc-tui

Terminal-native solitaire — Textual UI, rules inspired by [PySolFC].

Ships 11 variants today:

- **Klondike** (draw-1, draw-3)
- **FreeCell** (4-cell, 8-cell relaxed)
- **Spider** (1-suit, 2-suit, 4-suit)
- **Spiderette** (1-deck Spider)
- **Simple Simon**
- **Yukon**
- **Golf**

Cards render as 5×4 bordered glyphs with Unicode suit pips. Dark-felt
palette, alternate-colour selection highlight, mouse + keyboard both work.

## Quickstart

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/python pysol.py                     # Klondike
.venv/bin/python pysol.py -v FreeCell
.venv/bin/python pysol.py -v 'Spider (2-suit)' --seed 42
```

## Controls

| Key | Action |
|-----|--------|
| `←` `→` | cursor prev/next stack |
| `↑` `↓` | top row ↔ tableau |
| `Enter` / `Space` | pick up / drop held cards |
| `Esc` | cancel selection |
| `a` | auto-send to foundations |
| `s` | flip stock → waste (or recycle) |
| `u` | undo |
| `n` | new game (same variant) |
| `v` | variant picker modal |
| `?` | help screen |
| `q` | quit |
| mouse click | select that card (+ any legal stack above) / drop |

## Architecture

- `pysolfc_tui/engine.py` — pure-Python rule core. Class names mirror
  PySolFC (`AC_RowStack`, `SS_FoundationStack`, `WasteTalonStack`, …) so
  the vendored upstream `engine/` tree stays cross-referenceable.
- `pysolfc_tui/render.py` — card → (text, Rich style) glyph rows.
- `pysolfc_tui/app.py` — Textual app. `TableauView` extends `ScrollView`
  and paints via `render_line`.
- `pysolfc_tui/screens.py` — Help, VariantPicker, Win modals.
- `tests/qa.py` — 19-scenario QA harness (`python -m tests.qa`).
- `tests/perf.py` — hot-path benchmarks.
- `engine/` — vendored PySolFC source (gitignored, used as rules
  reference). Clone from
  <https://github.com/shlomif/PySolFC> into `engine/` yourself.

See [`DECISIONS.md`](DECISIONS.md) for the rationale behind the
clean-room rewrite (TL;DR: PySolFC's `Game` class is Tk-canvas coupled
end-to-end, so a shim would be the bulk of the project anyway).

## Running tests

```bash
.venv/bin/python -m tests.qa            # all
.venv/bin/python -m tests.qa cursor     # scenarios matching "cursor"
.venv/bin/python -m tests.perf          # baseline benchmarks
```

All 19 scenarios pass on Textual 0.80+.

## License

GPLv3 (matches PySolFC).
