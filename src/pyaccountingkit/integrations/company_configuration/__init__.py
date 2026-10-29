"""Candidate Company Configuration anti-corruption boundary (G0 compatibility spike).

No Company Configuration implementation, IAM authority, publishing, or
accounting posting is provided by this package. Kept outside the public facade
until an architecture/compatibility decision is independently approved.
"""

from .boundary import (
    CompanyConfigurationEntityBridge,
    LegacyEntityBinding,
    LegacyPeriodBounds,
    legacy_period_to_half_open,
)

__all__ = [
    "CompanyConfigurationEntityBridge",
    "LegacyEntityBinding",
    "LegacyPeriodBounds",
    "legacy_period_to_half_open",
]
