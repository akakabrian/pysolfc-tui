#!/usr/bin/env python3
"""Entry point: pysolfc-tui."""
from __future__ import annotations

import argparse

from pysolfc_tui.app import run
from pysolfc_tui.engine import VARIANTS


def main() -> None:
    p = argparse.ArgumentParser(description="Terminal solitaire (PySolFC rules)")
    p.add_argument("--variant", "-v", default="Klondike",
                   choices=list(VARIANTS.keys()),
                   help="Game variant (default: Klondike). Change in-app with `v`.")
    p.add_argument("--seed", "-s", type=int, default=None,
                   help="RNG seed for reproducible deals")
    p.add_argument("--music", dest="music", action="store_true",
                   help="Start background music on launch (toggle in-app with `m`). "
                        "Off by default until the subprocess-cleanup path is fully wired.")
    args = p.parse_args()
    run(variant=args.variant, seed=args.seed, music=args.music)


if __name__ == "__main__":
    main()
