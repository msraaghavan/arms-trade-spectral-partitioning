"""
Generates every matplotlib figure used in the case-study report.
Run AFTER build_graph.py.   ->  figures/fig01_*.png ... fig09_*.png

Figures are drawn on a white background (they get printed) but use the same
cluster palette as the 3D globe so the report and the website match.
"""

import json
import os
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np

import build_graph as bg
from country_coords import COORDS

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FIG = os.path.join(ROOT, "figures")
os.makedirs(FIG, exist_ok=True)
STATS = {}   # a few numbers the report quotes about the figures -> figures/fig_stats.json

PAL = ["#e02a4d", "#0e9ec4", "#6aa300", "#8b5cf6"]
GREY = "#9aa7b2"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9,
    "axes.edgecolor": "#c9d3db", "axes.labelcolor": "#33414d",
    "xtick.color": "#5b6b78", "ytick.color": "#5b6b78",
    "axes.titlesize": 11, "axes.titleweight": "bold",
    "figure.facecolor": "white", "savefig.facecolor": "white",
})


def save(fig, name):
    path = os.path.join(FIG, name)
    fig.savefig(path, dpi=165, bbox_inches="tight")
    plt.close(fig)
    print("  wrote", name)
    return path


# --------------------------------------------------------------------------
print("loading data.json ...")
D = json.load(open(os.path.join(ROOT, "web", "data.json"), encoding="utf-8"))
YEARS = D["meta"]["years"]

print("rebuilding graphs for the structural figures ...")
transfers, _ = bg.load_transfers()
by_year = defaultdict(lambda: defaultdict(float))
for s, r, y, v in transfers:
    by_year[y][(s, r)] += v


def graph_for(year):
    edges = bg.snapshot_edges(by_year, year)
    _, UG, nodes = bg.build_graphs(edges)
    W = nx.to_numpy_array(UG, nodelist=nodes, weight="lw")
    return UG, nodes, W, edges


# ==========================================================================
# FIG 1 -- the spectral gap, real vs random
# ==========================================================================
def fig01():
    fig, axes = plt.subplots(1, 2, figsize=(9.4, 3.5))
    for ax, yr in zip(axes, [1987, 2025]):
        f = D["frames"][str(yr)]
        eig = f["eig"][:12]
        reig = f["random"]["eig"][:12]
        x = np.arange(1, len(eig) + 1)

        ax.plot(x, eig, "o-", color="#0e9ec4", lw=1.8, ms=4.5, label="real network", zorder=3)
        ax.plot(x, reig, "s--", color="#e02a4d", lw=1.3, ms=3.2, alpha=.85,
                label="shuffled copy", zorder=2)
        # lambda_1 is 0 for every connected graph (real or shuffled), so the first
        # step says nothing -- grey it out so the eye goes to the lambda_2 -> lambda_3 gap
        ax.axvspan(.6, 1.5, color="#e5e7eb", alpha=.7, zorder=0)
        ax.text(1.05, max(eig) * .97, "$\\lambda_1$ = 0\nalways\n(ignored)", fontsize=7,
                color="#5b6b78", ha="center", va="top")

        # annotate the big jump after lambda_2
        ax.annotate("", xy=(2, eig[1]), xytext=(3, eig[2]),
                    arrowprops=dict(arrowstyle="<->", color="#111", lw=1.4))
        ax.text(3.15, eig[1] - .03, f"eigengap\n= {eig[2]-eig[1]:.3f}",
                fontsize=8.5, fontweight="bold", va="center", ha="left")
        ax.axvline(2.5, color="#111", ls=":", lw=1)
        ax.set_title(f"{yr}   (window {yr-9}-{yr})")
        ax.set_xlabel("eigenvalue number  i  (sorted, smallest first)")
        ax.set_xticks(x)
        ax.set_ylabel("$\\lambda_i$ of normalised Laplacian")
        ax.legend(frameon=False, fontsize=8, loc="lower right")
        ax.grid(alpha=.25, ls=":")
    fig.suptitle("Sorted Laplacian eigenvalues: the gap after $\\lambda_2$ "
                 "is why k = 2", y=1.03, fontsize=11, fontweight="bold")
    return save(fig, "fig01_spectral_gap.png")


