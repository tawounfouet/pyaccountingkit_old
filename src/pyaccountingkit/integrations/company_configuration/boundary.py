"""Anti-corruption adapters between historical accounting and proposed configuration.

The historical accounting EntityId is an opaque string. Proposed Company
Configuration LegalEntityId uses a UUID. There is NO implicit conversion,
membership inference, tenant authorization, or data migration in this module.

Existing accounting period dates are inclusive; the proposed configuration
effective interval is half-open. Convert only at the integration boundary.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from types import MappingProxyType
from uuid import UUID

from pyaccountingkit.core.errors import EntityScopeMismatchError
from pyaccountingkit.core.identifiers import EntityId
from pyaccountingkit.domain.periods.accounting_period import AccountingPeriod


def _required_text(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"{field} must be non-empty and trimmed")


@dataclass(frozen=True, slots=True)
class LegacyEntityBinding:
    """Explicitly approved correspondence, NOT an ownership or IAM grant.

    `evidence_ref` is a reference to a separately governed reconciliation
    decision, not a signature or proof of authorization by itself.
    """

    tenant_id: str
    company_id: UUID
    legal_entity_id: UUID
    accounting_entity_id: EntityId
    evidence_ref: str

    def __post_init__(self) -> None:
        _required_text(self.tenant_id, "tenant_id")
        if type(self.company_id) is not UUID or type(self.legal_entity_id) is not UUID:
            raise ValueError("Company and legal entity must be explicit UUIDs")
        _required_text(self.accounting_entity_id, "accounting_entity_id")
        _required_text(self.evidence_ref, "evidence_ref")


class CompanyConfigurationEntityBridge:
    """Immutable explicit identity map that rejects aliases and unknown scopes.

    Construction requires independently validated bindings. There is no
    lookup by legal entity UUID alone, no fuzzy matching and no synthesized ID.
    This bridge DOES NOT authenticate or authorize the calling principal.
    """

    __slots__ = ("_by_scope",)

    def __init__(self, bindings: Iterable[LegacyEntityBinding]) -> None:
        by_scope: dict[tuple[str, UUID, UUID], EntityId] = {}
        by_accounting_id: dict[str, tuple[str, UUID, UUID]] = {}
        for binding in bindings:
            if not isinstance(binding, LegacyEntityBinding):
                raise TypeError("LegacyEntityBinding required")
            scope = (binding.tenant_id, binding.company_id, binding.legal_entity_id)
            accounting_id = str(binding.accounting_entity_id)
            if scope in by_scope:
                raise ValueError("Duplicate Company Configuration identity mapping")
            if accounting_id in by_accounting_id:
                raise ValueError("Accounting EntityId cannot alias another legal scope")
            by_scope[scope] = binding.accounting_entity_id
            by_accounting_id[accounting_id] = scope
        self._by_scope: Mapping[tuple[str, UUID, UUID], EntityId] = MappingProxyType(by_scope)

    def resolve(self, *, tenant_id: str, company_id: UUID, legal_entity_id: UUID) -> EntityId:
        """Resolve an existing historical ID or fail closed without a fallback."""
        _required_text(tenant_id, "tenant_id")
        if type(company_id) is not UUID or type(legal_entity_id) is not UUID:
            raise ValueError("Explicit UUID scope required")
        entity_id = self._by_scope.get((tenant_id, company_id, legal_entity_id))
        if entity_id is None:
            raise EntityScopeMismatchError("Unmapped or unauthorized accounting scope")
        return entity_id


@dataclass(frozen=True, slots=True)
class LegacyPeriodBounds:
    """Transport-only half-open dates, without opening or closing a period."""

    start: date
    end_exclusive: date

    def __post_init__(self) -> None:
        if (
            type(self.start) is not date
            or type(self.end_exclusive) is not date
            or self.end_exclusive <= self.start
        ):
            raise ValueError("Expected a valid half-open calendar date interval")

    def contains(self, business_date: date) -> bool:
        if type(business_date) is not date:
            raise ValueError("Expected an exact business date")
        return self.start <= business_date < self.end_exclusive


def legacy_period_to_half_open(period: AccountingPeriod) -> LegacyPeriodBounds:
    """Translate inclusive legacy end date to the exclusive successor date.

    No implicit timezone transformation, mutation, posting permission or
    change to the historical `AccountingPeriod.contains` contract occurs.
    An inclusive `date.max` cannot be represented with a Python exclusive end,
    so conversion fails explicitly instead of silently truncating the period.
    """
    if not isinstance(period, AccountingPeriod):
        raise TypeError("Historical AccountingPeriod required")
    try:
        end_exclusive = period.end_date + timedelta(days=1)
    except OverflowError as exc:
        raise ValueError("Legacy inclusive period end has no exclusive successor") from exc
    return LegacyPeriodBounds(period.start_date, end_exclusive)


__all__ = [
    "LegacyEntityBinding",
    "CompanyConfigurationEntityBridge",
    "LegacyPeriodBounds",
    "legacy_period_to_half_open",
]
