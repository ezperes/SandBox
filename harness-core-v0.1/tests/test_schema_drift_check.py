from __future__ import annotations

import subprocess
from pathlib import Path

from scripts.check_schema_drift import schema_drift


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=check,
        capture_output=True,
        text=True,
    )


def initialized_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "ci@example.invalid")
    git(repo, "config", "user.name", "CI Test")
    schema_dir = repo / "harness" / "schemas"
    schema_dir.mkdir(parents=True)
    (schema_dir / "Existing.schema.json").write_text('{"version": 1}\n', encoding="utf-8")
    git(repo, "add", "harness/schemas/Existing.schema.json")
    git(repo, "commit", "-qm", "baseline schema")
    return repo


def test_old_git_diff_misses_new_untracked_schema_but_check_catches_it(tmp_path: Path) -> None:
    repo = initialized_repo(tmp_path)
    (repo / "harness" / "schemas" / "New.schema.json").write_text('{"new": true}\n', encoding="utf-8")

    old_check = git(repo, "diff", "--exit-code", "--", "harness/schemas", check=False)

    assert old_check.returncode == 0
    assert schema_drift(repo) == ["?? harness/schemas/New.schema.json"]


def test_check_catches_modified_tracked_schema(tmp_path: Path) -> None:
    repo = initialized_repo(tmp_path)
    (repo / "harness" / "schemas" / "Existing.schema.json").write_text('{"version": 2}\n', encoding="utf-8")

    assert schema_drift(repo) == [" M harness/schemas/Existing.schema.json"]


def test_check_is_clean_when_generated_state_matches_git(tmp_path: Path) -> None:
    repo = initialized_repo(tmp_path)

    assert schema_drift(repo) == []


def test_check_does_not_mask_ignored_generated_schema(tmp_path: Path) -> None:
    repo = initialized_repo(tmp_path)
    (repo / ".gitignore").write_text("harness/schemas/Ignored.schema.json\n", encoding="utf-8")
    (repo / "harness" / "schemas" / "Ignored.schema.json").write_text('{"ignored": true}\n', encoding="utf-8")

    assert schema_drift(repo) == ["!! harness/schemas/Ignored.schema.json"]
