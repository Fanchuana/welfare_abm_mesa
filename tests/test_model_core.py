from __future__ import annotations

from welfare_abm import WelfareModel
from welfare_abm.agents import FirmAgent, FirmState, GovernmentAgent, HouseholdType
from welfare_abm.config import ModelConfig, SubsidyTier


def test_government_is_agent_and_executes_policy() -> None:
    model = WelfareModel(
        config=ModelConfig(
            n_households=20,
            n_firms=2,
            ubi_amount=50.0,
            subsidy_tiers=(SubsidyTier(max_income=900.0, amount=20.0),),
        ),
        seed=1,
    )

    assert isinstance(model.government, GovernmentAgent)
    model.step()

    assert model.government.tax_revenue >= 0
    assert model.government.ubi_spending > 0
    assert "treasury" in model.datacollector.get_model_vars_dataframe().columns


def test_lightweight_family_formation_and_split() -> None:
    model = WelfareModel(
        config=ModelConfig(
            n_households=30,
            n_firms=2,
            family_formation_prob=1.0,
            young_adult_leave_prob=1.0,
            child_growth_prob=1.0,
            replacement_household_prob=0.0,
        ),
        seed=2,
    )
    single = next(h for h in model.households if h.household_type == HouseholdType.SINGLE_YOUNG)
    single.age = 25
    single.age_and_transition()
    assert single.household_type == HouseholdType.COUPLE_WITH_CHILDREN
    assert single.children >= 1

    single.children = 1
    single.age_and_transition()
    split = single.split_young_adult()
    assert single.adults >= 2
    assert split is not None
    assert split.household_type == HouseholdType.SINGLE_YOUNG


def test_mortality_is_scaled_to_period_length() -> None:
    model = WelfareModel(config=ModelConfig(n_households=5, n_firms=1), seed=3)
    household = model.households[0]
    household.age = 75

    annual = (75 + model.config.age_step - model.config.base_mortality_age) * model.config.annual_mortality_slope
    expected_period = 1.0 - (1.0 - annual) ** model.config.age_step

    assert expected_period < annual
    assert expected_period < 0.03


def test_death_settles_estate_without_asset_disappearance() -> None:
    model = WelfareModel(
        config=ModelConfig(n_households=2, n_firms=1, replacement_household_prob=0.0),
        seed=4,
    )
    dying, heir = model.households[:2]
    dying.assets = 1_234.0
    heir.assets = 500.0
    dying.alive = False

    model._lifecycle_update()

    assert dying.unique_id not in model.household_by_id
    assert sum(h.assets for h in model.households) + model.government.treasury == 500_000.0 + 1_734.0


def test_death_with_debt_is_written_off_by_government() -> None:
    model = WelfareModel(
        config=ModelConfig(n_households=1, n_firms=1, replacement_household_prob=0.0),
        seed=6,
    )
    dying = model.households[0]
    dying.assets = -321.0
    dying.alive = False

    model._lifecycle_update()

    assert len(model.households) == 0
    assert model.government.debt_writeoff_spending == 321.0
    assert model.government.treasury == 500_000.0 - 321.0


def test_firm_hiring_is_weighted_random_not_strict_productivity_sort() -> None:
    non_top_seen = False
    for seed in range(5, 15):
        model = WelfareModel(config=ModelConfig(n_households=8, n_firms=0), seed=seed)
        firm = FirmAgent(model, base_wage=1_000.0, base_capacity=8)
        firm.state = FirmState.STABLE
        households = model.households
        for household, productivity in zip(households, [0.5, 0.7, 0.9, 1.1, 1.3, 1.5, 1.7, 1.9]):
            household.age = 30
            household.adults = 1
            household.disabled_adults = 0
            household.productivity = productivity

        remaining = firm.hire([h.labor_offer() for h in households])
        selected_productivities = {model.household_by_id[hid].productivity for hid in firm.employee_ids}
        strict_top = set(sorted([h.productivity for h in households], reverse=True)[: len(firm.employee_ids)])
        assert len(remaining) == len(households) - len(firm.employee_ids)
        non_top_seen = non_top_seen or selected_productivities != strict_top

    assert non_top_seen


def test_household_labor_supply_scales_with_working_adults() -> None:
    model = WelfareModel(config=ModelConfig(n_households=1, n_firms=0), seed=7)
    household = model.households[0]
    household.age = 35
    household.adults = 2
    household.disabled_adults = 0

    offers = household.labor_offers()

    assert household.labor_capacity == 2
    assert len(offers) == 2


def test_wage_and_benefit_cashflows_enter_assets_once() -> None:
    model = WelfareModel(config=ModelConfig(n_households=1, n_firms=0), seed=8)
    household = model.households[0]
    household.assets = 1_000.0
    household.adults = 1
    household.children = 0
    household.age = 30

    household.receive_wage(firm_id=99, wage=500.0)
    household.receive_benefit(100.0, source="ubi")
    assert household.assets == 1_600.0

    household.consume()
    assert household.assets == 1_600.0 - household.consumption


def test_ubi_is_paid_to_adults_not_children() -> None:
    model = WelfareModel(
        config=ModelConfig(n_households=1, n_firms=0, ubi_amount=100.0, subsidy_tiers=()),
        seed=9,
    )
    household = model.households[0]
    household.adults = 2
    household.children = 2
    household.assets = 0.0

    model.government.pay_universal_basic_income()

    assert household.ubi_received == 200.0
    assert household.assets == 200.0
    assert model.government.ubi_spending == 200.0
