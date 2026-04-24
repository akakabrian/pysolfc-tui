"""Background music — fire-and-forget looping subprocess.

Plays an MP3 from `pysolfc_tui/assets/music/` via `paplay` (PulseAudio /
PipeWire on Linux) or `afplay` (macOS). Silent on failure — no audio
pipeline, SSH session, or missing player all degrade to a no-op rather
than exploding. Stop on app exit.

Format note: MP3 only. macOS `afplay` does not decode OGG; Linux
`aplay` does not decode MP3. paplay + afplay is the portable pair.
"""

from __future__ import annotations

import atexit
import ctypes
import os
import random
import shutil
import signal
import subprocess
import sys
from pathlib import Path


_ACTIVE: list["MusicPlayer"] = []


def _install_parent_death_trap() -> None:
    """On Linux, ask the kernel to SIGTERM us when the parent Python dies.

    Ensures the bash loop + paplay subprocess die whenever the Textual
    app exits — even on SIGKILL, terminal-window close, crash. macOS
    has no direct equivalent; we fall back to atexit + on_unmount.
    """
    if not sys.platform.startswith("linux"):
        return
    try:
        libc = ctypes.CDLL("libc.so.6", use_errno=True)
        # PR_SET_PDEATHSIG = 1; signal.SIGTERM propagates cleanly.
        libc.prctl(1, signal.SIGTERM)
    except (OSError, AttributeError):
        pass


@atexit.register
def _kill_all_players() -> None:
    for p in list(_ACTIVE):
        try:
            p.stop()
        except Exception:
            pass

MUSIC_DIR = Path(__file__).resolve().parent / "assets" / "music"

# Tracks assigned to pysolfc in the tui-music manifest (puzzle_relaxed bucket).
# Both are CC-BY 4.0 — attribution shown in the `?` help modal.
TRACKS: list[Path] = [
    MUSIC_DIR / "km_wallpaper.mp3",
    MUSIC_DIR / "km_dewdrop_fantasy.mp3",
]

ATTRIBUTIONS = [
    "Wallpaper — Kevin MacLeod (incompetech.com), CC-BY 4.0",
    "Dewdrop Fantasy — Kevin MacLeod (incompetech.com), CC-BY 4.0",
]


def _detect_player() -> list[str] | None:
    for cmd in (["paplay"], ["afplay"]):
        if shutil.which(cmd[0]):
            return cmd
    return None


class MusicPlayer:
    def __init__(self, enabled: bool = True,
                 tracks: list[Path] | None = None) -> None:
        self.tracks = [t for t in (tracks or TRACKS) if t.exists()]
        self.enabled = enabled and bool(self.tracks)
        self._player = _detect_player() if self.enabled else None
        self._proc: subprocess.Popen | None = None
        if self.enabled and self._player is None:
            self.enabled = False

    def start(self) -> None:
        if not self.enabled or self._proc is not None or not self.tracks:
            return
        track = random.choice(self.tracks)
        try:
            player_cmd = " ".join(self._player or [])
            loop_cmd = f'while true; do {player_cmd} "{track}" >/dev/null 2>&1; done'
            self._proc = subprocess.Popen(
                ["bash", "-c", loop_cmd],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
                preexec_fn=_install_parent_death_trap,
            )
            if self not in _ACTIVE:
                _ACTIVE.append(self)
        except (OSError, FileNotFoundError):
            self.enabled = False

    def stop(self) -> None:
        if self._proc is None:
            return
        try:
            os.killpg(os.getpgid(self._proc.pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
        try:
            self._proc.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(self._proc.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
        self._proc = None
        if self in _ACTIVE:
            _ACTIVE.remove(self)

    @property
    def is_playing(self) -> bool:
        return self._proc is not None

    def toggle(self) -> bool:
        """Flip mute state. Returns True if now playing."""
        if self.is_playing:
            self.stop()
            return False
        self.start()
        return self.is_playing
