from __future__ import annotations

from threading import Thread

import pytest

from harness.adapters.sources import InMemorySourceAdapter
from harness.core.freshness import (
    StrongRevisionGuardUnavailable,
    acquire_strong_revision_guard,
    read_versioned_for_sensitive_use,
)
from harness.ports import VersionedRead, VersionedReadSet
from harness.ports.versioning import RevisionConflictError, RevisionGuardActiveError


def source() -> InMemorySourceAdapter:
    return InMemorySourceAdapter(
        {
            "A": {"revision_ref": "REV-A", "value": 1, "nested": {"x": 1}},
            "B": {"revision_ref": "REV-B", "value": 2},
            "C": {"revision_ref": "REV-C", "value": 3},
            "D": {"revision_ref": "REV-D", "value": 4},
        }
    )


def read_set(src: InMemorySourceAdapter, *refs: str) -> VersionedReadSet:
    result = VersionedReadSet()
    for ref in refs:
        read_versioned_for_sensitive_use(src, ref, result)
    return result


def test_t1_mutation_between_read_and_guard_conflicts_before_boundary():
    src = source()
    observed = read_set(src, "A")
    src.records["A"]["value"] = 2
    boundary_calls = []

    with pytest.raises(RevisionConflictError) as exc:
        acquire_strong_revision_guard(src, observed, owner_ref="TOOL:R1")
        boundary_calls.append("called")

    assert boundary_calls == []
    assert exc.value.source_ref == "A"
    assert exc.value.expected_version_token != exc.value.observed_version_token
    assert exc.value.audit_data()["guard_result"] == "REVISION_CONFLICT"


def test_t2_active_guard_excludes_concurrent_material_mutation_until_release():
    src = source()
    guard = acquire_strong_revision_guard(src, read_set(src, "A"), owner_ref="TOOL:R1")
    errors = []

    def writer():
        try:
            src.records["A"]["value"] = 2
        except Exception as exc:  # captured from the concurrent thread for assertion
            errors.append(exc)

    thread = Thread(target=writer)
    thread.start()
    thread.join(timeout=2)

    assert len(errors) == 1
    assert isinstance(errors[0], RevisionGuardActiveError)
    assert src.read("A")["value"] == 1

    src.release_revision_guard(guard)
    src.records["A"]["value"] = 2
    assert src.read("A")["value"] == 2


def test_t3_material_change_rotates_version_token_even_when_revision_ref_is_reused():
    src = source()
    before = src.read_versioned("A")

    src.records["A"]["nested"]["x"] = 99

    after = src.read_versioned("A")
    assert after.revision_ref == before.revision_ref == "REV-A"
    assert after.version_token != before.version_token
    assert after.payload["nested"]["x"] == 99


def test_t4_multi_source_compare_is_all_or_nothing_with_no_partial_guard():
    src = source()
    observed = read_set(src, "A", "B", "C")
    src.records["B"]["value"] = 20

    with pytest.raises(RevisionConflictError) as exc:
        src.acquire_revision_guard(observed, "RESUME:R1")

    assert exc.value.source_ref == "B"
    # A failed multi-source acquire must leave no partial hold on A or C.
    src.records["A"]["value"] = 10
    src.records["C"]["value"] = 30
    assert src.read("A")["value"] == 10
    assert src.read("C")["value"] == 30


def test_t5_sensitive_use_fails_closed_when_adapter_has_no_strong_guard():
    class WeakSource:
        def __init__(self):
            self.payload = {"revision_ref": "REV-1", "value": 1}

        def read(self, source_ref):
            return dict(self.payload)

        def read_versioned(self, source_ref):
            return VersionedRead(
                source_ref=source_ref,
                payload=dict(self.payload),
                revision_ref="REV-1",
                version_token="WEAK-V1",
            )

    weak = WeakSource()
    observed = VersionedReadSet()
    read_versioned_for_sensitive_use(weak, "A", observed)
    boundary_calls = []

    with pytest.raises(StrongRevisionGuardUnavailable):
        acquire_strong_revision_guard(weak, observed, owner_ref="TOOL:R1")
        boundary_calls.append("called")

    assert boundary_calls == []


def test_t6_guard_release_is_idempotent():
    src = source()
    guard = src.acquire_revision_guard(read_set(src, "A"), "TOOL:R1")

    src.release_revision_guard(guard)
    released_at = guard.released_at
    src.release_revision_guard(guard)

    assert guard.guard_result == "RELEASED"
    assert guard.released_at == released_at
    src.records["A"]["value"] = 5
    assert src.read("A")["value"] == 5


def test_t7_stale_generation_cannot_release_or_reuse_new_guard():
    src = source()
    first = src.acquire_revision_guard(read_set(src, "A"), "TOOL:R1")
    src.release_revision_guard(first)

    second = src.acquire_revision_guard(read_set(src, "A"), "TOOL:R1")
    assert second.generation > first.generation

    # A stale release is a no-op and must not release the current generation.
    src.release_revision_guard(first)
    with pytest.raises(RevisionGuardActiveError):
        src.records["A"]["value"] = 7

    src.release_revision_guard(second)
    src.records["A"]["value"] = 7
    assert src.read("A")["value"] == 7


def test_t8_source_outside_read_set_does_not_invalidate_or_block_guard():
    src = source()
    observed = read_set(src, "A")
    guard = src.acquire_revision_guard(observed, "TOOL:R1")

    src.records["D"]["value"] = 40

    assert src.read("D")["value"] == 40
    assert guard.guard_result == "ACQUIRED"
    src.release_revision_guard(guard)


def test_t9_source_inside_read_set_causes_conflict_if_changed_before_acquire():
    src = source()
    observed = read_set(src, "A", "C")
    before = observed.get("C")
    src.records["C"]["value"] = 31

    with pytest.raises(RevisionConflictError) as exc:
        src.acquire_revision_guard(observed, "TOOL:R1")

    assert exc.value.source_ref == "C"
    assert exc.value.expected_version_token == before.version_token
    assert exc.value.observed_version_token == src.read_versioned("C").version_token


def test_guard_and_conflict_expose_internal_audit_shape_without_pydantic_contracts():
    src = source()
    observed = read_set(src, "A")
    guard = src.acquire_revision_guard(observed, "RUN:R1")
    acquired = guard.audit_data()

    assert acquired["guard_id"].startswith("RG-")
    assert acquired["guard_owner_ref"] == "RUN:R1"
    assert acquired["guard_result"] == "ACQUIRED"
    assert acquired["protected_versions"] == [
        {
            "source_ref": "A",
            "revision_ref": "REV-A",
            "version_token": observed.get("A").version_token,
        }
    ]

    src.release_revision_guard(guard)
    released = guard.audit_data()
    assert released["guard_result"] == "RELEASED"
    assert released["guard_released_at"] is not None
