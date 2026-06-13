from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np
from mesa import Agent


class HouseholdType(str, Enum):
    SINGLE_YOUNG = "single_young"
    COUPLE_WITH_CHILDREN = "couple_with_children"
    ELDERLY = "elderly"
    DISABLED = "disabled"


class FirmState(str, Enum):
    BOOM = "boom"
    STABLE = "stable"
    RECESSION = "recession"
    DEPRESSION = "depression"
    RECOVERY = "recovery"


@dataclass
class LaborOffer:
    household_id: int
    productivity: float
    worker_index: int


class HouseholdAgent(Agent):
    """A household with simple lifecycle, labor, consumption, and assets."""

    def __init__(
        self,
        model,
        household_type: HouseholdType,
        age: int,
        adults: int,
        children: int,
        assets: float,
        productivity: float,
        disabled_adults: int = 0,
    ) -> None:
        super().__init__(model)
        self.household_type = household_type
        self.age = age
        self.adults = adults
        self.children = children
        self.disabled_adults = disabled_adults
        self.assets = assets
        self.productivity = productivity
        self.employed_workers = 0
        self.employer_id: int | None = None
        self.wage_income = 0.0
        self.benefits = 0.0
        self.ubi_received = 0.0
        self.targeted_received = 0.0
        self.taxes_paid = 0.0
        self.consumption = 0.0
        self.alive = True

    @property
    def employed(self) -> bool:
        return self.employed_workers > 0

    @property
    def household_size(self) -> int:
        return max(1, self.adults + self.children)

    @property
    def labor_capacity(self) -> int:
        if self.age < self.model.config.adult_age or self.age >= self.model.config.retirement_age:
            return 0
        return max(0, self.adults - self.disabled_adults)

    @property
    def per_capita_income(self) -> float:
        return (self.wage_income + self.benefits) / self.household_size

    @property
    def total_income(self) -> float:
        return self.wage_income + self.benefits

    def reset_period(self) -> None:
        self.employed_workers = 0
        self.employer_id = None
        self.wage_income = 0.0
        self.benefits = 0.0
        self.ubi_received = 0.0
        self.targeted_received = 0.0
        self.taxes_paid = 0.0
        self.consumption = 0.0

    def labor_offers(self) -> list[LaborOffer]:
        if self.labor_capacity <= 0:
            return []
        return [
            LaborOffer(
                household_id=self.unique_id,
                productivity=float(np.clip(self.productivity * self.model.rng.normal(1.0, 0.05), 0.35, 2.3)),
                worker_index=i,
            )
            for i in range(self.labor_capacity)
        ]

    def labor_offer(self) -> LaborOffer | None:
        offers = self.labor_offers()
        return offers[0] if offers else None

    def receive_wage(self, firm_id: int, wage: float) -> None:
        self.employed_workers += 1
        self.employer_id = firm_id
        self.wage_income += wage
        self.assets += wage

    def pay_income_tax(self) -> float:
        tax = max(0.0, self.wage_income * self.model.config.income_tax_rate)
        self.taxes_paid += tax
        self.assets -= tax
        return tax

    def receive_benefit(self, amount: float, source: str = "targeted") -> None:
        self.benefits += amount
        if source == "ubi":
            self.ubi_received += amount
        else:
            self.targeted_received += amount
        self.assets += amount

    def consume(self) -> None:
        cfg = self.model.config
        need = cfg.baseline_consumption * self.adults
        need += cfg.child_consumption * self.children
        if self.age >= cfg.retirement_age:
            need += cfg.elder_consumption
        income_sensitive = 0.35 * max(0.0, self.wage_income + self.benefits)
        self.consumption = max(120.0, need + income_sensitive)
        self.assets = max(cfg.asset_floor, self.assets - self.consumption)

    def age_and_transition(self) -> None:
        cfg = self.model.config
        rng = self.model.rng
        self.age += cfg.age_step

        age_risk = 1.0 + max(0, self.age - 35) / 60.0
        low_asset_risk = 1.25 if self.assets < 0 else 1.0
        if self.labor_capacity > 0 and rng.random() < cfg.disability_shock_prob * age_risk * low_asset_risk:
            self.disabled_adults = min(self.adults, self.disabled_adults + 1)
            if self.disabled_adults >= self.adults:
                self.household_type = HouseholdType.DISABLED

        if self.children > 0 and rng.random() < cfg.child_growth_prob:
            self.children -= 1
            self.adults += 1

        if (
            self.household_type == HouseholdType.SINGLE_YOUNG
            and 22 <= self.age <= 38
            and rng.random() < cfg.family_formation_prob
        ):
            self.household_type = HouseholdType.COUPLE_WITH_CHILDREN
            self.adults = 2
            self.children = int(rng.integers(1, 3))

        if self.age >= cfg.retirement_age and self.household_type != HouseholdType.DISABLED:
            self.household_type = HouseholdType.ELDERLY

        annual_death_prob = max(
            0.0,
            (self.age - cfg.base_mortality_age) * cfg.annual_mortality_slope,
        )
        period_death_prob = 1.0 - (1.0 - min(annual_death_prob, 0.95)) ** cfg.age_step
        if self.age >= cfg.max_age or rng.random() < period_death_prob:
            self.alive = False

    def split_young_adult(self) -> HouseholdAgent | None:
        cfg = self.model.config
        if self.household_type != HouseholdType.COUPLE_WITH_CHILDREN:
            return None
        if len(self.model.households) >= int(cfg.n_households * cfg.max_households_multiplier):
            return None
        if self.adults <= 2 or self.model.rng.random() >= cfg.young_adult_leave_prob:
            return None
        self.adults -= 1
        transferred_assets = max(0.0, min(self.assets * 0.12, 4_000.0))
        self.assets -= transferred_assets
        return HouseholdAgent(
            self.model,
            household_type=HouseholdType.SINGLE_YOUNG,
            age=int(self.model.rng.integers(18, 25)),
            adults=1,
            children=0,
            assets=transferred_assets,
            productivity=float(np.clip(self.productivity * self.model.rng.normal(1.0, 0.12), 0.45, 2.0)),
        )


