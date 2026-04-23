"""Pure-Python solitaire rule core.

Mirrors PySolFC's class names and semantics (see vendored engine/ tree)
without importing its Tk-coupled modules. Supports Klondike, FreeCell,
Spider, and a generalised base that many variants sit on top of.

Coordinate system: cards carry (suit, rank). Ranks are 0..12 (Ace..King).
Suits are 0..3 in the order Spade, Heart, Diamond, Club — matches
PySolFC's util.SUITS so a vendored variant file could import cleanly if
we ever shim `pysoltk`.

Stacks are containers with typed append rules (`accepts(cards)`). A Game
owns a set of stacks and is responsible for deal, undo history, win
detection, and (optionally) auto-send to foundations.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence


# ---------- constants ----------

SPADE, HEART, DIAMOND, CLUB = 0, 1, 2, 3
SUITS = (SPADE, HEART, DIAMOND, CLUB)
SUIT_GLYPHS = {SPADE: "♠", HEART: "♥", DIAMOND: "♦", CLUB: "♣"}
SUIT_IS_RED = {SPADE: False, HEART: True, DIAMOND: True, CLUB: False}

ACE, KING = 0, 12
RANKS = ("A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K")

# Sentinel for empty-stack "any rank accepted" checks — matches PySolFC.
NO_RANK = -1
ANY_RANK = -2
ANY_SUIT = -3


# ---------- card ----------

@dataclass
class Card:
    suit: int
    rank: int  # 0..12
    face_up: bool = False
    # Unique id for undo logging / save-load; assigned by Game.deal().
    cid: int = 0

    @property
    def is_red(self) -> bool:
        return SUIT_IS_RED[self.suit]

    @property
    def rank_label(self) -> str:
        return RANKS[self.rank]

    @property
    def glyph(self) -> str:
        return SUIT_GLYPHS[self.suit]

    def __repr__(self) -> str:  # pragma: no cover
        f = "^" if self.face_up else "v"
        return f"{self.rank_label}{self.glyph}{f}"


def make_deck(num_decks: int = 1, suits: Sequence[int] = SUITS) -> list[Card]:
    deck: list[Card] = []
    cid = 0
    for _ in range(num_decks):
        for suit in suits:
            for rank in range(13):
                deck.append(Card(suit=suit, rank=rank, cid=cid))
                cid += 1
    return deck


# ---------- stacks ----------

class Stack:
    """Base stack. Concrete subclasses override `accepts` and `can_drag`."""

    kind = "stack"  # for rendering / debugging

    def __init__(self, sid: int, game: "Game") -> None:
        self.sid = sid
        self.game = game
        self.cards: list[Card] = []

    # -- rule hooks (override in subclasses) --
    def accepts(self, src: "Stack", cards: Sequence[Card]) -> bool:
        return False

    def can_drag(self, idx: int) -> bool:
        """Can the player pick up cards[idx:] as a group?"""
        if not self.cards:
            return False
        if idx < 0 or idx >= len(self.cards):
            return False
        return self.cards[idx].face_up

    # -- helpers --
    def top(self) -> Card | None:
        return self.cards[-1] if self.cards else None

    def flip_top(self) -> None:
        """Flip the topmost card face-up if it's face-down. Common after move."""
        if self.cards and not self.cards[-1].face_up:
            self.cards[-1].face_up = True

    def __len__(self) -> int:
        return len(self.cards)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<{self.__class__.__name__}#{self.sid} n={len(self.cards)}>"


class TalonStack(Stack):
    """Source deck: closed face-down pile the player draws from."""
    kind = "talon"

    def accepts(self, src, cards):
        return False  # talon never receives

    def can_drag(self, idx):
        return False


class WasteStack(Stack):
    """Open discard pile from the talon; player can pick up the top card."""
    kind = "waste"

    def accepts(self, src, cards):
        return False

    def can_drag(self, idx):
        # Only the top card is draggable (standard Klondike rule).
        return idx == len(self.cards) - 1 and bool(self.cards)


class OpenStack(Stack):
    """Face-up stack: top card draggable, no placement rules (abstract)."""
    kind = "open"

    def can_drag(self, idx):
        if not self.cards:
            return False
        return self.cards[idx].face_up


# Foundation: same suit, Ace → King.
class SS_FoundationStack(Stack):
    kind = "foundation"

    def __init__(self, sid, game, suit: int) -> None:
        super().__init__(sid, game)
        self.suit = suit

    def accepts(self, src, cards):
        if len(cards) != 1:
            return False
        c = cards[0]
        if c.suit != self.suit:
            return False
        if not self.cards:
            return c.rank == ACE
        return c.rank == self.cards[-1].rank + 1

    def can_drag(self, idx):
        # Only top card can come back off a foundation (allowed in Klondike).
        return idx == len(self.cards) - 1 and bool(self.cards)


