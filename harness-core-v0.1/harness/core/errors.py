from __future__ import annotations

from dataclasses import dataclass

from harness.contracts import HarnessErrorCode


@dataclass(slots=True)
class HarnessResolutionError(Exception):
    """Shared Core resolution/guard error with a stable public payload."""

    code: HarnessErrorCode
    message: str
    source_ref: str | None = None

    def __str__(self) -> str:
        suffix = f" [{self.source_ref}]" if self.source_ref else ""
        return f"{self.code.value}: {self.message}{suffix}"


__all__ = ["HarnessResolutionError"]
