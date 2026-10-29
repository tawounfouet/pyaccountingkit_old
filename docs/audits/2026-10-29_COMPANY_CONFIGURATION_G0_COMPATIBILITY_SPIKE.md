# G0 compatibility spike — Company Configuration against 0.7.0rc2 historical core

**Status:** experimental / review required / NOT MERGED.  
**Historical baseline:** `tawounfouet/pyaccountingkit_old` main `10b0a87076e66824d69cd24eafdbcb272cf1cd1d` (`pyaccountingkit==0.7.0rc2` according to project metadata).  
**New separate development:** `tawounfouet/pyaccountingkit` PRs #3–#25 (`pyaccountingkit==0.0.0` on PR #3).  
**Intended outcome:** test feasibility of adding a bounded integration layer without rewriting existing public accounting contracts.

## Verified source conflicts
- Historical `EntityId = NewType('EntityId', str)`; proposed Company Configuration `LegalEntityId` wraps UUID. They are **not** interchangeable.
- Historical accounting entity and proposed legal entity may overlap but should not silently become one aggregate.
- Historical `AccountingPeriod.contains` accepts inclusive `end_date`; Company Configuration proposes half-open effective intervals. There is no automatic safe equivalence.
- Historical public root exports are governed by `PUBLIC_API_MANIFEST.json`. Do not publish a second `pyaccountingkit` distribution or silently change public errors.

## Narrow implementation proposed here
- New private `integrations/company_configuration` module (anti-corruption layer): `LegacyEntityBinding` and fail-closed `CompanyConfigurationEntityBridge` register only **explicit** tenant/company/legal-entity UUID to legacy Accounting EntityId bindings. Reject duplicate or cross-tenant alias maps.
- `legacy_period_to_half_open` explicitly advances inclusive final date by one day for a **transport-only** half-open interval. Inclusive `date.max` must fail closed.
- Unit tests cover mapping, unauthorized/unmapped scope, alias collisions, immutability, leap/year boundaries and existing root export manifest.
- Does **not** change `pyproject.toml`, public `__init__`, old `core`, `ports`, `domain`, existing period semantics or migrations.

## Limitations and required decisions
- Registry input `evidence_ref` is a claimed reconciliation reference, **not validated authorization**; production must load approved records from an independently secured source and enforce actor/tenant policy.
- No bidirectional automatic migration, no Company Configuration snapshot/C10, no IAM integration, no schema change and no Ledger mutation.
- Compatibility to historical 0.7.0rc2 is an **implementation candidate**; CI for the exact branch SHA, security review, independent ADR decision and integration topology remain mandatory.
- The historical package tree is the **recommended candidate** for the integration baseline. Repository ownership/name and package migration require explicit user/maintainer decision before any main-branch merge or release.
- G0/G1/G2 are **NOT APPROVED**; no stable release is inferred.
