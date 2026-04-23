# Architecture decisions — pysolfc-tui

## 1. Engine integration: clean reimplementation, PySolFC as reference

**Context.** The task framed PySolFC as "already Python, so most work is UI
porting from Tkinter to Textual". On inspection, PySolFC is *deeply* coupled
to Tk: `pysollib/stack.py` (the core rule classes) imports `MfxCanvasGroup`,
`MfxCanvasImage`, `MfxCanvasText`, `bind`, `after_cancel`, etc. from
`pysoltk`. The canonical `Game` class manages canvas coordinates (`x, y` in
pixels) as first-class state. Every `RowStack` / `FoundationStack` /
`TalonStack` subclass expects to live inside a Tk canvas.

A full port would mean writing an `fake_pysoltk` shim that stubs every Tk
method — weeks of work, and the shim would still leak canvas assumptions
(pixel coordinates, image references, drag helpers) into our UI layer.

**Decision.** Vendor PySolFC at `engine/` as an upstream reference tree
(rule text, card set art, game-variant catalog) but implement a clean
Python rule core at `pysolfc_tui/engine.py`. Mirror PySolFC's class names
and semantics precisely (`AC_RowStack` = alternate-color descending,
`SS_FoundationStack` = same-suit ascending Ace→King, `WasteTalonStack`
flips N cards per click, etc.) so the vendored source stays
cross-referenceable. This is the "Textual-friendly interface layer"
the task anticipated — collapsed further than expected because of the
Tk coupling.

**Consequence.** Faster path to a playable game, no Tk dependency, but we
can't trivially inherit all 1000+ PySolFC variants. We target 10+
well-known ones (Klondike, FreeCell, Spider, Yukon, Canfield, Golf, etc.)
each of which is ~20 lines of rule definition on top of the core.

## 2. Card rendering: full 5×3 cards with box-drawing borders

**Context.** Simcity-tui treats every cell as a single glyph with a style.
Cards are inherently 2D — rank + suit + border + shadow. Two options:

- **Compact row:** `[A♠][2♥][3♦]…` — one line per stack, ~3 cells per card.
- **Full cards:** multi-line bordered cards with overlapping for fan stacks.

**Decision.** Full 5-wide × 4-tall cards with Unicode box-drawing borders
(`╭─╮ │A♠│ ╰─╯` style). Fan stacks overlap vertically by 3 rows (1 row of
each card visible) so 13 cards fit in a standard tableau column. The face
value sits in the top-left, suit glyph centered, duplicate corner for
symmetry. Red suits rendered `bold red` on dark parchment; black suits
`bold rgb(230,230,230)`.

This matches simcity-tui's convention of "rendering primitives earn their
space" — cards are the primary UI element so give them visual weight.

## 3. UI layout: 3-panel (Tableau / Status / Log)

**Context.** Simcity had Map / Status / Actions / Log. Solitaire doesn't
need an "actions" panel — moves are cursor/mouse driven. But it needs:
- A help/legend area for key bindings
- Game status (deal number, moves made, time, score)
- Variant selector

**Decision.** Main panel = tableau (foundations + stock/waste row on top,
tableau columns below). Right sidebar = status + legend + message log.
Modal screens (phase B) cover variant picker, win screen, help.

## 4. Input model: dual cursor + mouse

- Cursor navigates stacks (arrow keys).
- Enter/space = select / deselect / move (pick-up, then drop target).
- Mouse click on a card = select that card + cards above it.
- Mouse click on empty stack or same-stack = deselect.
- `s` = stock flip; `u` = undo; `n` = new game; `v` = variant picker.

## 5. Colors

Red suits on dark parchment, black suits on light cream — mimics the
real-world feel. Selection uses a bright yellow border overlay rather
than changing the card color. Legal-drop targets glow green-bordered
when a card is picked up.

## 6. Testing approach

Follow simcity-tui's `tests/qa.py` + `Pilot` exactly. Scenarios:
mount, deal shape, cursor move, cursor clamp, stock flip, legal move,
illegal move rejected, foundation auto-send, win detection, undo.
