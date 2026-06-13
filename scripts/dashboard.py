from __future__ import annotations

import base64
import html
import io
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import matplotlib.pyplot as plt
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from welfare_abm import WelfareModel
from welfare_abm.config import ModelConfig, SubsidyTier


DEFAULTS = {
    "steps": 80,
    "seed": 42,
    "households": 220,
    "firms": 4,
    "income_tax": 0.20,
    "corp_tax": 0.28,
    "ubi": 100.0,
    "false_positive_rate": 0.05,
    "false_negative_rate": 0.05,
    "tier_scale": 1.0,
}

BASE_TIERS = (
    SubsidyTier(max_income=450.0, amount=90.0),
    SubsidyTier(max_income=700.0, amount=60.0),
    SubsidyTier(max_income=950.0, amount=30.0),
)


def get_number(params: dict[str, list[str]], key: str, default, cast):
    try:
        return cast(params.get(key, [default])[0])
    except (TypeError, ValueError):
        return default


def parse_params(query: str) -> dict[str, float | int]:
    raw = parse_qs(query)
    return {
        "steps": get_number(raw, "steps", DEFAULTS["steps"], int),
        "seed": get_number(raw, "seed", DEFAULTS["seed"], int),
        "households": get_number(raw, "households", DEFAULTS["households"], int),
        "firms": get_number(raw, "firms", DEFAULTS["firms"], int),
        "income_tax": get_number(raw, "income_tax", DEFAULTS["income_tax"], float),
        "corp_tax": get_number(raw, "corp_tax", DEFAULTS["corp_tax"], float),
        "ubi": get_number(raw, "ubi", DEFAULTS["ubi"], float),
        "false_positive_rate": get_number(raw, "false_positive_rate", DEFAULTS["false_positive_rate"], float),
        "false_negative_rate": get_number(raw, "false_negative_rate", DEFAULTS["false_negative_rate"], float),
        "tier_scale": get_number(raw, "tier_scale", DEFAULTS["tier_scale"], float),
    }


def scaled_tiers(scale: float) -> tuple[SubsidyTier, ...]:
    return tuple(SubsidyTier(t.max_income, t.amount * scale) for t in BASE_TIERS)


def run_model(params: dict[str, float | int]) -> pd.DataFrame:
    config = ModelConfig(
        n_households=int(params["households"]),
        n_firms=int(params["firms"]),
        income_tax_rate=float(params["income_tax"]),
        corporate_tax_rate=float(params["corp_tax"]),
        ubi_amount=float(params["ubi"]),
        false_positive_rate=float(params["false_positive_rate"]),
        false_negative_rate=float(params["false_negative_rate"]),
        subsidy_tiers=scaled_tiers(float(params["tier_scale"])),
    )
    model = WelfareModel(config=config, seed=int(params["seed"]))
    for _ in range(int(params["steps"])):
        model.step()
    return model.datacollector.get_model_vars_dataframe()


def figure_data_uri(df: pd.DataFrame) -> str:
    fig, axes = plt.subplots(2, 2, figsize=(11, 7), constrained_layout=True)
    plots = [
        ("gini_assets", "Asset Gini"),
        ("means_tested_poverty_rate", "Means-tested poverty"),
        ("unemployment_rate", "Unemployment rate"),
        ("treasury", "Government treasury"),
    ]
    for ax, (column, title) in zip(axes.flat, plots):
        ax.plot(df.index, df[column], linewidth=2.2, color="#2454a6")
        ax.set_title(title)
        ax.set_xlabel("Step")
        ax.grid(alpha=0.25)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=160)
    plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def metric_card(label: str, value: float, suffix: str = "") -> str:
    return f"""
    <div class="metric">
      <span>{html.escape(label)}</span>
      <strong>{value:,.3f}{html.escape(suffix)}</strong>
    </div>
    """