class GovernmentAgent(Agent):
    """Policy executor: tax collection, UBI, targeted transfers, and treasury."""

    def __init__(self, model) -> None:
        super().__init__(model)
        self.treasury = model.config.initial_treasury
        self.ubi_spending = 0.0
        self.targeted_spending = 0.0
        self.false_positive_spending = 0.0
        self.false_negative_amount = 0.0
        self.false_negative_count = 0
        self.tax_revenue = 0.0
        self.inherited_assets_received = 0.0
        self.debt_writeoff_spending = 0.0

    def reset_period(self) -> None:
        self.ubi_spending = 0.0
        self.targeted_spending = 0.0
        self.false_positive_spending = 0.0
        self.false_negative_amount = 0.0
        self.false_negative_count = 0
        self.tax_revenue = 0.0
        self.inherited_assets_received = 0.0
        self.debt_writeoff_spending = 0.0

    def collect_taxes(self) -> None:
        for household in self.model.households:
            tax = household.pay_income_tax()
            self.treasury += tax
            self.tax_revenue += tax

        for firm in self.model.firms:
            tax = firm.settle_accounts()
            self.treasury += tax
            self.tax_revenue += tax

    def pay_universal_basic_income(self) -> None:
        amount = self.model.config.ubi_amount
        if amount <= 0:
            return
        for household in self.model.households:
            transfer = amount * household.adults
            household.receive_benefit(transfer, source="ubi")
            self.treasury -= transfer
            self.ubi_spending += transfer

    def pay_targeted_subsidies(self) -> None:
        if not self.model.config.subsidy_tiers:
            return
        cfg = self.model.config
        for household in self.model.households:
            true_amount = self.targeted_amount(household)
            judged_amount = true_amount
            if true_amount > 0:
                if self.model.rng.random() < cfg.effective_false_negative_rate:
                    self.false_negative_amount += true_amount
                    self.false_negative_count += 1
                    judged_amount = 0.0
            elif self.model.rng.random() < cfg.effective_false_positive_rate:
                judged_amount = self.false_positive_amount(household.household_size)
                self.false_positive_spending += judged_amount
            if judged_amount > 0:
                household.receive_benefit(judged_amount, source="targeted")
                self.treasury -= judged_amount
                self.targeted_spending += judged_amount

    def deprivation_score(self, household: HouseholdAgent) -> float:
        cfg = self.model.config
        income_pc = household.wage_income / household.household_size
        assessable_assets = max(0.0, household.assets - cfg.asset_exemption)
        asset_income_pc = assessable_assets / cfg.asset_means_test_divisor / household.household_size
        return income_pc + asset_income_pc

    def targeted_amount(self, household: HouseholdAgent) -> float:
        score = self.deprivation_score(household)
        for tier in self.model.config.subsidy_tiers:
            if score <= tier.max_income:
                return tier.amount * household.household_size
        return 0.0

    def false_positive_amount(self, household_size: int) -> float:
        tier = self.model._choice(list(self.model.config.subsidy_tiers))
        return tier.amount * household_size


