from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from welfare_abm import WelfareModel
from welfare_abm.config import ModelConfig, SubsidyTier


BASE_TIERS = (
    SubsidyTier(max_income=450.0, amount=90.0),
    SubsidyTier(max_income=700.0, amount=60.0),
    SubsidyTier(max_income=950.0, amount=30.0),
)


def scaled_tiers(scale: float) -> tuple[SubsidyTier, ...]:
    return tuple(SubsidyTier(t.max_income, round(t.amount * scale, 2)) for t in BASE_TIERS)


@st.cache_data(show_spinner=False)
def run_simulation(
    steps: int,
    seed: int,
    households: int,
    firms: int,
    income_tax: float,
    corp_tax: float,
    ubi: float,
    false_positive_rate: float,
    false_negative_rate: float,
    tier_scale: float,
) -> pd.DataFrame:
    config = ModelConfig(
        n_households=households,
        n_firms=firms,
        income_tax_rate=income_tax,
        corporate_tax_rate=corp_tax,
        ubi_amount=ubi,
        false_positive_rate=false_positive_rate,
        false_negative_rate=false_negative_rate,
        subsidy_tiers=scaled_tiers(tier_scale),
    )
    model = WelfareModel(config=config, seed=seed)
    for _ in range(steps):
        model.step()
    df = model.datacollector.get_model_vars_dataframe()
    df.index.name = "step"
    return df.reset_index()


def run_policy_case(name: str, config: ModelConfig, seed: int, steps: int) -> pd.DataFrame:
    model = WelfareModel(config=config, seed=seed)
    for _ in range(steps):
        model.step()
    df = model.datacollector.get_model_vars_dataframe()
    df.index.name = "step"
    df = df.reset_index()
    df["policy"] = name
    return df


@st.cache_data(show_spinner=False)
def run_policy_comparison(steps: int, seed: int) -> pd.DataFrame:
    no_tiers: tuple[SubsidyTier, ...] = ()
    cases = {
        "No welfare": ModelConfig(ubi_amount=0.0, subsidy_tiers=no_tiers),
        "UBI only": ModelConfig(ubi_amount=100.0, subsidy_tiers=no_tiers),
        "Targeted only": ModelConfig(ubi_amount=0.0, subsidy_tiers=BASE_TIERS, targeted_error_rate=0.05),
        "Mixed, 5% error": ModelConfig(ubi_amount=100.0, subsidy_tiers=BASE_TIERS, targeted_error_rate=0.05),
        "Mixed, 15% error": ModelConfig(ubi_amount=100.0, subsidy_tiers=BASE_TIERS, targeted_error_rate=0.15),
    }
    return pd.concat(
        [run_policy_case(name, config, seed, steps) for name, config in cases.items()],
        ignore_index=True,
    )


def sidebar_controls() -> dict[str, int | float]:
    st.sidebar.header("Simulation Controls")
    return {
        "steps": st.sidebar.slider("Steps", 20, 160, 80, 10),
        "seed": st.sidebar.number_input("Seed", min_value=1, max_value=9999, value=42, step=1),
        "households": st.sidebar.slider("Households", 60, 600, 220, 20),
        "firms": st.sidebar.slider("Firms", 3, 8, 4, 1),
        "income_tax": st.sidebar.slider("Income tax", 0.0, 0.5, 0.20, 0.01),
        "corp_tax": st.sidebar.slider("Corporate tax", 0.0, 0.5, 0.28, 0.01),
        "ubi": st.sidebar.slider("UBI", 0.0, 250.0, 100.0, 10.0),
        "false_positive_rate": st.sidebar.slider("False positive rate", 0.0, 0.50, 0.05, 0.01),
        "false_negative_rate": st.sidebar.slider("False negative rate", 0.0, 0.50, 0.05, 0.01),
        "tier_scale": st.sidebar.slider("Targeted subsidy scale", 0.0, 3.0, 1.0, 0.05),
    }


def final_metrics(df: pd.DataFrame) -> None:
    final = df.iloc[-1]
    cols = st.columns(4)
    cols[0].metric("Asset Gini", f"{final['gini_assets']:.3f}")
    cols[1].metric("Means-tested poverty", f"{final['means_tested_poverty_rate']:.1%}")
    cols[2].metric("Unemployment rate", f"{final['unemployment_rate']:.1%}")
    cols[3].metric("Treasury", f"{final['treasury']:,.0f}")
    cols2 = st.columns(3)
    cols2[0].metric("Targeted spending", f"{final['targeted_spending']:,.0f}")
    cols2[1].metric("False-positive spending", f"{final['false_positive_spending']:,.0f}")
    cols2[2].metric("False-negative missed aid", f"{final['false_negative_amount']:,.0f}")


def single_scenario_tab(params: dict[str, int | float]) -> None:
    with st.spinner("Running simulation..."):
        df = run_simulation(**params)

    final_metrics(df)
    st.subheader("Core Dynamics")
    st.line_chart(
        df.set_index("step")[
            ["gini_assets", "means_tested_poverty_rate"]
        ],
        height=320,
    )
    st.subheader("Labor Market")
    st.line_chart(
        df.set_index("step")[["unemployment_rate", "labor_participation", "avg_wage"]],
        height=300,
    )
    st.subheader("Government Finance")
    st.line_chart(
        df.set_index("step")[
            [
                "treasury",
                "tax_revenue",
                "ubi_spending",
                "targeted_spending",
                "false_positive_spending",
                "false_negative_amount",
            ]
        ],
        height=320,
    )
    with st.expander("Show raw metrics"):
        st.dataframe(df, use_container_width=True)


def policy_comparison_tab(steps: int, seed: int) -> None:
    with st.spinner("Running policy comparison..."):
        df = run_policy_comparison(steps=steps, seed=seed)
    final = df.sort_values("step").groupby("policy").tail(1)
    table = final[
        [
            "policy",
            "gini_assets",
            "poverty_rate",
            "means_tested_poverty_rate",
            "unemployment_rate",
            "treasury",
            "false_positive_spending",
            "false_negative_amount",
        ]
    ].sort_values("gini_assets")
    table = table.rename(
        columns={
            "policy": "Policy",
            "gini_assets": "Asset Gini",
            "poverty_rate": "Income poverty",
            "means_tested_poverty_rate": "Means-tested poverty",
            "unemployment_rate": "Unemployment rate",
            "treasury": "Treasury",
            "false_positive_spending": "False-positive spending",
            "false_negative_amount": "False-negative missed aid",
        }
    )
    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True,
    )
    pivot_metric = st.selectbox(
        "Metric",
        [
            "gini_assets",
            "means_tested_poverty_rate",
            "unemployment_rate",
            "treasury",
            "false_positive_spending",
            "false_negative_amount",
        ],
        index=0,
    )
    chart_df = df.pivot(index="step", columns="policy", values=pivot_metric)
    st.line_chart(chart_df, height=380)


def main() -> None:
    st.set_page_config(page_title="WelfareABM Dashboard", layout="wide")
    st.title("WelfareABM Dashboard")
    st.caption("Interactive Mesa simulation for UBI, targeted welfare, fiscal sustainability, and asset inequality.")

    params = sidebar_controls()
    tab_single, tab_compare = st.tabs(["Single Scenario", "Policy Comparison"])
    with tab_single:
        single_scenario_tab(params)
    with tab_compare:
        policy_comparison_tab(steps=int(params["steps"]), seed=int(params["seed"]))


if __name__ == "__main__":
    main()
