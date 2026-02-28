from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AppConfig:
    database_path: Path = Path("agent_fleet.db")
    runtime_dir: Path = Path("runtime")

    @property
    def pid_file_path(self) -> Path:
        return self.runtime_dir / "orchestrator.pid"

    @property
    def log_file_path(self) -> Path:
        return self.runtime_dir / "orchestrator.log"

    @classmethod
    def from_paths(
        cls,
        *,
        database_path: str | Path = Path("agent_fleet.db"),
        runtime_dir: str | Path = Path("runtime"),
    ) -> "AppConfig":
        return cls(database_path=Path(database_path), runtime_dir=Path(runtime_dir))
