from harness.contracts import HarnessErrorCode
from harness.core.errors import HarnessResolutionError
from harness.core.identity import HarnessResolutionError as LegacyHarnessResolutionError


def test_core_errors_is_canonical_owner_and_legacy_identity_import_is_compatible():
    assert LegacyHarnessResolutionError is HarnessResolutionError


def test_resolution_error_public_semantics_are_preserved():
    error = HarnessResolutionError(
        HarnessErrorCode.CHECKPOINT_INVALID,
        "checkpoint/run mismatch",
        "CP-1",
    )

    assert error.code == HarnessErrorCode.CHECKPOINT_INVALID
    assert error.message == "checkpoint/run mismatch"
    assert error.source_ref == "CP-1"
    assert str(error) == "CHECKPOINT_INVALID: checkpoint/run mismatch [CP-1]"


def test_resolution_error_without_source_ref_keeps_existing_string_shape():
    error = HarnessResolutionError(HarnessErrorCode.IDENTITY_UNRESOLVED, "identity payload is invalid")
    assert str(error) == "IDENTITY_UNRESOLVED: identity payload is invalid"
