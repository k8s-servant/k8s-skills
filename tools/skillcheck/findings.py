"""The result type every skillcheck check returns.

One shared shape lets the CLI print and count problems from any check the same way.
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Finding:
    """A single problem found in the repository.

    Attributes:
        path: File or folder the problem is in, relative to the repository root.
        line: 1-based line number, or None when the problem is not tied to a line.
        message: What is wrong, in one sentence.
    """

    path: Path
    line: int | None
    message: str

    def __str__(self) -> str:
        where = f"{self.path}" if self.line is None else f"{self.path}:{self.line}"
        return f"{where}: {self.message}"
