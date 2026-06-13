from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from welfare_abm import WelfareModel
from welfare_abm.config import ModelConfig, SubsidyTier


OUT = Path("report/figures")
OUT.mkdir(parents=True, exist_ok=True)
DATA = Path("report/data")
COMIC_FONT = Path("/work/home/cryoem666/xyf/temp/pycharm/OPUS-BioLLM-CSTP/font/Comic-Sans-MS-Regular-2.ttf")

COLORS = {
    "No welfare": "#6E6E6E",
    "UBI only": "#3B6BB5",
    "Targeted only": "#C9912B",
    "Mixed, 5% error": "#3A8B3A",
    "Mixed, 15% error": "#C0392B",
}
ORDER = ["No welfare", "UBI only", "Targeted only", "Mixed, 5% error", "Mixed, 15% error"]


def set_style() -> None:
    font_family = "Comic Sans MS"
    if COMIC_FONT.exists():
        from matplotlib import font_manager

        font_manager.fontManager.addfont(str(COMIC_FONT))
        font_family = font_manager.FontProperties(fname=str(COMIC_FONT)).get_name()
    plt.rcParams.update(
        {
            "font.family": font_family,
            "axes.unicode_minus": False,
            "font.size": 10.5,
            "axes.labelsize": 11,
            "axes.titlesize": 12,
            "legend.fontsize": 9,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "figure.dpi": 160,
            "savefig.dpi": 300,
        }
    )


def policy_configs() -> dict[str, ModelConfig]:
    tiers = (
        SubsidyTier(max_income=450.0, amount=90.0),
        SubsidyTier(max_income=700.0, amount=60.0),
        SubsidyTier(max_income=950.0, amount=30.0),
    )
    return {
        "No welfare": ModelConfig(ubi_amount=0.0, subsidy_tiers=()),
        "UBI only": ModelConfig(ubi_amount=100.0, subsidy_tiers=()),
        "Targeted only": ModelConfig(ubi_amount=0.0, subsidy_tiers=tiers, false_positive_rate=0.05, false_negative_rate=0.05),
        "Mixed, 5% error": ModelConfig(ubi_amount=100.0, subsidy_tiers=tiers, false_positive_rate=0.05, false_negative_rate=0.05),
        "Mixed, 15% error": ModelConfig(ubi_amount=100.0, subsidy_tiers=tiers, false_positive_rate=0.15, false_negative_rate=0.15),
    }


def make_time_series() -> pd.DataFrame:
    path = DATA / "multi_seed_timeseries.csv"
    if path.exists():
        return pd.read_csv(path)
    rows = []
    for policy, config in policy_configs().items():
        for seed in range(21, 41):
            model = WelfareModel(config=config, seed=seed)
            for _ in range(80):
                model.step()
            df = model.datacollector.get_model_vars_dataframe().reset_index(names="step")
            df["policy"] = policy
            df["seed"] = seed
            rows.append(df)
    ts = pd.concat(rows, ignore_index=True)
    DATA.mkdir(parents=True, exist_ok=True)
    ts.to_csv(path, index=False)
    return ts


def open_axes(ax) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_linewidth(0.9)
    ax.spines["bottom"].set_linewidth(0.9)
    ax.grid(axis="y", color="#E6E6E6", linestyle="--", linewidth=0.7)


def plot_dynamic_curves(ts: pd.DataFrame) -> None:
    metrics = [
        ("gini_assets", "Asset Gini"),
        ("treasury", "Government treasury"),
        ("unemployment_rate", "Unemployment rate"),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(13.2, 3.8), constrained_layout=True)
    for ax, (metric, title) in zip(axes, metrics):
        for policy in ORDER:
            sub = ts[ts["policy"] == policy]
            stat = sub.groupby("step")[metric].agg(["mean", "std"]).reset_index()
            x = stat["step"].to_numpy()
            mean = stat["mean"].to_numpy()
            std = stat["std"].fillna(0).to_numpy()
            ax.plot(x, mean, color=COLORS[policy], lw=1.8, label=policy)
            if policy in {"No welfare", "Mixed, 5% error"}:
                ax.fill_between(x, mean - std, mean + std, color=COLORS[policy], alpha=0.13, linewidth=0)
        ax.set_title(title)
        ax.set_xlabel("Step")
        open_axes(ax)
    axes[0].set_ylabel("Value")
    axes[0].legend(frameon=False, loc="best")
    fig.savefig(OUT / "fig1_dynamic_curves.png", bbox_inches="tight")
    plt.close(fig)