def render_page(params: dict[str, float | int]) -> bytes:
    df = run_model(params)
    final = df.iloc[-1]
    chart = figure_data_uri(df)
    metrics = "".join(
        [
            metric_card("Asset Gini", final["gini_assets"]),
            metric_card("Means-tested poverty", final["means_tested_poverty_rate"]),
            metric_card("Unemployment", final["unemployment_rate"]),
            metric_card("Treasury", final["treasury"]),
            metric_card("Tax revenue", final["tax_revenue"]),
            metric_card("UBI spending", final["ubi_spending"]),
            metric_card("Targeted spending", final["targeted_spending"]),
            metric_card("Households", final["households"]),
        ]
    )
    inputs = [
        ("steps", "Steps", "number", 20, 200, 1),
        ("seed", "Seed", "number", 1, 9999, 1),
        ("households", "Households", "number", 50, 600, 10),
        ("firms", "Firms", "number", 3, 8, 1),
        ("income_tax", "Income tax", "number", 0, 0.5, 0.01),
        ("corp_tax", "Corporate tax", "number", 0, 0.5, 0.01),
        ("ubi", "UBI", "number", 0, 250, 10),
        ("false_positive_rate", "False positive rate", "number", 0, 0.5, 0.01),
        ("false_negative_rate", "False negative rate", "number", 0, 0.5, 0.01),
        ("tier_scale", "Targeted scale", "number", 0, 3, 0.05),
    ]
    controls = "\n".join(
        f"""
        <label>
          <span>{label}</span>
          <input name="{key}" type="{typ}" min="{minv}" max="{maxv}" step="{step}" value="{params[key]}">
        </label>
        """
        for key, label, typ, minv, maxv, step in inputs
    )
    body = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>WelfareABM Dashboard</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #172033;
      --muted: #667085;
      --line: #d7dce5;
      --panel: #f7f8fb;
      --accent: #2454a6;
      --bg: #ffffff;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Arial, Helvetica, sans-serif;
      color: var(--ink);
      background: var(--bg);
    }}
    header {{
      padding: 20px 28px 12px;
      border-bottom: 1px solid var(--line);
    }}
    h1 {{
      margin: 0;
      font-size: 24px;
      letter-spacing: 0;
    }}
    main {{
      display: grid;
      grid-template-columns: 320px minmax(0, 1fr);
      min-height: calc(100vh - 70px);
    }}
    aside {{
      padding: 20px;
      border-right: 1px solid var(--line);
      background: var(--panel);
    }}
    form {{
      display: grid;
      gap: 12px;
    }}
    label {{
      display: grid;
      gap: 5px;
      font-size: 13px;
      color: var(--muted);
    }}
    input {{
      width: 100%;
      padding: 9px 10px;
      border: 1px solid #c8cfda;
      border-radius: 6px;
      background: #fff;
      color: var(--ink);
      font-size: 14px;
    }}
    button {{
      margin-top: 6px;
      padding: 10px 12px;
      border: 0;
      border-radius: 6px;
      background: var(--accent);
      color: white;
      font-size: 14px;
      cursor: pointer;
    }}
    section {{
      padding: 20px 24px 28px;
    }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(4, minmax(130px, 1fr));
      gap: 10px;
      margin-bottom: 18px;
    }}
    .metric {{
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 12px;
      background: #fff;
    }}
    .metric span {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 7px;
    }}
    .metric strong {{
      font-size: 18px;
      font-weight: 700;
    }}
    .chart {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
    }}
    .note {{
      margin-top: 12px;
      color: var(--muted);
      font-size: 13px;
    }}
    @media (max-width: 860px) {{
      main {{ grid-template-columns: 1fr; }}
      aside {{ border-right: 0; border-bottom: 1px solid var(--line); }}
      .metrics {{ grid-template-columns: repeat(2, minmax(120px, 1fr)); }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>WelfareABM Dashboard</h1>
  </header>
  <main>
    <aside>
      <form method="get">
        {controls}
        <button type="submit">Run Simulation</button>
      </form>
    </aside>
    <section>
      <div class="metrics">{metrics}</div>
      <img class="chart" src="{chart}" alt="Simulation metric curves">
      <p class="note">Each step represents roughly one quarter. The dashboard reruns the model after submitting parameters.</p>
    </section>
  </main>
</body>
</html>"""
    return body.encode("utf-8")


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        params = parse_params(parsed.query)
        try:
            body = render_page(params)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as exc:
            message = f"Dashboard error: {type(exc).__name__}: {exc}".encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(message)))
            self.end_headers()
            self.wfile.write(message)

    def log_message(self, format: str, *args) -> None:
        print(format % args)


def main() -> None:
    host = "127.0.0.1"
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    server = ThreadingHTTPServer((host, port), DashboardHandler)
    print(f"WelfareABM dashboard: http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
