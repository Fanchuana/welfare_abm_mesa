from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from welfare_abm import WelfareModel
from welfare_abm.config import ModelConfig, SubsidyTier


BASE_TIERS = (
    SubsidyTier(max_income=450.0, amount=90.0),
    SubsidyTier(max_income=700.0, amount=60.0),
    SubsidyTier(max_income=950.0, amount=30.0),
)


def run_case(policy: str, config: ModelConfig, seed: int, steps: int) -> dict[str, float | int | str]:
    model = WelfareModel(config=config, seed=seed)
    for _ in range(steps):
        model.step()
    df = model.datacollector.get_model_vars_dataframe()
    final = df.iloc[-1]
    tail = df.tail(20)
    return {
        "policy": policy,
        "seed": seed,
        "steps": steps,
        "households": final["households"],
        "gini_assets": final["gini_assets"],
        "gini_income": final["gini_income"],
        "poverty_rate": final["poverty_rate"],
        "means_tested_poverty_rate": final["means_tested_poverty_rate"],
        "unemployment_rate": final["unemployment_rate"],
        "labor_participation": final["labor_participation"],
        "avg_wage": final["avg_wage"],
        "treasury": final["treasury"],
        "avg_deficit_last20": tail["deficit"].mean(),
        "tax_revenue": tail["tax_revenue"].mean(),
        "ubi_spending": tail["ubi_spending"].mean(),
        "targeted_spending": tail["targeted_spending"].mean(),
        "false_positive_spending": tail["false_positive_spending"].mean(),
        "false_negative_amount": tail["false_negative_amount"].mean(),
    }


def main() -> None:
    outdir = Path("report/data")
    outdir.mkdir(parents=True, exist_ok=True)
    steps = 80
    seeds = list(range(21, 41))
    no_tiers: tuple[SubsidyTier, ...] = ()
    cases = {
        "No welfare": ModelConfig(ubi_amount=0.0, subsidy_tiers=no_tiers),
        "UBI only": ModelConfig(ubi_amount=100.0, subsidy_tiers=no_tiers),
        "Targeted only": ModelConfig(ubi_amount=0.0, subsidy_tiers=BASE_TIERS, false_positive_rate=0.05, false_negative_rate=0.05),
        "Mixed, 5% error": ModelConfig(ubi_amount=100.0, subsidy_tiers=BASE_TIERS, false_positive_rate=0.05, false_negative_rate=0.05),
        "Mixed, 15% error": ModelConfig(ubi_amount=100.0, subsidy_tiers=BASE_TIERS, false_positive_rate=0.15, false_negative_rate=0.15),
    }
    rows = [
        run_case(policy, config, seed, steps)
        for policy, config in cases.items()
        for seed in seeds
    ]
    raw = pd.DataFrame(rows)
    raw_path = outdir / "multi_seed_raw.csv"
    summary_path = outdir / "multi_seed_summary.csv"
    raw.to_csv(raw_path, index=False)
    summary = raw.groupby("policy").agg(["mean", "std"])
    summary.columns = ["_".join(col).strip() for col in summary.columns.values]
    summary = summary.reset_index()
    summary.to_csv(summary_path, index=False)
    print(f"raw={raw_path}")
    print(f"summary={summary_path}")
    print(
        summary[
            [
                "policy",
                "gini_assets_mean",
                "gini_assets_std",
                "means_tested_poverty_rate_mean",
                "unemployment_rate_mean",
                "treasury_mean",
                "avg_deficit_last20_mean",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()