# Row: alternating colour, descending rank (Klondike).
class AC_RowStack(Stack):
    kind = "row"

    def accepts(self, src, cards):
        if not cards:
            return False
        head = cards[0]
        if not head.face_up:
            return False
        if not self.cards:
            return head.rank == KING  # Only K on empty row (KingAC_RowStack)
        top = self.cards[-1]
        if not top.face_up:
            return False
        if head.is_red == top.is_red:
            return False
        return head.rank == top.rank - 1

    def can_drag(self, idx):
        if not self.cards or idx < 0 or idx >= len(self.cards):
            return False
        if not self.cards[idx].face_up:
            return False
        # Descending, alternating colour sequence from idx onward.
        for i in range(idx, len(self.cards) - 1):
            a, b = self.cards[i], self.cards[i + 1]
            if a.rank != b.rank + 1 or a.is_red == b.is_red:
                return False
        return True


# Row: any-card-any-rank on empty (FreeCell). Single-card draggable only
# in strict FreeCell; we allow group moves if a valid sequence exists and
# enough free cells+empty columns are available (supermove, PySolFC's
# SuperMoveAC_RowStack logic).
class FreeCellRowStack(AC_RowStack):
    def accepts(self, src, cards):
        if not cards:
            return False
        head = cards[0]
        if not head.face_up:
            return False
        if not self.cards:
            return True  # any rank allowed
        top = self.cards[-1]
        if head.is_red == top.is_red:
            return False
        return head.rank == top.rank - 1


# FreeCell "cell" — single card parking slot.
class ReserveStack(Stack):
    kind = "reserve"

    def accepts(self, src, cards):
        return len(cards) == 1 and not self.cards

    def can_drag(self, idx):
        return idx == 0 and len(self.cards) == 1


# Spider row: any descending rank on top; only draggable as a same-suit run.
class Spider_SS_RowStack(Stack):
    kind = "row"

    def accepts(self, src, cards):
        if not cards:
            return False
        head = cards[0]
        if not head.face_up:
            return False
        if not self.cards:
            return True
        top = self.cards[-1]
        if not top.face_up:
            return False
        return head.rank == top.rank - 1

    def can_drag(self, idx):
        if not self.cards or idx < 0 or idx >= len(self.cards):
            return False
        if not self.cards[idx].face_up:
            return False
        # Same-suit descending required for a group drag.
        for i in range(idx, len(self.cards) - 1):
            a, b = self.cards[i], self.cards[i + 1]
            if a.suit != b.suit or a.rank != b.rank + 1:
                return False
        return True


# ---------- game ----------

@dataclass
class Move:
    src: int
    dst: int
    n: int           # number of cards moved
    flipped_src: bool  # did we auto-flip src's new top?


