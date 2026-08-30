from pathlib import Path


HARNESS_ROOT = Path(__file__).resolve().parents[1] / "harness"


def test_red_team_no_parallel_revision_lease_or_runtime_fence_family():
    """Known REWORK pattern: do not create a second revision-proof subsystem.

    This is a structural tripwire only. Passing it is necessary, not sufficient:
    the active TOCTOU probes must still prove that Tool and Runtime boundaries
    are protected through the canonical VersionedReadSet + strong Revision Guard
    infrastructure on the future frozen integration SHA.
    """
    forbidden_symbols = ("RevisionLeasePort", "RuntimeResumeFence")
    hits: list[str] = []

    for path in HARNESS_ROOT.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for symbol in forbidden_symbols:
            if symbol in text:
                hits.append(f"{path.relative_to(HARNESS_ROOT.parent)}:{symbol}")

    assert not hits, (
        "parallel revision/fence family detected; converge on the existing "
        "VersionedReadSet + strong Revision Guard infrastructure instead: "
        + ", ".join(sorted(hits))
    )
