"""Figure 2 — the per-turn pipeline: recall -> generate -> (async) extract, with
the vector store. The async extraction path is highlighted to show it never
blocks the reply. Same palette/typography as Figure 1."""

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib import rcParams

rcParams.update({"font.family": "serif", "font.size": 10})

BLUE, ORANGE, GREEN, INK, MUTE = "#0072B2", "#D55E00", "#009E73", "#222222", "#666666"

fig, ax = plt.subplots(figsize=(7.2, 3.4))
ax.set_xlim(0, 12); ax.set_ylim(0, 6); ax.axis("off")


def box(x, y, w, h, text, edge, face="#ffffff", tcolor=INK, bold=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.08,rounding_size=0.12",
                                linewidth=1.6, edgecolor=edge, facecolor=face, zorder=2))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", color=tcolor,
            fontsize=9.5, fontweight="bold" if bold else "normal", zorder=3)


def arrow(x0, y0, x1, y1, color=INK, style="-|>", ls="-", lw=1.6):
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle=style, mutation_scale=14,
                                 lw=lw, color=color, linestyle=ls, zorder=1,
                                 shrinkA=2, shrinkB=2))


# top row: the interactive path (never blocked)
box(0.2, 3.6, 2.1, 1.2, "User\nmessage", MUTE)
box(2.9, 3.6, 2.4, 1.2, "1. Recall\n(embed query,\nage-aware top-k)", BLUE, bold=True)
box(5.9, 3.6, 2.4, 1.2, "2. Generate\n(stream reply)", BLUE, bold=True)
box(9.0, 3.6, 2.6, 1.2, "Reply to user\n(TTFT ~0.9s)", GREEN, bold=True)
arrow(2.3, 4.2, 2.9, 4.2)
arrow(5.3, 4.2, 5.9, 4.2)
arrow(8.3, 4.2, 9.0, 4.2, color=GREEN)

# vector store (left half, under User+Recall) and Extract (right, under Generate)
box(0.2, 1.3, 5.1, 1.0, "Typed vector store\n(FACT · EVENT · SELF, dated, deduplicated)", INK, face="#f5f5f3")
box(5.9, 1.3, 2.4, 1.0, "3. Extract\n(background)", ORANGE, bold=True)

arrow(3.5, 2.3, 3.5, 3.6, color=BLUE, ls="-")             # store -> recall (read, up)
arrow(7.1, 3.6, 7.1, 2.3, color=ORANGE, ls="--")          # generate -> extract (after reply)
arrow(5.9, 1.8, 5.3, 1.8, color=ORANGE, ls="--")          # extract -> store (write, left)
ax.text(3.7, 3.0, "read", color=BLUE, fontsize=8, va="center")
ax.text(7.3, 3.0, "after reply\n(async)", color=ORANGE, fontsize=8, style="italic", va="center")
ax.text(5.35, 2.05, "write", color=ORANGE, fontsize=8, ha="center")

ax.text(0.2, 5.5, "The reply never waits on extraction: recall + generation are the only interactive steps.",
        color=MUTE, fontsize=9, style="italic")

fig.subplots_adjust(left=0.01, right=0.99, top=0.98, bottom=0.02)
fig.savefig("paper/figures/fig2_architecture.pdf")
fig.savefig("paper/figures/fig2_architecture.png", dpi=150)
print("wrote fig2_architecture.pdf / .png")
