"""Build the report charts from reports/evaluation/*.json and reports/tuning_dev.md."""

from __future__ import annotations

import json
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
SURFACE, INK, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
BLUE, ORANGE = "#2a78d6", "#eb6834"

plt.rcParams.update({
    "font.family": "Helvetica", "font.size": 9, "axes.edgecolor": GRID, "text.color": INK,
    "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": INK, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
})


def systems_chart() -> None:
    data = json.loads((ROOT / "reports/evaluation/test.json").read_text())
    rows = [
        ("Keyword baseline", data["baseline_bm25"]),
        ("Dense top hit", data["baseline_dense"]),
        ("LinkMate", data["answers"]["score"]),
        ("LinkMate, strong only", data["strong_only"]),
    ]
    metrics = [("Right contact found", "hit_rate"), ("Correct refusals", "refusal_rate"), ("Recommendations that fit", "precision")]
    figure, axes = plt.subplots(1, 3, figsize=(7.0, 1.75), sharey=True)
    names = [name for name, _ in rows][::-1]
    for axis, (title, key) in zip(axes, metrics):
        values = [score[key] * 100 for _, score in rows][::-1]
        bars = axis.barh(names, values, color=BLUE, height=0.55)
        for bar, value in zip(bars, values):
            axis.text(value + 2, bar.get_y() + bar.get_height() / 2, f"{value:.0f}%", va="center", fontsize=8.5, color=INK)
        axis.set_title(title, fontsize=9, loc="left", color=INK, fontweight="bold")
        axis.set_xlim(0, 118)
        axis.xaxis.set_visible(False)
        axis.tick_params(axis="y", length=0)
        for side in ("top", "right", "bottom"):
            axis.spines[side].set_visible(False)
    figure.tight_layout(pad=0.4)
    figure.savefig(OUT / "results_test.pdf")
    figure.savefig(OUT / "results_test.png", dpi=220)


def threshold_chart() -> None:
    text = (ROOT / "reports/tuning_dev.md").read_text()
    rows = re.findall(r"\| (0\.\d+) \| (\d+)/(\d+) \| (\d+)/(\d+) \| \d+/\d+ \| [\d.]+ \|", text)
    x = [float(r[0]) for r in rows]
    hits = [int(r[1]) / int(r[2]) * 100 for r in rows]
    refusals = [int(r[3]) / int(r[4]) * 100 for r in rows]
    figure, axis = plt.subplots(figsize=(3.4, 1.9))
    axis.plot(x, hits, color=BLUE, linewidth=2, marker="o", markersize=4)
    axis.plot(x, refusals, color=ORANGE, linewidth=2, marker="o", markersize=4)
    axis.text(x[-1] + 0.004, hits[-1], "Right contact", color=INK, va="center", fontsize=8.5)
    axis.text(x[-1] + 0.004, refusals[-1], "Correct refusal", color=INK, va="center", fontsize=8.5)
    axis.axvline(0.59, color=MUTED, linewidth=1, linestyle=":")
    axis.text(0.592, 6, "chosen", color=MUTED, fontsize=8)
    axis.set_xlim(0.49, 0.76)
    axis.set_ylim(0, 105)
    axis.set_xlabel("Search threshold, development questions")
    axis.set_ylabel("%")
    axis.grid(axis="y", color=GRID, linewidth=0.7)
    axis.tick_params(length=0, colors=MUTED)
    for side in ("top", "right"):
        axis.spines[side].set_visible(False)
    figure.tight_layout(pad=0.4)
    figure.savefig(OUT / "threshold_dev.pdf")
    figure.savefig(OUT / "threshold_dev.png", dpi=220)


if __name__ == "__main__":
    threshold_chart()
    systems_chart()
