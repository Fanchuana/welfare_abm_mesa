from __future__ import annotations

import itertools
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from welfare_abm import WelfareModel
from welfare_abm.config import ModelConfig, SubsidyTier


BASE_TIERS = (
    SubsidyTier(max_income=450.0, amount=360.0),
    SubsidyTier(max_income=700.0, amount=240.0),
    SubsidyTier(max_income=950.0, amount=120.0),
)


def scale_tiers(scale: float) -> tuple[SubsidyTier, ...]:
    return tuple(SubsidyTier(t.max_income, round(t.amount * scale, 2)) for t in BASE_TIERS)


def run_config(config: ModelConfig, seed: int, steps: int) -> dict[str, float]:
    model = WelfareModel(config=config, seed=seed)
    for _ in range(steps):
        model.step()
    df = model.datacollector.get_model_vars_dataframe()
    tail = df.tail(20)
    final = df.iloc[-1]
    return {
        "final_treasury": float(final["treasury"]),
        "avg_deficit_last20": float(tail["deficit"].mean()),
        "gini_assets": float(final["gini_assets"]),
        "means_tested_poverty_rate": float(final["means_tested_poverty_rate"]),
        "unemployment_rate": float(final["unemployment_rate"]),
        "tax_revenue": float(tail["tax_revenue"].mean()),
        "ubi_spending": float(tail["ubi_spending"].mean()),
        "targeted_spending": float(tail["targeted_spending"].mean()),
    }


def score(row: dict[str, float], baseline_gini: float, baseline_poverty: float) -> float:
    treasury_penalty = max(0.0, -row["final_treasury"]) / 1_000_000.0
    deficit_penalty = abs(row["avg_deficit_last20"]) / 100_000.0
    gini_reward = max(0.0, baseline_gini - row["gini_assets"]) * 6.0
    poverty_penalty = max(0.0, row["means_tested_poverty_rate"] - baseline_poverty) * 2.0
    unemployment_penalty = max(0.0, row["unemployment_rate"] - 0.65) * 1.5
    return deficit_penalty + treasury_penalty + poverty_penalty + unemployment_penalty - gini_reward


def main() -> None:
    outdir = Path("outputs")
    outdir.mkdir(parents=True, exist_ok=True)
    steps = 80
    seeds = [11, 42, 77]
    baseline = run_config(
        ModelConfig(ubi_amount=0.0, subsidy_tiers=()),
        seed=42,
        steps=steps,
    )

    rows: list[dict[str, float | str]] = []
    grid = itertools.product(
        [0.16, 0.20, 0.24, 0.28],
        [0.20, 0.24, 0.28],
        [40.0, 60.0, 80.0, 100.0],
        [0.25, 0.35, 0.45, 0.55],
    )
    for income_tax, corp_tax, ubi, tier_scale in grid:
        metrics = []
        for seed in seeds:
            config = ModelConfig(
                income_tax_rate=income_tax,
                corporate_tax_rate=corp_tax,
                ubi_amount=ubi,
                subsidy_tiers=scale_tiers(tier_scale),
                targeted_error_rate=0.05,
            )
            metrics.append(run_config(config, seed=seed, steps=steps))
        row = {
            "income_tax_rate": income_tax,
            "corporate_tax_rate": corp_tax,
            "ubi_amount": ubi,
            "tier_scale": tier_scale,
        }
        for key in metrics[0]:
            row[key] = sum(item[key] for item in metrics) / len(metrics)
        row["score"] = score(row, baseline["gini_assets"], baseline["means_tested_poverty_rate"])
        rows.append(row)

    df = pd.DataFrame(rows).sort_values("score")
    path = outdir / "policy_calibration.csv"
    df.to_csv(path, index=False)
    print(f"calibration_csv={path}")
    print(df.head(12).to_string(index=False))


if __name__ == "__main__":
    main()