class FirmAgent(Agent):
    """A small firm whose business climate drives wages and hiring."""

    STATE_PARAMS = {
        FirmState.BOOM: (1.12, 1.18, 1.25),
        FirmState.STABLE: (1.0, 1.0, 1.0),
        FirmState.RECESSION: (0.9, 0.9, 0.8),
        FirmState.DEPRESSION: (0.76, 0.78, 0.55),
        FirmState.RECOVERY: (1.02, 0.96, 0.9),
    }

    TRANSITION = {
        FirmState.BOOM: [FirmState.BOOM, FirmState.STABLE, FirmState.RECESSION],
        FirmState.STABLE: [FirmState.BOOM, FirmState.STABLE, FirmState.RECESSION, FirmState.RECOVERY],
        FirmState.RECESSION: [FirmState.STABLE, FirmState.RECESSION, FirmState.DEPRESSION, FirmState.RECOVERY],
        FirmState.DEPRESSION: [FirmState.DEPRESSION, FirmState.RECESSION, FirmState.RECOVERY],
        FirmState.RECOVERY: [FirmState.RECOVERY, FirmState.STABLE, FirmState.BOOM, FirmState.RECESSION],
    }

    def __init__(self, model, base_wage: float, base_capacity: int) -> None:
        super().__init__(model)
        self.base_wage = base_wage
        self.base_capacity = base_capacity
        states = list(FirmState)
        self.state = states[int(self.model.rng.integers(0, len(states)))]
        self.revenue = 0.0
        self.payroll = 0.0
        self.profit = 0.0
        self.taxes_paid = 0.0
        self.employee_ids: list[int] = []

    def update_business_climate(self) -> None:
        choices = self.TRANSITION[self.state]
        self.state = choices[int(self.model.rng.integers(0, len(choices)))]

    def hire(self, offers: list[LaborOffer]) -> list[LaborOffer]:
        wage_mult, revenue_mult, capacity_mult = self.STATE_PARAMS[self.state]
        capacity_noise = self.model.rng.normal(1.0, 0.08)
        expected_labor_force = self.model.config.n_households * 1.02
        current_labor_force = sum(h.labor_capacity for h in self.model.households)
        labor_pressure = current_labor_force / max(1.0, expected_labor_force)
        capacity = max(0, int(self.base_capacity * labor_pressure * capacity_mult * capacity_noise))
        if capacity <= 0 or not offers:
            self.employee_ids = []
            self.payroll = 0.0
            return offers
        n_selected = min(capacity, len(offers))
        weights = np.array([max(0.05, offer.productivity) for offer in offers], dtype=float)
        weights = weights / weights.sum()
        selected_idx = self.model.rng.choice(len(offers), size=n_selected, replace=False, p=weights)
        selected_set = set(int(idx) for idx in selected_idx)
        selected = [offer for idx, offer in enumerate(offers) if idx in selected_set]
        remaining = [offer for idx, offer in enumerate(offers) if idx not in selected_set]
        self.employee_ids = [offer.household_id for offer in selected]
        self.payroll = 0.0

        for offer in selected:
            household = self.model.household_by_id[offer.household_id]
            wage = self.base_wage * wage_mult * offer.productivity
            wage *= float(np.clip(self.model.rng.normal(1.0, 0.06), 0.75, 1.3))
            household.receive_wage(self.unique_id, wage)
            self.payroll += wage
        return remaining

    def settle_accounts(self) -> float:
        _, revenue_mult, _ = self.STATE_PARAMS[self.state]
        productivity_sum = sum(
            self.model.household_by_id[hid].productivity for hid in self.employee_ids
        )
        per_firm_consumption = self.model.total_household_consumption / max(1, len(self.model.firms))
        demand_factor = float(np.clip(per_firm_consumption / 35_000.0, 0.75, 1.35))
        self.revenue = self.base_wage * 1.6 * productivity_sum * revenue_mult * demand_factor
        self.profit = self.revenue - self.payroll
        tax = max(0.0, self.profit * self.model.config.corporate_tax_rate)
        self.taxes_paid = tax
        self.profit -= tax
        return tax
