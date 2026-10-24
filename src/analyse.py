"""Analyse bus punctuality by local authority.

Questions:
1. How has the share of non-frequent bus services running on time changed nationally?
2. Which areas are the most and least punctual in the latest year?
3. Which areas have recovered, or fallen further, since before the pandemic?
4. Has the gap between the best and worst areas widened?

Run:  python src/analyse.py   (after src/fetch_data.py)
Writes results/summary.md, results/*.png and results/area_changes.csv.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
NATIONAL_NAMES = ("england", "england outside london", "great britain")
BASELINE_PREFERENCE = ("2018/19", "2019/20", "2019", "2018")
BLUE, GREY, RED = "#1f4e79", "#b7c4cf", "#b03a2e"


def split_national(long: pd.DataFrame) -> tuple[pd.Series, pd.DataFrame]:
    """Separate the England total (if the table has one) from individual areas.

    Aggregate rows such as regions and 'England' are excluded from area rankings.
    """
    name = long["area"].str.lower().str.strip()
    is_total = name.isin(NATIONAL_NAMES)
    codes = long.get("area_code")
    if codes is not None:
        # E92 = England, E12 = English regions: aggregates, not local authorities
        is_total |= codes.fillna("").str.match(r"^E(92|12)")
    is_region = name.str.contains(r"\b(?:region|north east|north west|yorkshire and the humber|east midlands|"
                                  r"west midlands|east of england|south east|south west)$", regex=True) & ~name.str.contains(
        "council|borough|county|city|district|unitary")
    england = long[name == "england"].set_index("year")["pct_on_time"]
    areas = long[~is_total & ~is_region]
    if england.empty:
        england = areas.groupby("year")["pct_on_time"].median().rename("pct_on_time")
        england.attrs["derived"] = True
    return england.sort_index(), areas


def pick_baseline(years: list[str]) -> str:
    for y in BASELINE_PREFERENCE:
        if y in years:
            return y
    return years[0]


def area_changes(areas: pd.DataFrame, baseline: str, latest: str) -> pd.DataFrame:
    wide = areas.pivot_table(index="area", columns="year", values="pct_on_time", aggfunc="mean")
    both = wide[[baseline, latest]].dropna()
    out = pd.DataFrame({"baseline": both[baseline], "latest": both[latest]})
    out["change_pp"] = out["latest"] - out["baseline"]
    return out.sort_values("change_pp")


def spread_by_year(areas: pd.DataFrame) -> pd.DataFrame:
    g = areas.groupby("year")["pct_on_time"]
    return pd.DataFrame({"p10": g.quantile(0.1), "median": g.median(), "p90": g.quantile(0.9), "n": g.count()})


def charts(england: pd.Series, spread: pd.DataFrame, latest_rank: pd.Series, changes: pd.DataFrame, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.fill_between(spread.index, spread["p10"], spread["p90"], color=GREY, alpha=0.5, label="Middle 80% of areas")
    ax.plot(england.index, england.values, color=BLUE, marker="o", label="England" if not england.attrs.get("derived") else "Median area")
    ax.set_ylabel("% of non-frequent services on time")
    ax.set_title("Bus punctuality over time")
    ax.legend(frameon=False)
    ax.tick_params(axis="x", rotation=45)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(out / "trend.png", dpi=150); plt.close(fig)

    show = pd.concat([latest_rank.head(10), latest_rank.tail(10)])
    fig, ax = plt.subplots(figsize=(8, 7))
    colors = [RED] * min(10, len(latest_rank)) + [BLUE] * (len(show) - min(10, len(latest_rank)))
    ax.barh(show.index, show.values, color=colors)
    ax.invert_yaxis()
    ax.set_xlabel("% on time")
    ax.set_title("Least (red) and most (blue) punctual areas, latest year")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(out / "best_worst_latest.png", dpi=150); plt.close(fig)

    if not changes.empty:
        fig, ax = plt.subplots(figsize=(6, 6))
        ax.scatter(changes["baseline"], changes["latest"], s=16, color=BLUE, alpha=0.7)
        lo = min(changes.min(numeric_only=True)[["baseline", "latest"]]) - 2
        hi = max(changes.max(numeric_only=True)[["baseline", "latest"]]) + 2
        ax.plot([lo, hi], [lo, hi], color="black", linewidth=0.8, linestyle="--")
        ax.set_xlabel("% on time, pre-pandemic baseline")
        ax.set_ylabel("% on time, latest year")
        ax.set_title("Areas below the line are less punctual than before")
        ax.spines[["top", "right"]].set_visible(False)
        fig.tight_layout(); fig.savefig(out / "baseline_vs_latest.png", dpi=150); plt.close(fig)


def summary(england, spread, latest, baseline, latest_rank, changes) -> str:
    label = "England" if not england.attrs.get("derived") else "The median area"
    first = england.index[0]
    lines = [
        "# Results",
        "",
        f"Source: DfT table BUS09, {spread['n'].max()} local authority areas, {england.index[0]} to {latest}. "
        "Measure: % of non-frequent bus services (fewer than six an hour) running on time.",
        "",
        "Years are DfT reporting years ending in March: 2019 means April 2018 to March 2019, the last full year "
        "before COVID-19. The 2021 peak reflects lockdown, when roads were empty and timetables were cut.",
        "",
        "## Headline",
        "",
        f"- {label}: **{england[latest]:.1f}%** of non-frequent services ran on time in {latest}, "
        f"compared with {england[first]:.1f}% in {first}"
        + (f" and {england[baseline]:.1f}% in {baseline} before the pandemic." if baseline in england else "."),
        f"- Best year: {england.idxmax()} ({england.max():.1f}%). Worst year: {england.idxmin()} ({england.min():.1f}%).",
        f"- In {latest} the most punctual 10% of areas ran at least {spread.loc[latest, 'p90']:.1f}% on time, "
        f"the least punctual 10% at most {spread.loc[latest, 'p10']:.1f}%: a gap of "
        f"{spread.loc[latest, 'p90'] - spread.loc[latest, 'p10']:.1f} points "
        f"(vs {spread.loc[first, 'p90'] - spread.loc[first, 'p10']:.1f} in {first}).",
    ]
    if not changes.empty:
        worse = (changes["change_pp"] < 0).mean()
        lines.append(f"- {worse:.0%} of areas with data for both years are less punctual in {latest} than in {baseline}.")
    lines += ["", f"## Least punctual areas, {latest}", "", "| Area | % on time |", "|---|---|"]
    lines += [f"| {a} | {v:.1f} |" for a, v in latest_rank.head(10).items()]
    lines += ["", f"## Most punctual areas, {latest}", "", "| Area | % on time |", "|---|---|"]
    lines += [f"| {a} | {v:.1f} |" for a, v in latest_rank.tail(10)[::-1].items()]
    if not changes.empty:
        lines += ["", f"## Biggest falls since {baseline}", "", "| Area | {} | {} | Change (pts) |".format(baseline, latest),
                  "|---|---|---|---|"]
        lines += [f"| {a} | {r.baseline:.1f} | {r.latest:.1f} | {r.change_pp:+.1f} |" for a, r in changes.head(10).iterrows()]
        lines += ["", f"## Biggest improvements since {baseline}", "", "| Area | {} | {} | Change (pts) |".format(baseline, latest),
                  "|---|---|---|---|"]
        lines += [f"| {a} | {r.baseline:.1f} | {r.latest:.1f} | {r.change_pp:+.1f} |" for a, r in changes.tail(10)[::-1].iterrows()]
    lines += ["", "![Trend](trend.png)", "", "![Best and worst](best_worst_latest.png)", "",
              "![Baseline vs latest](baseline_vs_latest.png)", ""]
    return "\n".join(lines)


def main() -> None:
    long = pd.read_csv(ROOT / "data" / "punctuality_long.csv", dtype={"year": str})
    out = ROOT / "results"
    out.mkdir(exist_ok=True)
    england, areas = split_national(long)
    spread = spread_by_year(areas)
    years = sorted(spread[spread["n"] >= 10].index)
    latest = years[-1]
    baseline = pick_baseline(years)
    england = england.reindex(years).dropna()
    spread = spread.loc[years]
    latest_rank = areas[areas["year"] == latest].groupby("area")["pct_on_time"].mean().sort_values()
    changes = area_changes(areas, baseline, latest) if baseline != latest else pd.DataFrame()
    changes.round(2).to_csv(out / "area_changes.csv")
    charts(england, spread, latest_rank, changes, out)
    (out / "summary.md").write_text(summary(england, spread, latest, baseline, latest_rank, changes), encoding="utf-8")
    print((out / "summary.md").read_text(encoding="utf-8").split("## Least")[0])


if __name__ == "__main__":
    main()
