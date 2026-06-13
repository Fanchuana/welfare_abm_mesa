from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from welfare_abm import WelfareModel
from welfare_abm.config import ModelConfig, SubsidyTier


def run_case(name: str, config: ModelConfig, seed: int, steps: int) -> pd.DataFrame:
    model = WelfareModel(config=config, seed=seed)
    for _ in range(steps):
        model.step()
    df = model.datacollector.get_model_vars_dataframe()
    df["policy"] = name
    return df


def plot_compare(all_df: pd.DataFrame, path: Path) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), constrained_layout=True)
    metrics = [
        ("gini_assets", "Asset Gini"),
        ("means_tested_poverty_rate", "Means-tested poverty"),
        ("unemployment_rate", "Unemployment rate"),
        ("treasury", "Government treasury"),
    ]
    for ax, (metric, title) in zip(axes.flat, metrics):
        for policy, df in all_df.groupby("policy"):
            ax.plot(df["step"], df[metric], label=policy, linewidth=1.8)
        ax.set_title(title)
        ax.set_xlabel("Step")
        ax.grid(alpha=0.25)
    axes[0, 0].legend(fontsize=8)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def main() -> None:
    outdir = Path("outputs")
    outdir.mkdir(parents=True, exist_ok=True)
    steps = 80
    seed = 42
    base_tiers = (
        SubsidyTier(max_income=450.0, amount=90.0),
        SubsidyTier(max_income=700.0, amount=60.0),
        SubsidyTier(max_income=950.0, amount=30.0),
    )
    no_tiers: tuple[SubsidyTier, ...] = ()

    cases = {
        "no_welfare": ModelConfig(ubi_amount=0.0, subsidy_tiers=no_tiers),
        "ubi_only": ModelConfig(ubi_amount=100.0, subsidy_tiers=no_tiers),
        "targeted_only": ModelConfig(ubi_amount=0.0, subsidy_tiers=base_tiers, false_positive_rate=0.05, false_negative_rate=0.05),
        "mixed_5pct_error": ModelConfig(ubi_amount=100.0, subsidy_tiers=base_tiers, false_positive_rate=0.05, false_negative_rate=0.05),
        "mixed_15pct_error": ModelConfig(ubi_amount=100.0, subsidy_tiers=base_tiers, false_positive_rate=0.15, false_negative_rate=0.15),
    }
    all_df = pd.concat(
        [run_case(name, config, seed=seed, steps=steps) for name, config in cases.items()],
        ignore_index=False,
    )
    all_df = all_df.rename_axis("step").reset_index()
    csv_path = outdir / "policy_comparison.csv"
    fig_path = outdir / "policy_comparison.png"
    all_df.to_csv(csv_path, index=False)
    plot_compare(all_df, fig_path)

    final = all_df.sort_values("step").groupby("policy").tail(1)
    print("Policy comparison finished")
    print(f"comparison_csv={csv_path}")
    print(f"comparison_plot={fig_path}")
    print(
        final[
            [
                "policy",
                "gini_assets",
                "poverty_rate",
                "means_tested_poverty_rate",
                "unemployment_rate",
                "treasury",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
