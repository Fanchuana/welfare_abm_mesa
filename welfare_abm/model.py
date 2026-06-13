from __future__ import annotations

from collections import Counter

import numpy as np
from mesa import Model
from mesa.datacollection import DataCollector

from .agents import FirmAgent, GovernmentAgent, HouseholdAgent, HouseholdType
from .config import ModelConfig
from .metrics import gini, safe_mean


class WelfareModel(Model):
    """A compact welfare-society ABM inspired by PolicySpace2-style actors."""

    def __init__(self, config: ModelConfig | None = None, seed: int | None = None) -> None:
        super().__init__(seed=seed)
        self.config = config or ModelConfig()
        self.rng = np.random.default_rng(seed)
        self.total_household_consumption = 0.0
        self.household_by_id: dict[int, HouseholdAgent] = {}
        self.government: GovernmentAgent | None = None
        self._create_agents()
        self.datacollector = DataCollector(
            model_reporters={
                "households": lambda m: len(m.households),
                "treasury": lambda m: m.government.treasury,
                "gini_assets": lambda m: gini([h.assets for h in m.households]),
                "gini_income": lambda m: gini([h.total_income for h in m.households]),
                "poverty_rate": lambda m: m.poverty_rate(),
                "means_tested_poverty_rate": lambda m: m.means_tested_poverty_rate(),
                "unemployment_rate": lambda m: m.unemployment_rate(),
                "labor_participation": lambda m: m.labor_participation(),
                "avg_wage": lambda m: safe_mean([h.wage_income for h in m.households if h.employed]),
                "avg_assets": lambda m: safe_mean([h.assets for h in m.households]),
                "ubi_spending": lambda m: m.government.ubi_spending,
                "targeted_spending": lambda m: m.government.targeted_spending,
                "false_positive_spending": lambda m: m.government.false_positive_spending,
                "false_negative_amount": lambda m: m.government.false_negative_amount,
                "false_negative_count": lambda m: m.government.false_negative_count,
                "inherited_assets_received": lambda m: m.government.inherited_assets_received,
                "debt_writeoff_spending": lambda m: m.government.debt_writeoff_spending,
                "tax_revenue": lambda m: m.government.tax_revenue,
                "deficit": lambda m: (
                    m.government.ubi_spending
                    + m.government.targeted_spending
                    + m.government.debt_writeoff_spending
                    - m.government.tax_revenue
                    - m.government.inherited_assets_received
                ),
                "single_young": lambda m: m.type_count(HouseholdType.SINGLE_YOUNG),
                "couple_with_children": lambda m: m.type_count(HouseholdType.COUPLE_WITH_CHILDREN),
                "elderly": lambda m: m.type_count(HouseholdType.ELDERLY),
                "disabled": lambda m: m.type_count(HouseholdType.DISABLED),
            }
        )
        self.datacollector.collect(self)

    @property
    def households(self) -> list[HouseholdAgent]:
        return [a for a in self.agents if isinstance(a, HouseholdAgent)]

    @property
    def firms(self) -> list[FirmAgent]:
        return [a for a in self.agents if isinstance(a, FirmAgent)]

    def _create_agents(self) -> None:
        cfg = self.config
        self.government = GovernmentAgent(self)
        expected_labor_force = cfg.n_households * 1.02
        for _ in range(cfg.n_firms):
            FirmAgent(
                self,
                base_wage=float(self.rng.uniform(850, 1_250)),
                base_capacity=max(10, int(expected_labor_force / cfg.n_firms * self.rng.uniform(0.78, 0.92))),
            )

        for _ in range(cfg.n_households):
            household = self._make_household()
            self.household_by_id[household.unique_id] = household

    def _choice(self, values, probabilities=None):
        idx = int(self.rng.choice(len(values), p=probabilities))
        return values[idx]

    def _make_household(self) -> HouseholdAgent:
        household_type = self._choice(
            values=[
                HouseholdType.SINGLE_YOUNG,
                HouseholdType.COUPLE_WITH_CHILDREN,
                HouseholdType.ELDERLY,
                HouseholdType.DISABLED,
            ],
            probabilities=[0.34, 0.34, 0.20, 0.12],
        )
        if household_type == HouseholdType.SINGLE_YOUNG:
            age, adults, children, disabled = int(self.rng.integers(20, 36)), 1, 0, 0
            assets = float(self.rng.normal(4_000, 1_800))
        elif household_type == HouseholdType.COUPLE_WITH_CHILDREN:
            age, adults, children, disabled = int(self.rng.integers(26, 46)), 2, int(self.rng.integers(1, 3)), 0
            assets = float(self.rng.normal(8_000, 3_000))
        elif household_type == HouseholdType.ELDERLY:
            age, adults, children, disabled = int(self.rng.integers(62, 80)), 1, 0, 0
            assets = float(self.rng.normal(12_000, 5_000))
        else:
            age, adults, children, disabled = int(self.rng.integers(24, 64)), 1, 0, 1
            assets = float(self.rng.normal(2_000, 1_500))

        productivity = float(np.clip(self.rng.lognormal(mean=0.0, sigma=0.28), 0.45, 2.0))
        return HouseholdAgent(
            self,
            household_type=household_type,
            age=age,
            adults=adults,
            children=children,
            assets=max(self.config.asset_floor, assets),
            productivity=productivity,
            disabled_adults=disabled,
        )

    def step(self) -> None:
        self.government.reset_period()

        for household in self.households:
            household.reset_period()
        for firm in self.firms:
            firm.update_business_climate()

        offers = [
            offer
            for household in self.households
            for offer in household.labor_offers()
        ]
        self.rng.shuffle(offers)
        firms = self.firms
        self.rng.shuffle(firms)
        for firm in firms:
            offers = firm.hire(offers)

        self.government.collect_taxes()
        self.government.pay_universal_basic_income()
        self.government.pay_targeted_subsidies()

        for household in self.households:
            household.consume()
        self.total_household_consumption = sum(h.consumption for h in self.households)

        self._lifecycle_update()
        self.datacollector.collect(self)

    def _lifecycle_update(self) -> None:
        new_households: list[HouseholdAgent] = []
        for household in list(self.households):
            household.age_and_transition()
            split_household = household.split_young_adult()
            if split_household is not None:
                new_households.append(split_household)
            if not household.alive:
                self._settle_estate(household)
                self.household_by_id.pop(household.unique_id, None)
                household.remove()
        for household in new_households:
            self.household_by_id[household.unique_id] = household
        while len(self.households) < self.config.n_households:
            if self.rng.random() > self.config.replacement_household_prob:
                break
            household = self._make_household()
            self.household_by_id[household.unique_id] = household

    def _settle_estate(self, household: HouseholdAgent) -> None:
        estate = household.assets
        household.assets = 0.0
        if estate > 0:
            heirs = [
                h for h in self.households
                if h.alive and h.unique_id != household.unique_id
            ]
            if heirs:
                scored_heirs = sorted(
                    heirs,
                    key=lambda h: (
                        h.household_type != HouseholdType.SINGLE_YOUNG,
                        abs(h.productivity - household.productivity),
                        h.assets,
                    ),
                )
                pool_size = max(1, min(self.config.inheritance_search_pool, len(scored_heirs)))
                heir = self._choice(scored_heirs[:pool_size])
                heir.assets += estate
            else:
                self.government.treasury += estate
                self.government.inherited_assets_received += estate
        elif estate < 0:
            writeoff = -estate
            self.government.treasury -= writeoff
            self.government.debt_writeoff_spending += writeoff

    def poverty_rate(self) -> float:
        poor = [h for h in self.households if h.per_capita_income < self.config.poverty_line]
        return len(poor) / max(1, len(self.households))

    def means_tested_poverty_rate(self) -> float:
        poor = [
            h
            for h in self.households
            if self.government.deprivation_score(h) < self.config.poverty_line
        ]
        return len(poor) / max(1, len(self.households))

    def unemployment_rate(self) -> float:
        labor_force = sum(h.labor_capacity for h in self.households)
        employed = sum(min(h.employed_workers, h.labor_capacity) for h in self.households)
        return (labor_force - employed) / max(1, labor_force)

    def labor_participation(self) -> float:
        working_age_adults = sum(
            h.adults
            for h in self.households
            if self.config.adult_age <= h.age < self.config.retirement_age
        )
        labor_force = sum(h.labor_capacity for h in self.households)
        return labor_force / max(1, working_age_adults)

    def type_count(self, household_type: HouseholdType) -> int:
        return Counter(h.household_type for h in self.households)[household_type]
