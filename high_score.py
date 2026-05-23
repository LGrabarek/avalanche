"""High score table — top-10 store with optional localStorage persistence.

Scores are kept sorted by IQ score (descending).  On desktop the list is
session-only (resets when the process exits).  In the browser, entries are
serialised as JSON and written to window.localStorage under STORAGE_KEY,
surviving page refreshes and service-worker cache clears.

Rule 3: MAX_ENTRIES cap enforced before every insertion in HighScoreTable.add().
"""

import json
import platform as _platform
from dataclasses import dataclass
from typing import Any

MAX_ENTRIES: int = 10
MAX_NAME_LEN: int = 12         # Maximum player-name length stored per entry
STORAGE_KEY: str = "avalanche_hs_v1"
LAST_NAME_KEY: str = "avalanche_last_name_v1"  # Persists the most recently typed name


def _entry_score_key(entry: "HighScoreEntry") -> int:
    """Sort key for HighScoreEntry — higher IQ score = higher rank."""
    return entry.iq_score


@dataclass
class HighScoreEntry:
    """One persisted high-score record."""

    name: str           # Player-entered name (max MAX_NAME_LEN chars; may be empty)
    iq_score: int       # Final I.Q. score (0 when the game ends pre-VICTORY)
    stage_reached: int  # 1-based stage where the run ended
    raw_score: int      # Raw wave score (shown alongside IQ)

    def to_dict(self) -> dict[str, str | int]:
        """Serialise to a plain dict for JSON storage."""
        return {
            "name": self.name,
            "iq": self.iq_score,
            "stage": self.stage_reached,
            "raw": self.raw_score,
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "HighScoreEntry":
        """Deserialise from a JSON-decoded dict; missing keys default to empty/0/1."""
        raw_name = d.get("name", "")
        name = str(raw_name)[:MAX_NAME_LEN] if isinstance(raw_name, str) else ""
        return HighScoreEntry(
            name=name,
            iq_score=int(d.get("iq", 0)),
            stage_reached=int(d.get("stage", 1)),
            raw_score=int(d.get("raw", 0)),
        )


class HighScoreTable:
    """Sorted top-10 high score list with optional browser-side persistence.

    The list is always sorted by IQ score (highest first).  Ties are kept in
    insertion order within the same score band (stable sort).  The table
    holds at most MAX_ENTRIES entries; the lowest entry is evicted on overflow.
    """

    def __init__(self) -> None:
        self._entries: list[HighScoreEntry] = []
        self._last_name: str = ""
        self._load()
        assert len(self._entries) <= MAX_ENTRIES, (
            "loaded more entries than MAX_ENTRIES — storage may be corrupt"
        )

    @property
    def entries(self) -> tuple[HighScoreEntry, ...]:
        """Immutable snapshot of the current ranking, highest score first."""
        return tuple(self._entries)

    @property
    def last_name(self) -> str:
        """Most recently submitted player name, or '' if none recorded yet."""
        return self._last_name

    def qualifies(self, iq_score: int) -> bool:
        """Return True if `iq_score` would appear in a full top-10 table."""
        if len(self._entries) < MAX_ENTRIES:
            return True
        return iq_score > self._entries[-1].iq_score

    def save_last_name(self, name: str) -> None:
        """Persist `name` as the last-used player name to localStorage.

        Silently no-ops on desktop (no browser localStorage available).
        Any storage errors are swallowed so a failing write never crashes the game.
        """
        assert len(name) <= MAX_NAME_LEN, (
            f"name length {len(name)} exceeds MAX_NAME_LEN {MAX_NAME_LEN}"
        )
        self._last_name = name
        try:
            if not hasattr(_platform, "window"):
                return
            ls = _platform.window.localStorage  # Pygbag injects `window` into platform in WASM
            ls.setItem(LAST_NAME_KEY, name)
        except Exception:  # noqa: BLE001  -- localStorage failures must not crash the game
            pass

    def add(
        self,
        iq_score: int,
        stage_reached: int,
        raw_score: int,
        name: str = "",
    ) -> int:
        """Insert a new entry. Returns its 0-based rank, or -1 if not in table.

        If the table is already full and the new score is ≤ the lowest entry,
        the entry is not inserted and -1 is returned.  Otherwise the entry is
        inserted, the list re-sorted, the lowest entry evicted if needed, and
        the 0-based rank of the new entry returned.  Saves to localStorage.
        """
        if not self.qualifies(iq_score):
            return -1
        assert len(name) <= MAX_NAME_LEN, (
            f"name length {len(name)} exceeds MAX_NAME_LEN {MAX_NAME_LEN}"
        )
        entry = HighScoreEntry(
            name=name,
            iq_score=iq_score,
            stage_reached=stage_reached,
            raw_score=raw_score,
        )
        assert len(self._entries) < MAX_ENTRIES + 1, (
            "entries list at cap before insertion — qualifies() logic error"
        )
        self._entries.append(entry)
        self._entries.sort(key=_entry_score_key, reverse=True)
        if len(self._entries) > MAX_ENTRIES:
            _ = self._entries.pop()     # evict lowest entry; return value unused
        rank = -1
        for i, e in enumerate(self._entries):
            if e is entry:
                rank = i
                break
        if rank == -1:
            return -1   # entry was evicted (score tied at the bottom and lost)
        assert 0 <= rank < len(self._entries), (
            f"computed rank {rank} is outside [0, {len(self._entries)})"
        )
        self._save()
        return rank

    def _load(self) -> None:
        """Load persisted entries and last name from browser localStorage."""
        self._load_entries()
        self._load_last_name()

    def _load_entries(self) -> None:
        """Load high-score entries from localStorage; silent no-op on desktop."""
        try:
            if not hasattr(_platform, "window"):
                return
            ls = _platform.window.localStorage  # Pygbag injects `window` into platform in WASM
            raw = ls.getItem(STORAGE_KEY)
            if raw is None:
                return
            data = json.loads(str(raw))
            if not isinstance(data, list):
                return
            loaded: list[HighScoreEntry] = []
            for item in data:
                if not isinstance(item, dict):
                    continue
                assert len(loaded) < MAX_ENTRIES, (
                    "stored entry count exceeds MAX_ENTRIES — truncating"
                )
                loaded.append(HighScoreEntry.from_dict(item))
            self._entries = loaded
        except Exception:  # noqa: BLE001  -- broad catch; localStorage failures must not crash the game
            self._entries = []

    def _load_last_name(self) -> None:
        """Load the last-used player name from localStorage; silent no-op on desktop."""
        try:
            if not hasattr(_platform, "window"):
                return
            ls = _platform.window.localStorage  # Pygbag injects `window` into platform in WASM
            raw = ls.getItem(LAST_NAME_KEY)
            if raw is None:
                return
            self._last_name = str(raw)[:MAX_NAME_LEN]
        except Exception:  # noqa: BLE001  -- localStorage failures must not crash the game
            self._last_name = ""

    def _save(self) -> None:
        """Persist current entries to browser localStorage; silent no-op on desktop."""
        assert len(self._entries) <= MAX_ENTRIES, (
            "attempting to save more entries than MAX_ENTRIES"
        )
        try:
            if not hasattr(_platform, "window"):
                return
            ls = _platform.window.localStorage  # Pygbag injects `window` into platform in WASM
            data = [e.to_dict() for e in self._entries]
            ls.setItem(STORAGE_KEY, json.dumps(data))
        except Exception:  # noqa: BLE001  -- localStorage failures must not crash the game
            pass