# ==========================================================================
# FIG 2 -- adjacency matrix before and after reordering by bloc
# ==========================================================================
def fig02(year=1987):
    """
    Three panels, one story:
      (a) the real matrix in alphabetical order          -> looks like noise
      (b) the SAME matrix reordered by the partition     -> two dense blocks
      (c) the RANDOM twin, reordered the exact same way  -> still no blocks
    Panel (c) is the control: it proves the blocks in (b) come from the data,
    not from the act of reordering.
    """
    UG, nodes, W, _ = graph_for(year)

    def reorder(mat, key):
        lab, _, _ = bg.spectral_partition(mat, 2)
        # share of the links that run BETWEEN the two groups (the off-diagonal corners)
        iu = np.triu_indices_from(mat, 1)
        on = mat[iu] > 0
        STATS[key] = {"n": int(len(mat)), "links": int(on.sum()),
                      "cross_pct": round(100 * float((lab[iu[0]] != lab[iu[1]])[on].mean()), 1)}
        d = mat.sum(axis=1)
        order = np.lexsort((-d, lab))
        split = int((lab[order] == lab[order][0]).sum())
        return (mat > 0).astype(float)[np.ix_(order, order)], split

    R = bg.random_twin(UG, bg.SEED)
    RW = nx.to_numpy_array(R, nodelist=list(R.nodes()), weight="lw")
    alpha = np.argsort(np.array(nodes))
    alpha_ord = (W > 0).astype(float)[np.ix_(alpha, alpha)]
    real_ord, split_r = reorder(W, "fig02_real")
    rand_ord, split_x = reorder(RW, "fig02_shuffled")

    fig, axes = plt.subplots(1, 3, figsize=(11.4, 4.1))
    panels = [
        (alpha_ord, None,
         "(a) REAL data, alphabetical order\nlooks like random dots"),
        (real_ord, split_r,
         "(b) SAME real data, sorted by group\ncorners (links between groups) almost empty"),
        (rand_ord, split_x,
         "(c) SHUFFLED copy, sorted the same way\ncorners stay full - this is the control"),
    ]
    for ax, (mat, split, title) in zip(axes, panels):
        ax.imshow(mat, cmap="binary", interpolation="nearest", aspect="equal")
        ax.set_title(title, fontsize=9)
        ax.set_xticks([]); ax.set_yticks([])
        if split is not None:
            ax.axhline(split - .5, color="#e02a4d", lw=1.6)
            ax.axvline(split - .5, color="#e02a4d", lw=1.6)
    fig.suptitle(f"Same {year} data every time - only the row and column order changes",
                 y=1.02, fontsize=10.5, fontweight="bold")
    return save(fig, "fig02_adjacency_blocks.png")


