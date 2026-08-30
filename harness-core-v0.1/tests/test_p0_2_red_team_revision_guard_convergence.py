from pathlib import Path


HARNESS_ROOT = Path(__file__).resolve().parents[1] / "harness"


def test_red_team_no_parallel_revision_protection_family():
    """RT-12 structural tripwire: exactly one revision-proof family may remain."""
    forbidden_symbols = (
        "RevisionLeasePort",
        "RuntimeResumeFence",
        "ToolBoundaryFence",
        "RevisionFenceSource",
    )
    hits: list[str] = []

    for path in HARNESS_ROOT.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for symbol in forbidden_symbols:
            if symbol in text:
                hits.append(f"{path.relative_to(HARNESS_ROOT.parent)}:{symbol}")

    assert not hits, (
        "parallel revision/fence family detected; converge on the existing "
        "VersionedReadSet + RevisionGuard infrastructure instead: "
        + ", ".join(sorted(hits))
    )