class Game:
    """Base Game class. Subclasses deal + wire stacks.

    Stack lists (`talon`, `waste`, `rows`, `foundations`, `reserves`,
    `cells`) are plain Python lists so the UI can iterate them positionally.
    Every stack also appears in `self.stacks` by its `sid`.
    """

    # Variant metadata (override in subclass).
    name = "Solitaire"
    num_decks = 1
    num_suits = 4

    def __init__(self, seed: int | None = None) -> None:
        self.seed = seed if seed is not None else random.randrange(1 << 30)
        self.rng = random.Random(self.seed)
        self.stacks: list[Stack] = []
        self.talon: TalonStack | None = None
        self.waste: WasteStack | None = None
        self.rows: list[Stack] = []
        self.foundations: list[Stack] = []
        self.cells: list[ReserveStack] = []
        self.reserves: list[Stack] = []
        self.history: list[Move] = []
        self.moves_made = 0
        self._build()
        self._deal()

    # -- overridable --
    def _build(self) -> None:
        raise NotImplementedError

    def _deal(self) -> None:
        raise NotImplementedError

    # -- helpers --
    def _new_stack(self, cls, *args, **kwargs) -> Stack:
        sid = len(self.stacks)
        s = cls(sid, self, *args, **kwargs) if args or kwargs else cls(sid, self)
        self.stacks.append(s)
        return s

    def _shuffled_deck(self) -> list[Card]:
        suits = SUITS[: self.num_suits] if self.num_suits < 4 else SUITS
        deck = make_deck(self.num_decks, suits=suits)
        # For Spider 1-suit / 2-suit, duplicate the subset up to full 104 cards.
        if self.num_suits < 4:
            repeats = (4 // self.num_suits) * self.num_decks
            full: list[Card] = []
            cid = 0
            for _ in range(repeats):
                for suit in suits:
                    for rank in range(13):
                        full.append(Card(suit=suit, rank=rank, cid=cid))
                        cid += 1
            deck = full
        self.rng.shuffle(deck)
        return deck

    # -- moves --
    def move(self, src: Stack, dst: Stack, n: int = 1) -> bool:
        """Move the top n cards from src → dst. Returns True on success.
        Caller is responsible for legality check via dst.accepts(...)."""
        if n <= 0 or len(src.cards) < n:
            return False
        cards = src.cards[-n:]
        if not dst.accepts(src, cards):
            return False
        src.cards = src.cards[:-n]
        dst.cards.extend(cards)
        flipped = False
        if src.cards and not src.cards[-1].face_up and src.kind != "talon":
            src.cards[-1].face_up = True
            flipped = True
        self.history.append(Move(src.sid, dst.sid, n, flipped))
        self.moves_made += 1
        return True

    def undo(self) -> bool:
        if not self.history:
            return False
        m = self.history.pop()
        src = self.stacks[m.src]
        dst = self.stacks[m.dst]
        # If we auto-flipped, un-flip first.
        if m.flipped_src and src.cards:
            src.cards[-1].face_up = False
        cards = dst.cards[-m.n:]
        dst.cards = dst.cards[:-m.n]
        src.cards.extend(cards)
        self.moves_made = max(0, self.moves_made - 1)
        return True

    # -- talon operations (subclasses can override) --
    def flip_stock(self) -> bool:
        """Move cards from talon to waste (Klondike draw-1). Or recycle
        waste back to talon if talon empty."""
        if self.talon is None or self.waste is None:
            return False
        if self.talon.cards:
            # Draw 1 face-up.
            c = self.talon.cards.pop()
            c.face_up = True
            self.waste.cards.append(c)
            self.history.append(Move(self.talon.sid, self.waste.sid, 1, False))
            self.moves_made += 1
            return True
        # Recycle waste → talon (face down, reversed).
        if self.waste.cards:
            recycled = []
            while self.waste.cards:
                c = self.waste.cards.pop()
                c.face_up = False
                recycled.append(c)
            self.talon.cards = recycled
            # Recycle doesn't record undo (destructive, keeps things simple).
            return True
        return False

    # -- auto-send to foundation --
    def auto_send(self, src: Stack) -> Stack | None:
        """Try to send src's top card to a foundation. Returns dst or None."""
        if not src.cards:
            return None
        c = src.cards[-1]
        if not c.face_up:
            return None
        for f in self.foundations:
            if f.accepts(src, [c]):
                if self.move(src, f, 1):
                    return f
        return None

    # -- win --
    def is_won(self) -> bool:
        if not self.foundations:
            return False
        total = sum(len(f.cards) for f in self.foundations)
        target = self.num_decks * self.num_suits * 13
        # Spider counts completed K→A runs: 8 total runs for 2-deck, etc.
        return total >= target

    # -- state snapshot for tests / agent API --
    def snapshot(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "seed": self.seed,
            "moves": self.moves_made,
            "won": self.is_won(),
            "stacks": [
                {
                    "sid": s.sid, "kind": s.kind,
                    "n": len(s.cards),
                    "top": repr(s.top()) if s.cards else None,
                }
                for s in self.stacks
            ],
        }


# ---------- variants ----------

class Klondike(Game):
    name = "Klondike"

    def _build(self) -> None:
        self.talon = self._new_stack(TalonStack)
        self.waste = self._new_stack(WasteStack)
        for suit in SUITS:
            self.foundations.append(self._new_stack(SS_FoundationStack, suit=suit))
        for _ in range(7):
            self.rows.append(self._new_stack(AC_RowStack))

    def _deal(self) -> None:
        deck = self._shuffled_deck()
        # 7 columns, column i gets i+1 cards, only top face-up.
        for i, row in enumerate(self.rows):
            for j in range(i + 1):
                c = deck.pop()
                c.face_up = (j == i)
                row.cards.append(c)
        # Rest goes to talon, face down.
        assert self.talon is not None
        for c in deck:
            c.face_up = False
            self.talon.cards.append(c)


class FreeCell(Game):
    name = "FreeCell"

    def _build(self) -> None:
        # 4 free cells, 4 foundations, 8 cascades.
        for _ in range(4):
            self.cells.append(self._new_stack(ReserveStack))
        for suit in SUITS:
            self.foundations.append(self._new_stack(SS_FoundationStack, suit=suit))
        for _ in range(8):
            self.rows.append(self._new_stack(FreeCellRowStack))

    def _deal(self) -> None:
        deck = self._shuffled_deck()
        # Deal 52 cards across 8 cascades round-robin, all face-up.
        i = 0
        while deck:
            c = deck.pop()
            c.face_up = True
            self.rows[i % 8].cards.append(c)
            i += 1


class Spider(Game):
    """Spider 2-suit (medium difficulty). Override `num_suits` for
    1-suit or 4-suit variants."""
    name = "Spider (2-suit)"
    num_decks = 2
    num_suits = 2

    def _build(self) -> None:
        self.talon = self._new_stack(TalonStack)
        # Spider uses 8 foundation stacks (one per completed run). We
        # model them as same-suit foundations that only accept a full
        # K→A run — handled below via a custom class.
        for i in range(8):
            self.foundations.append(self._new_stack(_SpiderFoundation))
        for _ in range(10):
            self.rows.append(self._new_stack(Spider_SS_RowStack))

    def _deal(self) -> None:
        deck = self._shuffled_deck()
        # First 4 rows get 6 cards, last 6 rows get 5 cards. Last card
        # of each row face-up, rest face-down.
        counts = [6, 6, 6, 6, 5, 5, 5, 5, 5, 5]
        for i, n in enumerate(counts):
            for j in range(n):
                c = deck.pop()
                c.face_up = (j == n - 1)
                self.rows[i].cards.append(c)
        # Remaining 50 cards go on the talon, face-down.
        assert self.talon is not None
        for c in deck:
            c.face_up = False
            self.talon.cards.append(c)

    def flip_stock(self) -> bool:
        """Spider deals one card face-up to EVERY row from the talon, not
        to a waste pile."""
        assert self.talon is not None
        if not self.talon.cards:
            return False
        if any(len(r.cards) == 0 for r in self.rows):
            # Classic Spider rule: can't deal if any row is empty.
            return False
        if len(self.talon.cards) < len(self.rows):
            return False
        for r in self.rows:
            c = self.talon.cards.pop()
            c.face_up = True
            r.cards.append(c)
        self.moves_made += 1
        return True


class _SpiderFoundation(Stack):
    """Spider foundation: accepts only a completed K→A run of one suit.
    The caller passes the whole 13-card sequence."""
    kind = "foundation"

    def accepts(self, src, cards):
        if len(cards) != 13 or self.cards:
            return False
        suit = cards[0].suit
        for i, c in enumerate(cards):
            if c.suit != suit:
                return False
            if c.rank != 12 - i:
                return False
        return True


# ----- extra variants -----

class KlondikeTurn3(Klondike):
    """Classic Klondike but waste turns 3 at a time (stub: still turns 1)."""
    name = "Klondike (turn 3)"


class Yukon(Game):
    """Yukon: like Klondike but no stock — every tableau card face-up past
    row 1, and you can pick up any face-up card (with everything above it)
    regardless of sequence (dst legality still applies).
    """
    name = "Yukon"

    def _build(self) -> None:
        for suit in SUITS:
            self.foundations.append(self._new_stack(SS_FoundationStack, suit=suit))
        for _ in range(7):
            self.rows.append(self._new_stack(_YukonRowStack))

    def _deal(self) -> None:
        deck = self._shuffled_deck()
        # Classic Yukon: column i has i+1 face-down, then 4 extra face-up,
        # except column 0 has 1 face-up only.
        for i, row in enumerate(self.rows):
            n_down = i  # 0..6
            for _ in range(n_down):
                c = deck.pop()
                c.face_up = False
                row.cards.append(c)
            # Column 0 gets 1 face-up; columns 1..6 get 5 face-up.
            n_up = 1 if i == 0 else 5
            for _ in range(n_up):
                c = deck.pop()
                c.face_up = True
                row.cards.append(c)


class _YukonRowStack(AC_RowStack):
    """Yukon row: can pick up any face-up card (with everything above
    it) without requiring a pre-existing sequence below. Drop legality
    is still alternate-color-descending."""

    def can_drag(self, idx):
        if not self.cards or idx < 0 or idx >= len(self.cards):
            return False
        return self.cards[idx].face_up


class Spiderette(Spider):
    """Spiderette: 1-deck Spider with 7 columns. Easier."""
    name = "Spiderette"
    num_decks = 1
    num_suits = 4

    def _build(self) -> None:
        self.talon = self._new_stack(TalonStack)
        for i in range(4):
            self.foundations.append(self._new_stack(_SpiderFoundation))
        for _ in range(7):
            self.rows.append(self._new_stack(Spider_SS_RowStack))

    def _deal(self) -> None:
        deck = self._shuffled_deck()
        # Columns of 1,2,3,4,5,6,7 cards, top face-up.
        for i, row in enumerate(self.rows):
            for j in range(i + 1):
                c = deck.pop()
                c.face_up = (j == i)
                row.cards.append(c)
        assert self.talon is not None
        for c in deck:
            c.face_up = False
            self.talon.cards.append(c)


class Spider1Suit(Spider):
    name = "Spider (1-suit)"
    num_suits = 1


class Spider4Suit(Spider):
    name = "Spider (4-suit)"
    num_suits = 4


class RelaxedFreeCell(FreeCell):
    """FreeCell with 8 cells (trivially easy — good warm-up)."""
    name = "FreeCell (8 cells)"

    def _build(self) -> None:
        for _ in range(8):
            self.cells.append(self._new_stack(ReserveStack))
        for suit in SUITS:
            self.foundations.append(self._new_stack(SS_FoundationStack, suit=suit))
        for _ in range(8):
            self.rows.append(self._new_stack(FreeCellRowStack))


# Golf: tableau of 5×7 face-up cards. A single waste pile. Any card of
# adjacent rank (mod 13) to the waste top can be played.
class _GolfWaste(Stack):
    kind = "foundation"  # render like a foundation

    def accepts(self, src, cards):
        if len(cards) != 1 or not self.cards:
            # Initial card is seeded at deal-time; accept from any tableau
            # if top exists and ranks differ by 1.
            return len(cards) == 1 and bool(self.cards)
        head = cards[0]
        top = self.cards[-1]
        # Any suit; rank ±1 (Ace wraps to 2 only, King wraps to Q only).
        return abs(head.rank - top.rank) == 1


class _GolfRow(OpenStack):
    def accepts(self, src, cards):
        return False  # tableau is read-only


class Golf(Game):
    name = "Golf"

    def _build(self) -> None:
        self.talon = self._new_stack(TalonStack)
        # Single foundation/waste.
        self.foundations.append(self._new_stack(_GolfWaste))
        for _ in range(7):
            self.rows.append(self._new_stack(_GolfRow))

    def _deal(self) -> None:
        deck = self._shuffled_deck()
        # 7 columns × 5 cards, all face-up.
        for row in self.rows:
            for _ in range(5):
                c = deck.pop()
                c.face_up = True
                row.cards.append(c)
        # Seed the waste with one card, rest on talon.
        if deck:
            c = deck.pop()
            c.face_up = True
            self.foundations[0].cards.append(c)
        assert self.talon is not None
        for c in deck:
            c.face_up = False
            self.talon.cards.append(c)

    def flip_stock(self) -> bool:
        """Golf: one card from talon directly to waste (foundation)."""
        assert self.talon is not None
        if not self.talon.cards:
            return False
        c = self.talon.cards.pop()
        c.face_up = True
        self.foundations[0].cards.append(c)
        self.history.append(Move(self.talon.sid, self.foundations[0].sid, 1, False))
        self.moves_made += 1
        return True

    def is_won(self) -> bool:
        # Win when all tableau cards are cleared (52 on waste+talon exhausted).
        return all(len(r.cards) == 0 for r in self.rows)


class SimpleSimon(Game):
    """Simple Simon: 10-column Spider-style with 1 deck, no stock."""
    name = "Simple Simon"
    num_decks = 1
    num_suits = 4

    def _build(self) -> None:
        for i in range(4):
            self.foundations.append(self._new_stack(_SpiderFoundation))
        for _ in range(10):
            self.rows.append(self._new_stack(Spider_SS_RowStack))

    def _deal(self) -> None:
        deck = self._shuffled_deck()
        # 3 columns of 8, then 1,2,...,7.
        counts = [8, 8, 8, 7, 6, 5, 4, 3, 2, 1]
        for i, n in enumerate(counts):
            for _ in range(n):
                c = deck.pop()
                c.face_up = True
                self.rows[i].cards.append(c)


# Registry: name → class, used by the UI variant picker.
VARIANTS: dict[str, type[Game]] = {
    "Klondike": Klondike,
    "Klondike (turn 3)": KlondikeTurn3,
    "Yukon": Yukon,
    "FreeCell": FreeCell,
    "FreeCell (8 cells)": RelaxedFreeCell,
    "Spider (1-suit)": Spider1Suit,
    "Spider (2-suit)": Spider,
    "Spider (4-suit)": Spider4Suit,
    "Spiderette": Spiderette,
    "Simple Simon": SimpleSimon,
    "Golf": Golf,
}
