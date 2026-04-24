"""Per-variant rule text — extracted from engine/html-src/rules/*.html at
package import time. Source is GPL-3.0 vendored PySolFC.
"""

from __future__ import annotations

import html
import re
from pathlib import Path

_RULES_DIR = (Path(__file__).resolve().parent.parent
              / "engine" / "html-src" / "rules")

# Map each VARIANTS key (see engine.VARIANTS) to its rule file stem.
_VARIANT_RULE_FILE: dict[str, str] = {
    "Klondike": "klondike",
    "Klondike (turn 3)": "klondike",
    "FreeCell": "freecell",
    "FreeCell (8 cells)": "freecell",
    "Spider (1-suit)": "spider",
    "Spider (2-suit)": "spider",
    "Spider (4-suit)": "spider",
    "Spiderette": "spiderette",
    "Simple Simon": "simplesimon",
    "Yukon": "yukon",
    "Golf": "golf",
}


def _html_to_text(raw: str) -> str:
    """Crude but dependency-free HTML → plain text conversion.
    Targets the specific PySolFC rule-file style (only h1/h3/p tags)."""
    s = raw
    # Section headers: h1 → uppercase title; h3 → underlined heading.
    s = re.sub(r"<h1[^>]*>(.*?)</h1>", lambda m: f"\n{m.group(1).upper()}\n{'=' * len(m.group(1))}\n",
               s, flags=re.DOTALL | re.IGNORECASE)
    s = re.sub(r"<h3[^>]*>(.*?)</h3>", lambda m: f"\n{m.group(1)}\n{'-' * len(m.group(1))}\n",
               s, flags=re.DOTALL | re.IGNORECASE)
    # Paragraphs → blank-line separated.
    s = re.sub(r"<p[^>]*>", "\n", s, flags=re.IGNORECASE)
    s = re.sub(r"</p>", "\n", s, flags=re.IGNORECASE)
    # Line breaks / lists.
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.IGNORECASE)
    s = re.sub(r"<li[^>]*>", "  • ", s, flags=re.IGNORECASE)
    # Strip all remaining tags.
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    # Collapse whitespace.
    s = re.sub(r"\n[ \t]+", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def _load_all() -> dict[str, str]:
    out: dict[str, str] = {}
    for variant, stem in _VARIANT_RULE_FILE.items():
        path = _RULES_DIR / f"{stem}.html"
        if not path.exists():
            continue
        out[variant] = _html_to_text(path.read_text(encoding="utf-8"))
    return out


RULES: dict[str, str] = _load_all()


def rules_for(variant: str) -> str:
    """Return plaintext rules for `variant`. Falls back to a stub."""
    return RULES.get(variant, f"No rules text bundled for {variant}.")
