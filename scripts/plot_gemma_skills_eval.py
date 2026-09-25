#!/usr/bin/env python3
"""Generates dark-mode evaluation plots color-coded by model generation."""

import os
import matplotlib.pyplot as plt
import numpy as np

data = [
    {"name": "Gemini 3.7 Flash", "gen": "Gemini", "base_pct": 77.1, "skill_pct": 100.0, "base_ast": 37, "skill_ast": 48},
    {"name": "Gemma 4 E4B-IT", "gen": "Gemma 4", "base_pct": 47.9, "skill_pct": 97.9, "base_ast": 23, "skill_ast": 47},
    {"name": "Gemma 3 27B-IT", "gen": "Gemma 3", "base_pct": 47.9, "skill_pct": 97.9, "base_ast": 23, "skill_ast": 47},
    {"name": "Gemini 3.8 Flash", "gen": "Gemini", "base_pct": 72.9, "skill_pct": 95.8, "base_ast": 35, "skill_ast": 46},
    {"name": "Gemma 2 27B-IT", "gen": "Gemma 2", "base_pct": 43.8, "skill_pct": 93.8, "base_ast": 21, "skill_ast": 45},
    {"name": "Gemma 3 12B-IT", "gen": "Gemma 3", "base_pct": 68.8, "skill_pct": 93.8, "base_ast": 33, "skill_ast": 45},
    {"name": "Gemma 3 4B-IT", "gen": "Gemma 3", "base_pct": 54.2, "skill_pct": 93.8, "base_ast": 26, "skill_ast": 45},
    {"name": "Gemini 2.5 Flash", "gen": "Gemini", "base_pct": 52.1, "skill_pct": 87.5, "base_ast": 25, "skill_ast": 42},
    {"name": "Gemma 2 9B-IT", "gen": "Gemma 2", "base_pct": 35.4, "skill_pct": 83.3, "base_ast": 17, "skill_ast": 40},
    {"name": "Gemma 2 2B-IT", "gen": "Gemma 2", "base_pct": 27.1, "skill_pct": 66.7, "base_ast": 13, "skill_ast": 32},
    {"name": "Gemma 3 1B-IT", "gen": "Gemma 3", "base_pct": 58.3, "skill_pct": 60.4, "base_ast": 28, "skill_ast": 29},
    {"name": "Gemma 4 E2B-IT", "gen": "Gemma 4", "base_pct": 10.4, "skill_pct": 41.7, "base_ast": 5, "skill_ast": 20},
]

# Reverse for horizontal chart top-to-bottom
data = data[::-1]

gen_colors = {
    "Gemma 2": "#4285F4",       # Blue
    "Gemma 3": "#34A853",       # Green
    "Gemma 4": "#FBBC04",       # Amber / Yellow
    "Gemini": "#EA4335",        # Coral / Red
}

plt.style.use("dark_background")
fig, ax = plt.subplots(figsize=(12, 7.5), facecolor="#141414")
ax.set_facecolor("#141414")

y_pos = np.arange(len(data))
bar_height = 0.45

# Draw baseline markers/bars in muted gray
for i, d in enumerate(data):
    # Baseline bar
    ax.barh(y_pos[i] + bar_height/2, d["base_pct"], height=bar_height*0.8, color="#404040", edgecolor="#666666", alpha=0.8, label="Baseline (Unassisted)" if i == 0 else "")
    # With-Skill bar
    color = gen_colors[d["gen"]]
    ax.barh(y_pos[i] - bar_height/2, d["skill_pct"], height=bar_height*0.8, color=color, edgecolor="none", alpha=0.95)

    # Annotate skill score
    ax.text(d["skill_pct"] + 1.2, y_pos[i] - bar_height/2, f"{d['skill_ast']}/48 ({d['skill_pct']:.1f}%)", va="center", ha="left", color="#FFFFFF", fontsize=9, fontweight="bold")
    # Annotate baseline score
    ax.text(d["base_pct"] + 1.2, y_pos[i] + bar_height/2, f"{d['base_ast']}/48", va="center", ha="left", color="#9E9E9E", fontsize=8)

ax.set_yticks(y_pos)
ax.set_yticklabels([d["name"] for d in data], fontsize=10, fontweight="medium", color="#E0E0E0")
ax.set_xlim(0, 115)
ax.set_xlabel("Assertion Accuracy (%) across 48 Evaluated Checks", fontsize=11, color="#CCCCCC", labelpad=10)
ax.set_title("Operational Assertion Performance: Baseline vs. With Domain Skill\nGrouped & Color-Coded by Model Generation", fontsize=13, fontweight="bold", color="#FFFFFF", pad=15)

# Styling grid lines
ax.xaxis.grid(True, linestyle="--", alpha=0.2, color="#FFFFFF")
ax.set_axisbelow(True)
for spine in ax.spines.values():
    spine.set_color("#333333")

# Custom Legend for Generations and Arms
from matplotlib.patches import Patch
legend_elements = [
    Patch(facecolor="#404040", edgecolor="#888888", label="Baseline (Unassisted Priors)"),
    Patch(facecolor=gen_colors["Gemma 2"], label="Gemma 2 Generation"),
    Patch(facecolor=gen_colors["Gemma 3"], label="Gemma 3 Generation"),
    Patch(facecolor=gen_colors["Gemma 4"], label="Gemma 4 MoE Generation"),
    Patch(facecolor=gen_colors["Gemini"], label="Gemini Managed Reference"),
]
ax.legend(handles=legend_elements, loc="lower right", framealpha=0.9, facecolor="#1E1E1E", edgecolor="#333333", fontsize=9)

plt.tight_layout()
os.makedirs("docs/blog/images", exist_ok=True)
output_png = "docs/blog/images/gemma_skills_performance_by_generation.png"
output_svg = "docs/blog/images/gemma_skills_performance_by_generation.svg"
plt.savefig(output_png, dpi=300, bbox_inches="tight")
plt.savefig(output_svg, bbox_inches="tight")
print(f"Generated {output_png} and {output_svg}")
