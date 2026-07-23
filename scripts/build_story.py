#!/usr/bin/env python3
"""Regenerate data story markdown, HTML preview, and aggregates.json from audit CSVs."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from charts import generate_all_charts  # noqa: E402
from enrich import compute_aggregates  # noqa: E402
from load_csv import load_csv  # noqa: E402

try:
    from jinja2 import Environment, FileSystemLoader, select_autoescape
except ImportError:
    print("Install dependencies: pip install -r requirements.txt", file=sys.stderr)
    sys.exit(1)

DATA_DIR = ROOT / "data"
TEMPLATE_DIR = ROOT / "templates"
OUTPUT_DIR = ROOT / "output"


def svg_bar_chart(
    labels: list[str],
    values: list[int],
    *,
    title: str,
    y_label: str,
    bar_color: str = "#c45c26",
    second_values: list[int] | None = None,
    second_color: str = "#666",
    second_label: str = "",
) -> str:
    if not labels:
        return f'<svg class="chart-svg" viewBox="0 0 400 120"><text x="8" y="24">{title} — no data</text></svg>'

    w, h, pad = 640, 220, 48
    n = len(labels)
    gap = 4
    bar_w = max(8, (w - 2 * pad - gap * (n - 1)) / n)
    max_v = max(max(values), max(second_values or [0]), 1)
    chart_h = h - pad - 36

    bars = []
    for i, (lab, val) in enumerate(zip(labels, values)):
        x = pad + i * (bar_w + gap)
        bh = (val / max_v) * chart_h
        y = pad + chart_h - bh
        bars.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" fill="{bar_color}"/>'
        )
        if second_values is not None and i < len(second_values):
            val2 = second_values[i]
            bh2 = (val2 / max_v) * chart_h
            y2 = pad + chart_h - bh2
            x2 = x + bar_w * 0.15
            w2 = bar_w * 0.7
            bars.append(
                f'<rect x="{x2:.1f}" y="{y2:.1f}" width="{w2:.1f}" height="{bh2:.1f}" fill="{second_color}" opacity="0.85"/>'
            )
        short = lab.replace("20", "’") if lab.startswith("20") else lab
        if len(short) > 8:
            short = short[-5:]
        bars.append(
            f'<text x="{x + bar_w/2:.1f}" y="{h - 8}" text-anchor="middle" font-size="9" font-family="system-ui,sans-serif" fill="#555">{short}</text>'
        )

    legend = ""
    if second_values is not None:
        legend = (
            f'<rect x="{pad}" y="12" width="10" height="10" fill="{bar_color}"/>'
            f'<text x="{pad+14}" y="21" font-size="10" font-family="system-ui,sans-serif">Audits</text>'
            f'<rect x="{pad+70}" y="12" width="10" height="10" fill="{second_color}"/>'
            f'<text x="{pad+84}" y="21" font-size="10" font-family="system-ui,sans-serif">{second_label or "Unique domains"}</text>'
        )

    return (
        f'<svg class="chart-svg" viewBox="0 0 {w} {h}" role="img" aria-label="{title}">'
        f'<text x="{pad}" y="28" font-size="13" font-weight="600" font-family="system-ui,sans-serif">{title}</text>'
        f"{legend}"
        f'<line x1="{pad}" y1="{pad + chart_h}" x2="{w - pad}" y2="{pad + chart_h}" stroke="#ccc"/>'
        f'<text x="8" y="{pad + chart_h/2}" font-size="10" font-family="system-ui,sans-serif" fill="#888" transform="rotate(-90 12 {pad + chart_h/2})">{y_label}</text>'
        + "".join(bars)
        + "</svg>"
    )


def svg_horizontal_bars(items: list[tuple[str, int]], title: str) -> str:
    if not items:
        return f'<svg class="chart-svg" viewBox="0 0 400 80"><text x="8" y="24">{title}</text></svg>'
    w, h = 640, 40 + len(items) * 28
    pad = 160
    max_v = max(v for _, v in items) or 1
    inner_w = w - pad - 24
    parts = [
        f'<svg class="chart-svg" viewBox="0 0 {w} {h}" role="img" aria-label="{title}">',
        f'<text x="16" y="22" font-size="13" font-weight="600" font-family="system-ui,sans-serif">{title}</text>',
    ]
    for i, (lab, val) in enumerate(items):
        y = 36 + i * 28
        bw = (val / max_v) * inner_w
        display = lab.replace("_", " ")
        parts.append(f'<text x="16" y="{y + 14}" font-size="11" font-family="system-ui,sans-serif">{display[:22]}</text>')
        parts.append(f'<rect x="{pad}" y="{y}" width="{bw:.1f}" height="18" fill="#c45c26"/>')
        parts.append(f'<text x="{pad + bw + 6}" y="{y + 14}" font-size="11" font-family="system-ui,sans-serif">{val}</text>')
    parts.append("</svg>")
    return "".join(parts)


def label_map_org(key: str) -> str:
    return {
        "commercial": "Commercial",
        "public_agency": "Public agency",
        "education": "Education",
        "nonprofit_org": "Nonprofit (.org)",
    }.get(key, key)


def label_map_size(key: str) -> str:
    return {
        "likely_smb": "Likely SMB",
        "enterprise_known": "Known enterprise",
        "agency_edu_nonprofit": "Agency / edu / nonprofit",
        "unknown": "Unknown",
    }.get(key, key.replace("_", " "))


def main() -> None:
    leads_path = DATA_DIR / "audit_leads.csv"
    reqs_path = DATA_DIR / "audit_requests.csv"
    if not leads_path.exists() or not reqs_path.exists():
        print(f"Missing CSVs in {DATA_DIR}. Copy exports to audit_leads.csv and audit_requests.csv.", file=sys.stderr)
        sys.exit(1)

    leads = load_csv(leads_path)
    requests = load_csv(reqs_path)
    agg = compute_aggregates(leads, requests)

    wr = agg["weekly_requests"]
    chart_weekly_requests = svg_bar_chart(
        [r["week"] for r in wr],
        [r["audits"] for r in wr],
        title="Weekly audit runs",
        y_label="Count",
        second_values=[r["unique_domains"] for r in wr],
        second_label="Unique domains",
    )
    wl = agg["weekly_leads"]
    chart_weekly_leads = svg_bar_chart(
        [r["week"] for r in wl],
        [r["leads"] for r in wl],
        title="Weekly email leads",
        y_label="Count",
    )

    org_items = [(label_map_org(k), v) for k, v in sorted(agg["org_type_unique_domains"].items(), key=lambda x: -x[1])]
    chart_org_type = svg_horizontal_bars(org_items, "Org type (unique domains)")

    size_items = [(label_map_size(k), v) for k, v in sorted(agg["size_proxy_unique_domains"].items(), key=lambda x: -x[1])]
    chart_size_proxy = svg_horizontal_bars(size_items, "Size proxy (unique domains)")

    sector_items = list(agg["sector_unique_domains"].items())[:10]
    chart_sectors = svg_horizontal_bars(sector_items, "Sectors (unique domains)")

    user_leads = agg["volume"]["user_lead_rows"] or 1
    pct_free = round(100 * agg["volume"]["free_email_user_leads"] / user_leads)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    chart_files = generate_all_charts(
        agg,
        org_items=org_items,
        size_items=size_items,
        sector_items=sector_items,
        out_dir=OUTPUT_DIR,
    )

    context = {
        "meta": agg["meta"],
        "volume": agg["volume"],
        "spike": agg["spike"],
        "methodology": agg["methodology"],
        "anonymized_examples": agg["anonymized_examples"],
        "public_agency_note": agg["public_agency_note"],
        "pct_free_email": pct_free,
        "weekly_requests": agg["weekly_requests"],
        "weekly_leads": agg["weekly_leads"],
        "org_type_rows": org_items,
        "size_proxy_rows": size_items,
        "sector_rows": sector_items,
        "charts": chart_files,
    }

    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html", "xml"]),
    )

    md = env.get_template("story.md.j2").render(**context)
    html = env.get_template("story.html.j2").render(
        **context,
        chart_weekly_requests=chart_weekly_requests,
        chart_weekly_leads=chart_weekly_leads,
        chart_org_type=chart_org_type,
        chart_size_proxy=chart_size_proxy,
        chart_sectors=chart_sectors,
    )

    md_path = OUTPUT_DIR / "data_story.md"
    html_path = OUTPUT_DIR / "liz_data_story.html"
    json_path = OUTPUT_DIR / "aggregates.json"
    md_path.write_text(md, encoding="utf-8")
    html_path.write_text(html, encoding="utf-8")
    json_path.write_text(json.dumps(agg, indent=2), encoding="utf-8")

    print(f"Wrote {md_path}")
    print(f"Wrote charts in {OUTPUT_DIR / 'charts'}")
    print(f"Wrote {html_path} (local preview, gitignored)")
    print(f"Wrote {json_path}")
    print(
        f"Sanity: {len(leads)} leads, {len(requests)} requests, "
        f"{agg['volume']['unique_domains_audited']} unique domains, "
        f"spike 14d requests {agg['spike']['requests_last_14d']} vs prior {agg['spike']['requests_prior_14d']}"
    )


if __name__ == "__main__":
    main()