# ==========================================================================
# FIG 10 -- readable graph diagram for the Graph Modeling section
# ==========================================================================
def fig10(year=1987, topn=24):
    """A small, clearly labelled subgraph -- 153 nodes is unreadable on paper."""
    UG, nodes, W, edges = graph_for(year)
    # colour by the SAME k=2 labels the report and website use (0 = Soviet side)
    cl = {n["id"]: n["c2"] for n in D["frames"][str(year)]["nodes"]}
    assert cl["Soviet Union"] == 0 and cl["United States"] == 1

    strength = {n: UG.degree(n, weight="weight") for n in nodes}
    keep = sorted(nodes, key=lambda n: -strength[n])[:topn]
    S = UG.subgraph(keep).copy()

    # keep only the visually meaningful edges
    ew = sorted((d["weight"] for _, _, d in S.edges(data=True)), reverse=True)
    cutoff = ew[min(len(ew) - 1, 55)]
    S.remove_edges_from([(u, v) for u, v, d in S.edges(data=True) if d["weight"] < cutoff])
    S.remove_nodes_from([n for n in list(S.nodes()) if S.degree(n) == 0])
    STATS["fig10"] = {"n_full": len(nodes), "nodes": S.number_of_nodes(),
                      "edges": S.number_of_edges()}

    pos = nx.spring_layout(S, weight="lw", seed=3, k=1.35, iterations=350)
    fig, ax = plt.subplots(figsize=(8.6, 6.2))

    wmax = max(d["weight"] for _, _, d in S.edges(data=True))
    for u, v, d in S.edges(data=True):
        ax.plot([pos[u][0], pos[v][0]], [pos[u][1], pos[v][1]],
                color="#e02a4d" if cl[u] == cl[v] == 0 else
                      "#0e9ec4" if cl[u] == cl[v] == 1 else "#94a3b8",
                lw=.5 + 3.4 * (d["weight"] / wmax) ** .55,
                alpha=.55, zorder=1, solid_capstyle="round")

    smax = max(strength[n] for n in S.nodes())
    for n in S.nodes():
        r = 150 + 1150 * (strength[n] / smax) ** .75
        ax.scatter(*pos[n], s=r, c=PAL[cl[n]], alpha=.92, linewidths=1.2,
                   edgecolors="white", zorder=2)
    # labels go BELOW the node, not inside it -- country names are too long to fit
    for n in S.nodes():
        off = 0.055 + 0.030 * (strength[n] / smax) ** .75
        ax.annotate(n, (pos[n][0], pos[n][1] - off), fontsize=6.9, fontweight="bold",
                    ha="center", va="top", color="#1f2937", zorder=4,
                    bbox=dict(fc="white", ec="none", alpha=.78, pad=.7))

    ax.axis("off")
    ax.margins(0.13)
    ax.set_title(f"Graph model, top {S.number_of_nodes()} countries by trade "
                 f"volume ({year-9}-{year})\n"
                 "Vertex = country  |  Edge = arms transfer  |  Edge thickness = volume (TIV)  |  "
                 "Colour = detected bloc", fontsize=9.8, fontweight="bold")
    red = plt.Line2D([], [], marker="o", ls="", color=PAL[0], label="Soviet-aligned bloc")
    blue = plt.Line2D([], [], marker="o", ls="", color=PAL[1], label="US/Western-aligned bloc")
    ax.legend(handles=[red, blue], frameon=False, fontsize=8.5, ncol=2,
              loc="upper center", bbox_to_anchor=(.5, -.01))
    return save(fig, "fig10_graph_model.png")


# ==========================================================================
# FIG 4 -- how strongly the real network beats random, across time
# ==========================================================================
def fig04():
    z2 = [D["frames"][str(y)]["random"]["z"]["2"] for y in YEARS]
    z4 = [D["frames"][str(y)]["random"]["z"]["4"] for y in YEARS]
    fig, ax = plt.subplots(figsize=(9.4, 3.3))
    ax.fill_between(YEARS, 0, z2, color="#0e9ec4", alpha=.20)
    ax.plot(YEARS, z2, color="#0e9ec4", lw=2.1, label="k = 2  (eigengap-optimal)")
    ax.plot(YEARS, z4, color="#8b5cf6", lw=1.4, ls="--", label="k = 4  (refined)")
    ax.axhline(0, color="#33414d", lw=1)
    ax.axhline(2, color="#e02a4d", lw=1, ls=":")
    ax.text(YEARS[1], 2.6, "significance threshold (2$\\sigma$)", color="#e02a4d", fontsize=7.5)
    ax.axvline(1991, color=GREY, lw=1, ls="--")
    ax.text(1991.6, max(z2) * .88, "USSR dissolved", fontsize=7.5, color="#5b6b78")
    ax.set_xlabel("year (end of 10-year window)")
    ax.set_ylabel("z-score of spectral gap\nvs 10 random twins")
    ax.set_title("How many standard deviations the real network's spectral gap "
                 "beats random wiring", fontsize=10.5)
    ax.legend(frameon=False, fontsize=8)
    ax.grid(alpha=.25, ls=":")
    return save(fig, "fig04_zscore_time.png")


