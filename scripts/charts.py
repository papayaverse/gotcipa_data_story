"""Generate seaborn chart PNGs for the markdown data story."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

ACCENT = "#c45c26"
SLATE = "#4a4a4a"
MUTED = "#888888"
BG = "#ffffff"


def apply_theme() -> None:
    sns.set_theme(
        style="whitegrid",
        context="notebook",
        font_scale=1.05,
        rc={
            "figure.facecolor": BG,
            "axes.facecolor": BG,
            "axes.edgecolor": "#dddddd",
            "axes.labelcolor": SLATE,
            "text.color": SLATE,
            "xtick.color": SLATE,
            "ytick.color": SLATE,
            "grid.color": "#eeeeee",
            "grid.linewidth": 0.8,
            "font.family": "sans-serif",
            "font.sans-serif": ["Helvetica Neue", "Arial", "DejaVu Sans"],
        },
    )


def _save(fig: plt.Figure, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=160, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    return path.name


def _short_week(week: str) -> str:
    # 2026-W29 -> W29
    if "-W" in week:
        return week.split("-W", 1)[1]
    return week


def chart_weekly_requests(weekly: list[dict], out_dir: Path) -> str:
    apply_theme()
    df = pd.DataFrame(weekly)
    df["week_label"] = df["week"].map(_short_week)

    fig, ax = plt.subplots(figsize=(10, 4.5))
    x = range(len(df))
    width = 0.38
    ax.bar(
        [i - width / 2 for i in x],
        df["audits"],
        width=width,
        label="Audit runs",
        color=ACCENT,
        edgecolor="white",
        linewidth=0.6,
    )
    ax.bar(
        [i + width / 2 for i in x],
        df["unique_domains"],
        width=width,
        label="Unique domains",
        color=SLATE,
        alpha=0.75,
        edgecolor="white",
        linewidth=0.6,
    )
    ax.set_xticks(list(x))
    ax.set_xticklabels(df["week_label"], rotation=0)
    ax.set_xlabel("ISO week")
    ax.set_ylabel("Count")
    ax.set_title("Weekly audit activity", loc="left", fontweight="600", pad=12)
    ax.legend(frameon=False, loc="upper left")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    sns.despine(left=False, bottom=False)
    return _save(fig, out_dir / "weekly_requests.png")


def chart_weekly_leads(weekly: list[dict], out_dir: Path) -> str:
    apply_theme()
    df = pd.DataFrame(weekly)
    df["week_label"] = df["week"].map(_short_week)

    fig, ax = plt.subplots(figsize=(10, 4))
    sns.barplot(
        data=df,
        x="week_label",
        y="leads",
        color=ACCENT,
        edgecolor="white",
        linewidth=0.6,
        ax=ax,
    )
    ax.set_xlabel("ISO week")
    ax.set_ylabel("Lead captures")
    ax.set_title("Weekly email leads", loc="left", fontweight="600", pad=12)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    return _save(fig, out_dir / "weekly_leads.png")


def chart_horizontal_bars(
    items: list[tuple[str, int]],
    *,
    title: str,
    xlabel: str,
    filename: str,
    out_dir: Path,
    color: str = ACCENT,
) -> str:
    apply_theme()
    if not items:
        fig, ax = plt.subplots(figsize=(8, 2))
        ax.text(0.5, 0.5, "No data", ha="center", va="center")
        ax.axis("off")
        return _save(fig, out_dir / filename)

    labels = [lab for lab, _ in items]
    values = [val for _, val in items]
    df = pd.DataFrame({"label": labels, "count": values})
    df = df.sort_values("count", ascending=True)

    height = max(3.2, 0.45 * len(df) + 1.2)
    fig, ax = plt.subplots(figsize=(9, height))
    sns.barplot(
        data=df,
        y="label",
        x="count",
        color=color,
        edgecolor="white",
        linewidth=0.6,
        ax=ax,
    )
    ax.set_xlabel(xlabel)
    ax.set_ylabel("")
    ax.set_title(title, loc="left", fontweight="600", pad=12)
    for container in ax.containers:
        ax.bar_label(container, padding=4, fontsize=9, color=SLATE)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    return _save(fig, out_dir / filename)


def generate_all_charts(
    agg: dict,
    *,
    org_items: list[tuple[str, int]],
    size_items: list[tuple[str, int]],
    sector_items: list[tuple[str, int]],
    out_dir: Path,
) -> dict[str, str]:
    """Return chart filename map for markdown embedding."""
    charts_dir = out_dir / "charts"
    return {
        "weekly_requests": chart_weekly_requests(agg["weekly_requests"], charts_dir),
        "weekly_leads": chart_weekly_leads(agg["weekly_leads"], charts_dir),
        "org_type": chart_horizontal_bars(
            org_items,
            title="Org type (unique domains, inferred)",
            xlabel="Unique domains",
            filename="org_type.png",
            out_dir=charts_dir,
        ),
        "size_proxy": chart_horizontal_bars(
            size_items,
            title="Size proxy (unique domains, inferred)",
            xlabel="Unique domains",
            filename="size_proxy.png",
            out_dir=charts_dir,
            color=SLATE,
        ),
        "sectors": chart_horizontal_bars(
            sector_items,
            title="Sectors (audit runs, inferred)",
            xlabel="Audit runs",
            filename="sectors.png",
            out_dir=charts_dir,
            color="#6b5b4a",
        ),
    }
