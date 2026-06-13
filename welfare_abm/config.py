from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SubsidyTier:
    """A targeted-transfer tier based on household per-capita income."""

    max_income: float
    amount: float


@dataclass(frozen=True)
class ModelConfig:
    """Central knobs for a small welfare-society simulation."""

    n_households: int = 220
    n_firms: int = 4
    initial_treasury: float = 500_000.0
    income_tax_rate: float = 0.20
    corporate_tax_rate: float = 0.28
    ubi_amount: float = 100.0
    targeted_error_rate: float = 0.05
    false_positive_rate: float | None = None
    false_negative_rate: float | None = None
    poverty_line: float = 300.0
    asset_means_test_divisor: float = 18.0
    asset_exemption: float = 3_000.0
    age_step: float = 0.25
    retirement_age: int = 62
    adult_age: int = 18
    max_age: int = 88
    base_mortality_age: int = 70
    annual_mortality_slope: float = 0.015
    inheritance_search_pool: int = 8
    disability_shock_prob: float = 0.003
    child_growth_prob: float = 0.015
    family_formation_prob: float = 0.035
    young_adult_leave_prob: float = 0.025
    max_households_multiplier: float = 1.10
    replacement_household_prob: float = 0.25
    baseline_consumption: float = 320.0
    child_consumption: float = 120.0
    elder_consumption: float = 200.0
    asset_floor: float = -10_000.0
    subsidy_tiers: tuple[SubsidyTier, ...] = field(
        default_factory=lambda: (
            SubsidyTier(max_income=450.0, amount=90.0),
            SubsidyTier(max_income=700.0, amount=60.0),
            SubsidyTier(max_income=950.0, amount=30.0),
        )
    )

    @property
    def effective_false_positive_rate(self) -> float:
        return self.targeted_error_rate if self.false_positive_rate is None else self.false_positive_rate

    @property
    def effective_false_negative_rate(self) -> float:
        return self.targeted_error_rate if self.false_negative_rate is None else self.false_negative_rate
