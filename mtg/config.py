"""Filesystem layout for downloaded, hand-maintained, and generated data."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Paths:
    """Locations under the data folder (default: ./data)."""

    root: Path = Path("data")

    @property
    def downloads(self) -> Path:
        """Scryfall bulk data files (not tracked in git)."""
        return self.root / "downloads"

    @property
    def manual(self) -> Path:
        """Hand-maintained data (tracked in git)."""
        return self.root / "manual"

    @property
    def output(self) -> Path:
        """Generated sites, one timestamped folder per run (not tracked in git)."""
        return self.root / "output"

    @property
    def types_file(self) -> Path:
        """Type lists from the comprehensive rules (tracked in git as a fallback)."""
        return self.root / "rules" / "types.json"

    @property
    def supercycles_file(self) -> Path:
        return self.manual / "supercycles.yaml"
