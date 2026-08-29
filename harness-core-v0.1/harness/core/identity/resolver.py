from __future__ import annotations

from pydantic import ValidationError

from harness.contracts import AgentIdentity, HarnessErrorCode
from harness.core.errors import HarnessResolutionError
from harness.ports import SourcePort


class IdentityResolver:
    """Resolve AgentIdentity exclusively from a canonical SourcePort."""

    def __init__(self, source: SourcePort):
        self.source = source

    def resolve(self, source_ref: str) -> AgentIdentity:
        try:
            raw = self.source.read(source_ref)
        except Exception as exc:  # adapter boundary
            raise HarnessResolutionError(
                HarnessErrorCode.IDENTITY_UNRESOLVED,
                f"identity source could not be read: {exc}",
                source_ref,
            ) from exc

        payload = dict(raw.get("identity", raw))
        payload.setdefault("source_ref", source_ref)
        if raw.get("revision_ref") and not payload.get("source_revision_ref"):
            payload["source_revision_ref"] = raw["revision_ref"]

        try:
            identity = AgentIdentity.model_validate(payload)
        except (ValidationError, TypeError, ValueError) as exc:
            raise HarnessResolutionError(
                HarnessErrorCode.IDENTITY_UNRESOLVED,
                f"identity payload is invalid: {exc}",
                source_ref,
            ) from exc

        if identity.source_ref != source_ref:
            raise HarnessResolutionError(
                HarnessErrorCode.IDENTITY_UNRESOLVED,
                "identity source_ref does not match the canonical source requested",
                source_ref,
            )
        return identity
