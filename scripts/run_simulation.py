from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from welfare_abm import WelfareModel
from welfare_abm.config import ModelConfig, SubsidyTier


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run WelfareABM policy simulation.")
    parser.add_argument("--steps", type=int, default=80)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--households", type=int, default=220)
    parser.add_argument("--firms", type=int, default=4)
    parser.add_argument("--ubi", type=float, default=100.0)
    parser.add_argument("--error-rate", type=float, default=0.05)
    parser.add_argument("--false-positive-rate", type=float, default=None)
    parser.add_argument("--false-negative-rate", type=float, default=None)
    parser.add_argument("--outdir", type=Path, default=Path("outputs"))
    return parser.parse_args()


def build_config(args: argparse.Namespace) -> ModelConfig:
    return ModelConfig(
        n_households=args.households,
        n_firms=args.firms,
        ubi_amount=args.ubi,
        targeted_error_rate=args.error_rate,
        false_positive_rate=args.false_positive_rate,
        false_negative_rate=args.false_negative_rate,
        subsidy_tiers=(
            SubsidyTier(max_income=450.0, amount=90.0),
            SubsidyTier(max_income=700.0, amount=60.0),
            SubsidyTier(max_income=950.0, amount=30.0),
        ),
    )


def plot_metrics(df: pd.DataFrame, path: Path) -> None:
    fig, axes = plt.subplots(3, 2, figsize=(12, 10), constrained_layout=True)
    series = [
        ("gini_assets", "Asset Gini"),
        ("means_tested_poverty_rate", "Means-tested poverty"),
        ("unemployment_rate", "Unemployment rate"),
        ("treasury", "Government treasury"),
        ("avg_wage", "Average wage"),
        ("deficit", "Period deficit"),
    ]
    for ax, (column, title) in zip(axes.flat, series):
        ax.plot(df.index, df[column], linewidth=2)
        ax.set_title(title)
        ax.set_xlabel("Step")
        ax.grid(alpha=0.25)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def main() -> None:
    args = parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)
    model = WelfareModel(config=build_config(args), seed=args.seed)
    for _ in range(args.steps):
        model.step()

    df = model.datacollector.get_model_vars_dataframe()
    csv_path = args.outdir / "welfare_abm_metrics.csv"
    fig_path = args.outdir / "welfare_abm_metrics.png"
    df.to_csv(csv_path, index_label="step")
    plot_metrics(df, fig_path)

    final = df.iloc[-1]
    print("Simulation finished")
    print(f"metrics_csv={csv_path}")
    print(f"metrics_plot={fig_path}")
    print(
        "final: "
        f"gini_assets={final['gini_assets']:.3f}, "
        f"poverty_rate={final['poverty_rate']:.3f}, "
        f"unemployment_rate={final['unemployment_rate']:.3f}, "
        f"treasury={final['treasury']:.1f}"
    )


if __name__ == "__main__":
    main()
