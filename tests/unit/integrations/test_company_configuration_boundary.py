"""G0 compatibility proof; no production Company Configuration integration."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from datetime import date, datetime
from pathlib import Path
from uuid import uuid4

import pytest

import pyaccountingkit
from pyaccountingkit.core.errors import EntityScopeMismatchError
from pyaccountingkit.core.identifiers import EntityId, FiscalYearId, PeriodId
from pyaccountingkit.domain.periods.accounting_period import AccountingPeriod
from pyaccountingkit.integrations.company_configuration import (
    CompanyConfigurationEntityBridge,
    LegacyEntityBinding,
    LegacyPeriodBounds,
    legacy_period_to_half_open,
)


def _binding(
    *,
    tenant: str = "tenant-a",
    company=None,
    legal=None,
    accounting="entity_a",
    evidence="reconciliation:approved-001",
) -> LegacyEntityBinding:
    return LegacyEntityBinding(
        tenant_id=tenant,
        company_id=company or uuid4(),
        legal_entity_id=legal or uuid4(),
        accounting_entity_id=EntityId(accounting),
        evidence_ref=evidence,
    )


def test_explicit_existing_entity_id_is_returned_without_uuid_inference() -> None:
    binding = _binding(accounting="legacy_123_non_uuid")
    bridge = CompanyConfigurationEntityBridge([binding])
    actual = bridge.resolve(
        tenant_id=binding.tenant_id,
        company_id=binding.company_id,
        legal_entity_id=binding.legal_entity_id,
    )
    assert actual == EntityId("legacy_123_non_uuid")
    assert isinstance(actual, str)


@pytest.mark.parametrize("wrong", ["tenant", "company", "legal"])
def test_cross_scope_lookup_rejected_without_fallback(wrong: str) -> None:
    binding = _binding()
    bridge = CompanyConfigurationEntityBridge([binding])
    kwargs = dict(
        tenant_id=binding.tenant_id,
        company_id=binding.company_id,
        legal_entity_id=binding.legal_entity_id,
    )
    kwargs[{"tenant": "tenant_id", "company": "company_id", "legal": "legal_entity_id"}[wrong]] = (
        "tenant-other" if wrong == "tenant" else uuid4()
    )
    with pytest.raises(EntityScopeMismatchError, match="Unmapped"):
        bridge.resolve(**kwargs)


def test_unmapped_id_denied_even_when_same_tenant_and_company() -> None:
    binding = _binding()
    bridge = CompanyConfigurationEntityBridge([binding])
    with pytest.raises(EntityScopeMismatchError):
        bridge.resolve(
            tenant_id=binding.tenant_id,
            company_id=binding.company_id,
            legal_entity_id=uuid4(),
        )


@pytest.mark.parametrize(
    "bindings",
    [
        lambda b: [b, b],
        lambda b: [b, _binding(tenant="tenant-b", accounting=str(b.accounting_entity_id))],
        lambda b: [b, _binding(accounting=str(b.accounting_entity_id))],
    ],
)
def test_duplicate_or_cross_tenant_legacy_alias_rejected(bindings) -> None:
    binding = _binding()
    with pytest.raises(ValueError):
        CompanyConfigurationEntityBridge(bindings(binding))


@pytest.mark.parametrize(
    "field,value",
    [
        ("tenant_id", " "),
        ("tenant_id", "tenant-a "),
        ("accounting_entity_id", EntityId(" ")),
        ("evidence_ref", ""),
        ("company_id", "not-a-uuid"),
        ("legal_entity_id", "not-a-uuid"),
    ],
)
def test_invalid_mapping_is_rejected(field: str, value: object) -> None:
    binding = _binding()
    from dataclasses import replace

    with pytest.raises(ValueError):
        replace(binding, **{field: value})


def test_bindings_are_frozen_and_input_mutations_do_not_change_registry() -> None:
    binding = _binding()
    supplied = [binding]
    bridge = CompanyConfigurationEntityBridge(supplied)
    supplied.clear()
    assert (
        bridge.resolve(
            tenant_id=binding.tenant_id,
            company_id=binding.company_id,
            legal_entity_id=binding.legal_entity_id,
        )
        == binding.accounting_entity_id
    )
    with pytest.raises(FrozenInstanceError):
        binding.tenant_id = "tenant-other"


def _period(start: date, end: date) -> AccountingPeriod:
    return AccountingPeriod(
        id=PeriodId("period_1"),
        entity_id=EntityId("entity_a"),
        fiscal_year_id=FiscalYearId("fiscal_1"),
        start_date=start,
        end_date=end,
    )


def test_inclusive_legacy_period_maps_to_exact_half_open_successor() -> None:
    legacy = _period(date(2026, 1, 1), date(2026, 1, 31))
    mapped = legacy_period_to_half_open(legacy)
    assert mapped == LegacyPeriodBounds(date(2026, 1, 1), date(2026, 2, 1))
    assert legacy.contains(date(2026, 1, 31))
    assert mapped.contains(date(2026, 1, 31))
    assert not mapped.contains(date(2026, 2, 1))
    assert legacy.start_date == date(2026, 1, 1)
    assert legacy.end_date == date(2026, 1, 31)


def test_single_day_year_end_and_leap_day_boundaries() -> None:
    for start, end, expected in (
        (date(2026, 12, 31), date(2026, 12, 31), date(2027, 1, 1)),
        (date(2024, 2, 29), date(2024, 2, 29), date(2024, 3, 1)),
    ):
        bounds = legacy_period_to_half_open(_period(start, end))
        assert bounds.end_exclusive == expected
        assert bounds.contains(end)
        assert not bounds.contains(expected)


def test_unrepresentable_max_date_fails_closed() -> None:
    with pytest.raises(ValueError, match="no exclusive successor"):
        legacy_period_to_half_open(_period(date.max, date.max))


def test_reject_datetime_or_wrong_period_input() -> None:
    with pytest.raises(TypeError):
        legacy_period_to_half_open("period")
    with pytest.raises(ValueError):
        LegacyPeriodBounds(datetime(2026, 1, 1), date(2026, 2, 1))
    with pytest.raises(ValueError):
        LegacyPeriodBounds(date(2026, 1, 1), datetime(2026, 2, 1))
    with pytest.raises(ValueError):
        LegacyPeriodBounds(date(2026, 2, 1), date(2026, 2, 1))
    with pytest.raises(ValueError):
        LegacyPeriodBounds(date(2026, 1, 1), date(2026, 2, 1)).contains(datetime(2026, 1, 10))


def test_legacy_root_exports_still_match_previous_manifest() -> None:
    # This read-only check detects accidental changes to the historic facade.
    root = Path(__file__).resolve().parents[3]
    manifest = json.loads((root / "PUBLIC_API_MANIFEST.json").read_text(encoding="utf-8"))
    assert set(pyaccountingkit.__all__) == set(manifest["public_api"]["root_exports"])
