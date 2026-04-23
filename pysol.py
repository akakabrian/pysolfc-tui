#!/usr/bin/env python3
"""Entry point: pysolfc-tui."""
from __future__ import annotations

import argparse

from pysolfc_tui.app import run


def main() -> None:
    p = argparse.ArgumentParser(description="Terminal solitaire (PySolFC rules)")
    p.add_argument("--variant", "-v", default="Klondike",
                   choices=["Klondike", "FreeCell", "Spider (2-suit)"],
                   help="Game variant (default: Klondike)")
    p.add_argument("--seed", "-s", type=int, default=None,
                   help="RNG seed for reproducible deals")
    args = p.parse_args()
    run(variant=args.variant, seed=args.seed)


if __name__ == "__main__":
    main()