# ==========================================================================
# FIG 5 -- bloc loyalty (persistence) over time, real vs random
# ==========================================================================
def fig05():
    pr, rr, ys = [], [], []
    for y in YEARS:
        s = D["frames"][str(y)]["stats"]
        r = D["frames"][str(y)]["random"]
        if s["persist"] is None or r.get("persist") is None:
            continue
        ys.append(y); pr.append(s["persist"] * 100); rr.append(r["persist"] * 100)
    fig, ax = plt.subplots(figsize=(9.4, 3.3))
    ax.plot(ys, pr, color="#0e9ec4", lw=2.1, label="real network")
    ax.plot(ys, rr, color="#e02a4d", lw=1.5, ls="--", label="random twin")
    ax.axhline(25, color=GREY, lw=1, ls=":")
    ax.text(ys[1], 27, "pure chance = 1/k = 25%", fontsize=7.5, color="#5b6b78")
    ax.fill_between(ys, rr, pr, color="#0e9ec4", alpha=.13)
    ax.axvline(1991, color=GREY, lw=1, ls="--")
    ax.text(1991.6, 96, "USSR dissolved", fontsize=7.5, color="#5b6b78")
    ax.set_ylim(0, 105)
    ax.set_xlabel("year"); ax.set_ylabel("% of countries staying\nin the same bloc next year")
    ax.set_title("Bloc loyalty: real alliances persist, random groupings do not",
                 fontsize=10.5)
    ax.legend(frameon=False, fontsize=8, loc="center left")
    ax.grid(alpha=.25, ls=":")
    return save(fig, "fig05_persistence.png")


# ==========================================================================
# FIG 6 -- size of each bloc over time (k = 2)
# ==========================================================================
def fig06():
    a, b, ys = [], [], []
    for y in YEARS:
        nd = D["frames"][str(y)]["nodes"]
        ys.append(y)
        a.append(sum(1 for n in nd if n["c2"] == 0))
        b.append(sum(1 for n in nd if n["c2"] == 1))
    fig, ax = plt.subplots(figsize=(9.4, 3.3))
    ax.stackplot(ys, a, b, colors=[PAL[0], PAL[1]], alpha=.85,
                 labels=["Soviet / Russia-aligned bloc", "US / Western-aligned bloc"])
    ax.axvline(1991, color="white", lw=1.6, ls="--")
    ax.text(1991.8, 12, "USSR dissolved", fontsize=7.5, color="white", fontweight="bold")
    ax.set_xlim(min(ys), max(ys))
    ax.set_xlabel("year"); ax.set_ylabel("number of countries")
    ax.set_title("Membership of the two detected blocs, 1959-2025", fontsize=10.5)
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    return save(fig, "fig06_bloc_sizes.png")


# ==========================================================================
# FIG 7 -- bridge nations (betweenness) for a chosen year
# ==========================================================================
def fig07(year=2025):
    nd = D["frames"][str(year)]["nodes"]
    top = sorted(nd, key=lambda n: -n["bt"])[:14][::-1]
    fig, ax = plt.subplots(figsize=(7.2, 4.3))
    cols = ["#f4a300" if n["br"] else "#0e9ec4" for n in top]
    ax.barh([n["id"] for n in top], [n["bt"] for n in top], color=cols, height=.68)
    for n, y in zip(top, range(len(top))):
        ax.text(n["bt"] + .002, y, f"{int(n['cr']*100)}% cross-bloc",
                va="center", fontsize=7.2, color="#5b6b78")
    ax.set_xlabel("weighted betweenness centrality")
    ax.set_title(f"Bridge nations, {year-9}-{year}\n"
                 "(orange = flagged as a bridge: high betweenness AND >35% cross-bloc trade)",
                 fontsize=10)
    ax.grid(axis="x", alpha=.25, ls=":")
    ax.set_xlim(0, max(n["bt"] for n in top) * 1.33)
    return save(fig, "fig07_bridges.png")


