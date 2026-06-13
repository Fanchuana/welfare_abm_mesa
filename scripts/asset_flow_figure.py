from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from welfare_abm import WelfareModel
from welfare_abm.agents import HouseholdType
from welfare_abm.config import ModelConfig, SubsidyTier


FIG = PROJECT_ROOT / "report" / "figures"
DATA = PROJECT_ROOT / "report" / "data"
COMIC_FONT = Path("/work/home/cryoem666/xyf/temp/pycharm/OPUS-BioLLM-CSTP/font/Comic-Sans-MS-Regular-2.ttf")

TYPE_LABELS = {
    HouseholdType.SINGLE_YOUNG: "Single\nyoung",
    HouseholdType.COUPLE_WITH_CHILDREN: "Families\nwith kids",
    HouseholdType.ELDERLY: "Elderly",
    HouseholdType.DISABLED: "Disabled",
}

TYPE_COLORS = {
    HouseholdType.SINGLE_YOUNG: "#5B7DB9",
    HouseholdType.COUPLE_WITH_CHILDREN: "#3B8B6E",
    HouseholdType.ELDERLY: "#C99A2E",
    HouseholdType.DISABLED: "#B95F5F",
}


def set_style() -> None:
    family = "Comic Sans MS"
    if COMIC_FONT.exists():
        font_manager.fontManager.addfont(str(COMIC_FONT))
        family = font_manager.FontProperties(fname=str(COMIC_FONT)).get_name()
    plt.rcParams.update(
        {
            "font.family": family,
            "axes.unicode_minus": False,
            "figure.dpi": 160,
            "savefig.dpi": 300,
            "font.size": 10,
        }
    )


def mixed_config() -> ModelConfig:
    tiers = (
        SubsidyTier(max_income=450.0, amount=90.0),
        SubsidyTier(max_income=700.0, amount=60.0),
        SubsidyTier(max_income=950.0, amount=30.0),
    )
    return ModelConfig(
        ubi_amount=100.0,
        subsidy_tiers=tiers,
        false_positive_rate=0.05,
        false_negative_rate=0.05,
    )


def collect_tail_flows(seeds: range = range(21, 41), steps: int = 80, tail: int = 20) -> tuple[pd.DataFrame, pd.DataFrame]:
    type_rows = []
    total_rows = []
    for seed in seeds:
        model = WelfareModel(config=mixed_config(), seed=seed)
        for step in range(1, steps + 1):
            model.step()
            if step <= steps - tail:
                continue

            by_type = defaultdict(lambda: defaultdict(float))
            for household in model.households:
                bucket = by_type[household.household_type]
                bucket["wages"] += household.wage_income
                bucket["income_tax"] += household.taxes_paid
                bucket["ubi"] += household.ubi_received
                bucket["targeted"] += household.targeted_received
                bucket["consumption"] += household.consumption
                bucket["net_assets"] += (
                    household.wage_income
                    + household.ubi_received
                    + household.targeted_received
                    - household.taxes_paid
                    - household.consumption
                )

            for household_type, values in by_type.items():
                type_rows.append(
                    {
                        "seed": seed,
                        "step": step,
                        "household_type": household_type.value,
                        **values,
                    }
                )

            total_rows.append(
                {
                    "seed": seed,
                    "step": step,
                    "wages": sum(h.wage_income for h in model.households),
                    "income_tax": sum(h.taxes_paid for h in model.households),
                    "corporate_tax": sum(f.taxes_paid for f in model.firms),
                    "ubi": model.government.ubi_spending,
                    "targeted": model.government.targeted_spending,
                    "consumption": model.total_household_consumption,
                    "tax_revenue": model.government.tax_revenue,
                    "welfare_spending": model.government.ubi_spending + model.government.targeted_spending,
                    "treasury_delta": model.government.tax_revenue
                    - model.government.ubi_spending
                    - model.government.targeted_spending,
                    "false_positive": model.government.false_positive_spending,
                    "false_negative": model.government.false_negative_amount,
                }
            )

    flow_columns = [
        "wages",
        "income_tax",
        "corporate_tax",
        "ubi",
        "targeted",
        "consumption",
        "tax_revenue",
        "welfare_spending",
        "treasury_delta",
        "false_positive",
        "false_negative",
    ]
    type_df = pd.DataFrame(type_rows)
    total_df = pd.DataFrame(total_rows)
    type_summary = type_df.groupby("household_type", as_index=False).mean(numeric_only=True)
    total_summary = total_df[flow_columns].mean(numeric_only=True).to_frame("mean").reset_index(names="flow")
    return type_summary, total_summary


def draw_box(ax, xy: tuple[float, float], width: float, height: float, label: str, color: str) -> None:
    patch = FancyBboxPatch(
        xy,
        width,
        height,
        boxstyle="round,pad=0.018,rounding_size=0.025",
        facecolor=color,
        edgecolor="#2F2F2F",
        linewidth=1.0,
        alpha=0.96,
    )
    ax.add_patch(patch)
    ax.text(
        xy[0] + width / 2,
        xy[1] + height / 2,
        label,
        ha="center",
        va="center",
        color="white",
        fontsize=10.5,
        fontweight="bold",
    )


