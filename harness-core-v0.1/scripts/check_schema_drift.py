from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = Path("harness/schemas")


def schema_drift(root: Path = ROOT) -> list[str]:
    """Return Git porcelain entries for any schema drift, including untracked/ignored files."""
    result = subprocess.run(
        [
            "git",
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "--ignored=matching",
            "--",
            SCHEMA_PATH.as_posix(),
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def main() -> int:
    changes = schema_drift()
    if changes:
        print("schema drift detected under harness/schemas:", file=sys.stderr)
        for change in changes:
            print(f"  {change}", file=sys.stderr)
        return 1
    print("schema export matches the Git-tracked state")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