# ==========================================================================
# FIG 8 -- India case study: which bloc, across time
# ==========================================================================
def fig08(country="India"):
    ys, side, vol = [], [], []
    for y in YEARS:
        n = next((x for x in D["frames"][str(y)]["nodes"] if x["id"] == country), None)
        if not n:
            continue
        ys.append(y); side.append(n["c2"]); vol.append(n["cr"] * 100)
    fig, ax = plt.subplots(figsize=(9.4, 3.0))
    ax.plot(ys, vol, color="#8b5cf6", lw=2.0, label="% of trade crossing bloc lines")
    for i in range(len(ys) - 1):
        ax.axvspan(ys[i], ys[i + 1], color=PAL[side[i]], alpha=.16, lw=0)
    ax.set_ylim(0, 100)
    ax.set_xlim(min(ys), max(ys))
    ax.set_xlabel("year"); ax.set_ylabel("cross-bloc trade share (%)")
    ax.set_title(f"{country} as a bridge nation. Background colour = which bloc "
                 f"{country} was assigned to.", fontsize=10.5)
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    ax.grid(alpha=.25, ls=":")
    return save(fig, "fig08_india_bridge.png")


# ==========================================================================
# FIG 11 -- the two validation results in ONE figure (replaces fig04 + fig05)
# ==========================================================================
def fig11():
    fig, axes = plt.subplots(1, 2, figsize=(10.4, 3.5))

    # (a) how many times bigger the real split is than the shuffled one
    rat = [D["frames"][str(y)]["stats"]["gap2"]
           / D["frames"][str(y)]["random"]["gap_mean"]["2"] for y in YEARS]
    ax = axes[0]
    ax.fill_between(YEARS, 1, rat, color="#0e9ec4", alpha=.2)
    ax.plot(YEARS, rat, color="#0e9ec4", lw=2.1)
    ax.axhline(1, color="#e02a4d", ls=":", lw=1.2)
    ax.text(YEARS[1], 1.6, "1x = no better than shuffled", color="#e02a4d", fontsize=7.5)
    ax.axvline(1991, color=GREY, lw=1, ls="--")
    ax.text(1991.8, max(rat)*.9, "USSR ends", fontsize=7.5, color="#5b6b78")
    ax.set_xlabel("year"); ax.set_ylabel("times bigger than shuffled")
    ax.set_title("(a) The split is always far stronger than chance", fontsize=9.5)
    ax.grid(alpha=.25, ls=":")

    # (b) how many countries stay in the same group next year
    ys, pr, rr = [], [], []
    for y in YEARS:
        s, r = D["frames"][str(y)]["stats"], D["frames"][str(y)]["random"]
        if s["persist2"] is None or r["persist"]["2"] is None:
            continue
        ys.append(y); pr.append(s["persist2"]*100); rr.append(r["persist"]["2"]*100)
    ax = axes[1]
    ax.plot(ys, pr, color="#0e9ec4", lw=2.1, label="real world")
    ax.plot(ys, rr, color="#e02a4d", lw=1.5, ls="--", label="shuffled")
    ax.fill_between(ys, rr, pr, color="#0e9ec4", alpha=.13)
    ax.set_ylim(0, 105)
    ax.set_xlabel("year"); ax.set_ylabel("% staying in the same group")
    ax.axhline(50, color=GREY, ls=":", lw=1.2)
    ax.text(ys[1], 42, "pure chance for a 2-way split = 50%", fontsize=7.5, color="#5b6b78")
    ax.set_title("(b) Real groups last; shuffled ones barely beat chance", fontsize=9.5)
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    ax.grid(alpha=.25, ls=":")

    fig.suptitle("Two checks that the groups are real, run on all 67 years",
                 y=1.02, fontsize=10.5, fontweight="bold")
    return save(fig, "fig11_validation.png")


if __name__ == "__main__":
    print("generating figures ...")
    for fn in (fig01, fig02, fig10, fig11):     # the four used in the report
        fn()
    json.dump(STATS, open(os.path.join(FIG, "fig_stats.json"), "w"), indent=1)
    print("done ->", FIG, STATS)
