# DOGFOOD — pysolfc-tui

_Session: 2026-04-23T22:06:16, driver: pilot, duration: 5.0 min_

**PASS** — ran for 1.3m, captured 10 snap(s), 4 milestone(s), 0 blocker(s), 0 major(s).

## Summary

Ran a rule-based exploratory session via `pilot` driver. Found no findings worth flagging. Game reached 4 unique state snapshots. Captured 4 milestone shot(s); top candidates promoted to `screenshots/candidates/`. 4 coverage note(s) — see Coverage section.

## Findings

### Blockers

_None._

### Majors

_None._

### Minors

_None._

### Nits

_None._

### UX (feel-better-ifs)

_None._

## Coverage

- Driver backend: `pilot`
- Keys pressed: 199 (unique: 22)
- State samples: 26 (unique: 4)
- Score samples: 26
- Milestones captured: 4
- Phase durations (s): A=16.4, B=31.2, C=30.0
- Snapshots: `/home/brian/AI/projects/tui-dogfood/reports/snaps/pysolfc-tui-20260423-220458`

Unique keys exercised: /, 3, :, ?, H, R, c, down, enter, escape, h, left, n, p, question_mark, r, right, shift+slash, space, up, w, z

### Coverage notes

- **[CN1] Phase A exited early due to saturation**
  - State hash unchanged for 10 consecutive samples after 10 golden-path loop(s); no further learning expected.
- **[CN2] help modal discovered via high-value key probe**
  - Pressing '?' changed screen='Screen' → 'HelpScreen' / stack_len=1 → 2. Previously-undiscovered help surface.
- **[CN3] Phase B exited early due to saturation**
  - State hash unchanged for 10 consecutive samples during the stress probe; remaining keys skipped.
- **[CN4] help key opened a previously-undiscovered modal**
  - Pressing '?' pushed a new screen during the stress probe — worth inspecting the milestone snapshot for help-text quality.

## Milestones

| Event | t (s) | Interest | File | Note |
|---|---|---|---|---|
| first_input | 0.3 | 6738.6 | `pysolfc-tui-20260423-220458/milestones/first_input.svg` | key=right |
| first_score_gain | 1.7 | 7608.8 | `pysolfc-tui-20260423-220458/milestones/first_score_gain.svg` | 0 → 7 |
| high_density | 8.2 | 7608.8 | `pysolfc-tui-20260423-220458/milestones/high_density.svg` | interest=7608.8 |
| new_modal | 33.9 | 7722.8 | `pysolfc-tui-20260423-220458/milestones/new_modal-04.svg` | Screen → HelpScreen |
