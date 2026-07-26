"""Figure 1 — length-invariance. Judged accuracy when a question's evidence is
still inside the context window vs. truncated out of it. Flat lines (retrieval)
crossing a falling line (context-stuffing) is the paper's central figure.

Palette: Okabe-Ito CVD-safe (validated ΔE 37.2). Secondary encoding via distinct
markers + linestyles so it survives grayscale/print.
"""

import matplotlib.pyplot as plt
from matplotlib import rcParams

rcParams.update({
    "font.family": "serif",
    "font.size": 11,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.dpi": 150,
})

x = [0, 1]
xlabels = ["Evidence in window\n(recent)", "Evidence truncated\n(old)"]

# Numbers come from scripts/robustness_ci.py (single source of truth; it
# reconstructs the in-window/truncated split and bootstraps CIs).
series = [
    # label,           y_in,  y_out, color,     marker, linestyle, label_dy(pts)
    ("full-history",   0.702, 0.170, "#D55E00", "s", "--", 0),
    ("agentic (ours)", 0.330, 0.343, "#0072B2", "o", "-", -15),
    ("raw RAG",        0.306, 0.329, "#009E73", "^", ":", +15),
]

fig, ax = plt.subplots(figsize=(5.6, 3.6))
for label, y0, y1, c, mk, ls, dy in series:
    ax.plot(x, [y0, y1], color=c, marker=mk, linestyle=ls, linewidth=2,
            markersize=8, label=label, zorder=3, clip_on=False)
    # direct labels at the right end, nudged apart where lines coincide
    ax.annotate(label, xy=(1, y1), xytext=(10, dy), textcoords="offset points",
                va="center", ha="left", color=c, fontsize=10, fontweight="bold")

# annotate the collapse and the flat gap
ax.annotate("−76%", xy=(1, (0.702 + 0.170) / 2), xytext=(0.62, 0.47),
            color="#D55E00", fontsize=10, fontweight="bold")
ax.annotate("2.0× at the truncated end", xy=(1, 0.25), xytext=(0.05, 0.20),
            color="#333333", fontsize=9, style="italic")

ax.set_xticks(x)
ax.set_xticklabels(xlabels)
ax.set_ylabel("Judged accuracy")
ax.set_ylim(0.0, 0.75)
ax.set_xlim(-0.05, 1.0)
ax.set_title("Retrieval-based memory is length-invariant;\ncontext-stuffing collapses past its window",
             fontsize=11, loc="left")
ax.grid(axis="y", color="#e6e6e6", linewidth=0.8, zorder=0)
ax.margins(x=0.15)
fig.subplots_adjust(right=0.74, bottom=0.18, top=0.82, left=0.11)

fig.savefig("paper/figures/fig1_length_invariance.pdf")
fig.savefig("paper/figures/fig1_length_invariance.png", dpi=150)
print("wrote fig1_length_invariance.pdf / .png")