def plot_policy_bars(summary: pd.DataFrame) -> None:
    labels = ORDER
    x = np.arange(len(labels))
    width = 0.28
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), constrained_layout=True)
    metrics = [
        ("gini_assets", "Asset Gini", "lower is better"),
        ("means_tested_poverty_rate", "Means-tested poverty", "lower is better"),
    ]
    for ax, (metric, ylabel, note) in zip(axes, metrics):
        means = [summary.loc[summary.policy == p, f"{metric}_mean"].item() for p in labels]
        stds = [summary.loc[summary.policy == p, f"{metric}_std"].item() for p in labels]
        bars = ax.bar(x, means, yerr=stds, width=0.62, color=[COLORS[p] for p in labels],
                      edgecolor="white", linewidth=0.8, capsize=3)
        for bar, policy, value in zip(bars, labels, means):
            if policy == "Mixed, 5% error":
                bar.set_hatch("//")
                bar.set_edgecolor("#2F6F2F")
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.015,
                    f"{value:.2f}", ha="center", va="bottom",
                    fontsize=8.5, fontweight="bold" if policy == "Mixed, 5% error" else "normal")
        ax.set_xticks(x)
        ax.set_xticklabels(["No\nwelfare", "UBI\nonly", "Targeted\nonly", "Mixed\n5%", "Mixed\n15%"])
        ax.set_ylabel(ylabel)
        ax.set_title(note)
        open_axes(ax)
    fig.savefig(OUT / "fig2_policy_outcomes.png", bbox_inches="tight")
    plt.close(fig)


def plot_tradeoff(summary: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(6.2, 4.6), constrained_layout=True)
    for policy in ORDER:
        row = summary[summary.policy == policy].iloc[0]
        x = row["treasury_mean"] / 1e6
        y = row["gini_assets_mean"]
        ax.scatter(x, y, s=95, color=COLORS[policy], edgecolor="white", linewidth=0.8, zorder=3)
        ax.text(x + 0.08, y, policy, va="center", fontsize=8.8)
    ax.set_xlabel("Final treasury (million)")
    ax.set_ylabel("Final asset Gini")
    ax.set_title("Fiscal-equity trade-off")
    open_axes(ax)
    fig.savefig(OUT / "fig3_tradeoff.png", bbox_inches="tight")
    plt.close(fig)


def plot_error_accounting(summary: pd.DataFrame) -> None:
    labels = ["Mixed, 5% error", "Mixed, 15% error"]
    x = np.arange(len(labels))
    fp = [summary.loc[summary.policy == p, "false_positive_spending_mean"].item() for p in labels]
    fn = [summary.loc[summary.policy == p, "false_negative_amount_mean"].item() for p in labels]
    fig, ax = plt.subplots(figsize=(6.4, 4.2), constrained_layout=True)
    ax.bar(x - 0.16, fp, width=0.32, color="#C0392B", label="False-positive spending")
    ax.bar(x + 0.16, fn, width=0.32, color="#3B6BB5", label="False-negative missed aid")
    ax.set_xticks(x)
    ax.set_xticklabels(["5% error", "15% error"])
    ax.set_ylabel("Amount per period")
    ax.set_title("Targeting error accounting")
    open_axes(ax)
    ax.legend(frameon=False)
    fig.savefig(OUT / "fig4_error_accounting.png", bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    set_style()
    summary = pd.read_csv(DATA / "multi_seed_summary.csv")
    ts = make_time_series()
    plot_dynamic_curves(ts)
    plot_policy_bars(summary)
    plot_tradeoff(summary)
    plot_error_accounting(summary)
    print(f"wrote figures to {OUT}")


if __name__ == "__main__":
    main()