def draw_flow(
    ax,
    start: tuple[float, float],
    end: tuple[float, float],
    value: float,
    label: str,
    color: str,
    max_value: float,
    rad: float = 0.0,
    text_offset: tuple[float, float] = (0.0, 0.0),
) -> None:
    width = 1.4 + 12.0 * value / max_value
    arrow = FancyArrowPatch(
        start,
        end,
        arrowstyle="-|>",
        mutation_scale=12 + width * 0.45,
        linewidth=width,
        color=color,
        alpha=0.62,
        connectionstyle=f"arc3,rad={rad}",
        shrinkA=8,
        shrinkB=8,
        capstyle="round",
        joinstyle="round",
    )
    ax.add_patch(arrow)
    mid = ((start[0] + end[0]) / 2 + text_offset[0], (start[1] + end[1]) / 2 + text_offset[1])
    ax.text(
        mid[0],
        mid[1],
        f"{label}\n{value/1000:.1f}k",
        ha="center",
        va="center",
        fontsize=9,
        color="#222222",
        bbox=dict(boxstyle="round,pad=0.22", facecolor="white", edgecolor="none", alpha=0.78),
    )


def plot_asset_flow(type_summary: pd.DataFrame, total_summary: pd.DataFrame) -> None:
    totals = total_summary.set_index("flow")["mean"]
    max_value = float(max(totals["consumption"], totals["wages"], totals["welfare_spending"], totals["tax_revenue"]))

    fig, ax = plt.subplots(figsize=(12.8, 7.2))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.set_title("Asset-flow balance under mixed welfare policy", fontsize=15, fontweight="bold", pad=14)

    draw_box(ax, (0.06, 0.48), 0.15, 0.12, "Firms", "#34495E")
    draw_box(ax, (0.42, 0.73), 0.16, 0.12, "Government", "#6A4C93")
    draw_box(ax, (0.79, 0.48), 0.15, 0.12, "Market\nconsumption", "#7A6A53")
    household_frame = FancyBboxPatch(
        (0.315, 0.105),
        0.365,
        0.39,
        boxstyle="round,pad=0.02,rounding_size=0.02",
        facecolor="#F7F8FB",
        edgecolor="#CBD2DD",
        linewidth=1.0,
        alpha=0.55,
        zorder=-2,
    )
    ax.add_patch(household_frame)
    ax.text(0.497, 0.485, "Households by type", ha="center", va="bottom", fontsize=9.5, color="#555555")

    household_positions = {
        HouseholdType.SINGLE_YOUNG: (0.34, 0.36),
        HouseholdType.COUPLE_WITH_CHILDREN: (0.50, 0.36),
        HouseholdType.ELDERLY: (0.34, 0.15),
        HouseholdType.DISABLED: (0.50, 0.15),
    }
    for household_type, pos in household_positions.items():
        row = type_summary[type_summary["household_type"] == household_type.value]
        assets = float(row["net_assets"].iloc[0]) if not row.empty else 0.0
        label = f"{TYPE_LABELS[household_type]}\nnet {assets/1000:+.1f}k"
        draw_box(ax, pos, 0.13, 0.105, label, TYPE_COLORS[household_type])

    draw_flow(
        ax,
        (0.21, 0.54),
        (0.405, 0.37),
        totals["wages"],
        "wages",
        "#2E86AB",
        max_value,
        rad=-0.04,
        text_offset=(-0.01, -0.055),
    )
    draw_flow(
        ax,
        (0.45, 0.49),
        (0.47, 0.73),
        totals["income_tax"],
        "income tax",
        "#D1495B",
        max_value,
        rad=0.06,
        text_offset=(-0.145, 0.01),
    )
    draw_flow(
        ax,
        (0.17, 0.60),
        (0.43, 0.78),
        totals["corporate_tax"],
        "corp. tax",
        "#9B2226",
        max_value,
        rad=0.09,
        text_offset=(-0.01, 0.065),
    )
    draw_flow(
        ax,
        (0.50, 0.73),
        (0.405, 0.43),
        totals["ubi"],
        "UBI",
        "#8ECAE6",
        max_value,
        rad=0.10,
        text_offset=(-0.18, -0.02),
    )
    draw_flow(
        ax,
        (0.53, 0.73),
        (0.50, 0.43),
        totals["targeted"],
        "targeted",
        "#70AD47",
        max_value,
        rad=-0.08,
        text_offset=(0.16, 0.03),
    )
    draw_flow(
        ax,
        (0.58, 0.34),
        (0.79, 0.54),
        totals["consumption"],
        "consumption",
        "#F4A261",
        max_value,
        rad=0.04,
        text_offset=(0.01, -0.045),
    )

    balance = totals["treasury_delta"]
    balance_color = "#2A9D8F" if balance >= 0 else "#C0392B"
    ax.text(
        0.50,
        0.93,
        f"Tail-period fiscal balance: tax revenue - transfers = {balance/1000:+.1f}k per step",
        ha="center",
        va="center",
        fontsize=11,
        fontweight="bold",
        color=balance_color,
        bbox=dict(boxstyle="round,pad=0.35", facecolor="#F7F8FB", edgecolor="#CBD2DD", linewidth=0.8),
    )
    ax.text(
        0.50,
        0.045,
        "Width is proportional to the average monetary flow in the last 20 steps across 20 random seeds.",
        ha="center",
        va="center",
        fontsize=9.5,
        color="#555555",
    )
    fig.savefig(FIG / "fig5_asset_flow.png", bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    DATA.mkdir(parents=True, exist_ok=True)
    set_style()
    type_summary, total_summary = collect_tail_flows()
    type_summary.to_csv(DATA / "asset_flows_by_household_type.csv", index=False)
    total_summary.to_csv(DATA / "asset_flows_summary.csv", index=False)
    plot_asset_flow(type_summary, total_summary)
    print(f"wrote {FIG / 'fig5_asset_flow.png'}")
    print(f"wrote {DATA / 'asset_flows_summary.csv'}")


if __name__ == "__main__":
    main()
