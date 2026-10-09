"""
=============================================================================
 GLOBAL ARMS TRADE NETWORK  --  SPECTRAL PARTITIONING PIPELINE
 23CSE451 Graph Mining, Case Study
=============================================================================

WHAT THIS SCRIPT DOES, IN ONE SENTENCE:
    It reads SIPRI's raw arms-transfer records, turns them into a weighted
    graph of countries for every year from 1959 to 2025, splits that graph
    into geopolitical blocs using spectral partitioning, and writes one JSON
    file that the 3D globe website reads.

PIPELINE STAGES
    1. LOAD      read the SIPRI trade register CSV (skip its 10 preamble rows)
    2. CLEAN     drop non-state actors, merge duplicate country names
    3. EXPLODE   one record can cover many delivery years -> split the volume
    4. SNAPSHOT  for year Y, build the graph of the 10-year window [Y-9, Y]
    5. MINE      normalised Laplacian -> eigendecomposition -> k-means  (k=4)
    6. MEASURE   betweenness centrality, bridge nations, normalised cut
    7. NULL      repeat everything on a random graph of the same size
    8. EXPORT    web/data.json

RUN:  python analysis/build_graph.py
=============================================================================
"""

import csv
import io
import json
import os
import re
import time
from collections import defaultdict

import numpy as np
import networkx as nx
from scipy.linalg import eigh
from scipy.optimize import linear_sum_assignment
from sklearn.cluster import KMeans

from country_coords import COORDS, ALIASES

# --------------------------------------------------------------------------
# CONFIGURATION
# --------------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

CSV_PATH = os.path.join(ROOT, "data", "sipri_trade_register.csv")
OUT_JSON = os.path.join(ROOT, "web", "data.json")

# ---- HOW MANY BLOCS? ------------------------------------------------------
# We do NOT pick k by taste.  We read it off the eigenvalue spectrum: the
# eigengap heuristic says the right k is where the sorted eigenvalues of the
# Laplacian jump.  On this data the jump after the 2nd eigenvalue is roughly
# 10x bigger than any other, so the data's own answer is k = 2 -- a bipolar
# world.  The next-largest gap sits at k = 4, which resolves that bipolar
# split into four regional blocs.  We compute BOTH and report both.
K_PRIMARY = 2        # eigengap-optimal partition (the headline result)
K_REFINED = 4        # secondary partition, used for the globe colours
K_LIST = [K_PRIMARY, K_REFINED]
K_CLUSTERS = K_REFINED
WINDOW = 10          # sliding window length in years
FIRST_YEAR = 1959    # first year that has a full 10-year window
LAST_YEAR = 2025
MAX_LINKS_OUT = 350  # only the heaviest arcs are drawn on the globe
MAX_RAND_LINKS = 220
N_EIGS_OUT = 12      # how many eigenvalues to send to the spectral-gap chart
N_NULL = 10          # random replicas used to build the null distribution
SEED = 42

rng = np.random.default_rng(SEED)


# ==========================================================================
# STAGE 1 + 2 + 3 :  LOAD, CLEAN, EXPLODE
# ==========================================================================
def load_transfers():
    """
    Returns a list of (supplier, recipient, year, tiv) tuples.

    The SIPRI CSV has three quirks we must handle:
      (a) 10 lines of human-readable preamble before the real header row
      (b) it is cp1252 encoded, not UTF-8
      (c) 'Year(s) of delivery' can hold many years ("1979; 1980; 1981"),
          while 'SIPRI TIV of delivered weapons' is the TOTAL over all of
          them.  We divide the total evenly across the listed years.
    """
    raw = open(CSV_PATH, encoding="cp1252", errors="replace").read().split("\n")
    header_idx = next(i for i, l in enumerate(raw) if l.startswith("Recipient,Supplier"))
    reader = csv.DictReader(io.StringIO("\n".join(raw[header_idx:])))

    out = []
    stats = {"rows": 0, "nonstate": 0, "noyear": 0, "novalue": 0, "kept": 0}

    for row in reader:
        stats["rows"] += 1
        sup = (row.get("Supplier") or "").strip()
        rec = (row.get("Recipient") or "").strip()

        # (2) CLEAN -- SIPRI marks rebel groups with * and organisations with **
        if not sup or not rec:
            continue
        if "*" in sup or "*" in rec or "unknown" in sup.lower() or "unknown" in rec.lower():
            stats["nonstate"] += 1
            continue
        sup = ALIASES.get(sup, sup)
        rec = ALIASES.get(rec, rec)
        if sup == rec:
            continue
        if sup not in COORDS or rec not in COORDS:
            stats["nonstate"] += 1
            continue

        years = [int(y) for y in re.findall(r"\d{4}", row.get("Year(s) of delivery") or "")]
        years = [y for y in years if 1949 <= y <= LAST_YEAR]
        if not years:
            stats["noyear"] += 1
            continue

        try:
            tiv = float(row.get("SIPRI TIV of delivered weapons") or 0)
        except ValueError:
            tiv = 0.0
        if tiv <= 0:
            stats["novalue"] += 1
            continue

        # (3) EXPLODE -- spread the delivered volume evenly over the years
        share = tiv / len(years)
        for y in years:
            out.append((sup, rec, y, share))
        stats["kept"] += 1

    return out, stats


# ==========================================================================
# STAGE 4 :  BUILD ONE SNAPSHOT GRAPH
# ==========================================================================
def snapshot_edges(by_year, year):
    """Aggregate all transfers inside the sliding window [year-WINDOW+1, year]."""
    acc = defaultdict(float)
    for y in range(year - WINDOW + 1, year + 1):
        for (sup, rec), v in by_year.get(y, {}).items():
            acc[(sup, rec)] += v
    return acc


def build_graphs(edge_weights):
    """
    Returns (G_directed, G_undirected, nodes).

    Spectral partitioning needs a SYMMETRIC matrix, so the undirected graph
    uses W = (A + A^T) / 2.  The directed graph is kept only so the globe can
    animate arcs in the true supplier -> recipient direction.
    """
    DG = nx.DiGraph()
    for (s, t), w in edge_weights.items():
        DG.add_edge(s, t, weight=w)

    UG = nx.Graph()
    for (s, t), w in edge_weights.items():
        a, b = (s, t) if s < t else (t, s)
        if UG.has_edge(a, b):
            UG[a][b]["weight"] += w / 2.0
        else:
            UG.add_edge(a, b, weight=w / 2.0)

    # ---- WHY WE TAKE THE LOG OF EVERY EDGE WEIGHT -----------------------
    # Raw SIPRI TIV spans five orders of magnitude (one 0.08 rifle deal next
    # to a 6000 fighter-jet deal). Fed straight into the Laplacian, a handful
    # of mega-deals dominate every eigenvector and the partition just isolates
    # those few edges instead of finding real blocs. A $10 bn transfer does
    # not make two countries 1000x more "allied" than a $10 m one, so we
    # compress the scale with lw = log(1 + TIV) and cluster on that.
    # The raw TIV is kept for arc thickness and all reported volumes.
    for _, _, d in UG.edges(data=True):
        d["lw"] = float(np.log1p(d["weight"]))

    # spectral partitioning is only defined on a connected graph, so we work
    # on the largest connected component (isolated countries get cluster -1)
    if UG.number_of_nodes():
        giant = max(nx.connected_components(UG), key=len)
        UG = UG.subgraph(giant).copy()
    return DG, UG, list(UG.nodes())


# ==========================================================================
# STAGE 5 :  SPECTRAL PARTITIONING  (hand-rolled, not a black box)
# ==========================================================================
def spectral_partition(W, k):
    """
    Normalised-cut spectral clustering, written out step by step.

        1. degree matrix          D = diag(sum of each row of W)
        2. normalised Laplacian   L = I - D^(-1/2) W D^(-1/2)
        3. eigendecomposition     L u = lambda u          (scipy.linalg.eigh)
        4. embedding              U = k eigenvectors of the k SMALLEST lambdas
        5. row-normalise U        (Ng-Jordan-Weiss step, projects onto sphere)
        6. k-means on the rows of U -> one cluster label per country

    Why the SMALLEST eigenvalues?  lambda measures how much an edge weight is
    "cut" by a candidate split.  Small lambda = a split that cuts very little
    = a natural boundary in the network.  lambda_1 is always 0.

    Returns (labels, eigenvalues, embedding).
    """
    n = W.shape[0]
    deg = W.sum(axis=1)
    deg[deg <= 0] = 1e-12
    d_inv_sqrt = 1.0 / np.sqrt(deg)

    # L_sym = I - D^-1/2 W D^-1/2   (built without forming D explicitly)
    L = np.eye(n) - (W * d_inv_sqrt[:, None]) * d_inv_sqrt[None, :]
    L = (L + L.T) / 2.0                      # kill floating-point asymmetry

    eigenvalues, eigenvectors = eigh(L)      # ascending order, O(n^3)

    U = eigenvectors[:, :k]
    norms = np.linalg.norm(U, axis=1, keepdims=True)
    norms[norms < 1e-12] = 1.0
    U = U / norms

    labels = KMeans(n_clusters=k, n_init=20, random_state=SEED).fit_predict(U)
    return labels, eigenvalues, U


def normalised_cut(W, labels, k):
    """
    Ncut = sum over clusters of  cut(C, rest) / volume(C).
    Lower is better.  A perfect split of k disconnected blobs gives 0.
    A meaningless split of a random graph gives a value close to k-1.
    """
    total = 0.0
    vol_all = W.sum()
    for c in range(k):
        mask = labels == c
        if not mask.any():
            continue
        vol = W[mask].sum()
        cut = W[np.ix_(mask, ~mask)].sum()
        total += cut / vol if vol > 0 else 0.0
    return float(total)


def align_labels(prev_labels, prev_nodes, labels, nodes, k):
    """
    k-means numbers its clusters arbitrarily, so "cluster 2" in 1980 has
    nothing to do with "cluster 2" in 1981 and the globe colours would flicker.

    Fix: build a k x k overlap table between last year's labelling and this
    year's, then use the Hungarian algorithm to find the relabelling that
    keeps the most countries in the same colour.
    """
    if prev_labels is None:
        return labels
    prev_map = dict(zip(prev_nodes, prev_labels))
    overlap = np.zeros((k, k))
    for node, new_c in zip(nodes, labels):
        old_c = prev_map.get(node)
        if old_c is not None and old_c >= 0:
            overlap[new_c, old_c] += 1
    row, col = linear_sum_assignment(-overlap)      # maximise overlap
    remap = {r: c for r, c in zip(row, col)}
    return np.array([remap.get(int(c), int(c)) for c in labels])


# ==========================================================================
# STAGE 6 :  CENTRALITY AND BRIDGE NATIONS
# ==========================================================================
def betweenness(UG):
    """
    Betweenness centrality on the weighted graph.

    networkx treats 'weight' as a DISTANCE (small = close), but our weight is
    trade VOLUME (big = close).  So we feed it 1/volume as the distance.
    """
    H = nx.Graph()
    for u, v, d in UG.edges(data=True):
        H.add_edge(u, v, dist=1.0 / max(d["lw"], 1e-9))
    return nx.betweenness_centrality(H, weight="dist", normalized=True)


def bridge_scores(UG, cluster_of):
    """
    A 'bridge nation' is a country whose trade is unusually split ACROSS
    blocs rather than inside its own bloc.

        cross_ratio = (weight going to other clusters) / (total weight)

    Combined with high betweenness this identifies the diplomatic middlemen.
    """
    out = {}
    for n in UG.nodes():
        own = cluster_of.get(n, -1)
        total = cross = 0.0
        for nb in UG.neighbors(n):
            w = UG[n][nb]["lw"]
            total += w
            if cluster_of.get(nb, -1) != own:
                cross += w
        out[n] = cross / total if total > 0 else 0.0
    return out


# ==========================================================================
# STAGE 7 :  RANDOM NULL MODEL
# ==========================================================================
def random_twin(UG, seed):
    """
    Build a random graph with the SAME countries, the SAME number of edges and
    the SAME multiset of edge weights -- but wired completely at random
    (Erdos-Renyi G(n, m)).  Everything the real network has is preserved
    except ONE thing: who trades with whom.  So any structure spectral
    partitioning still finds here is, by construction, pure chance.
    """
    nodes = sorted(UG.nodes())
    R = nx.gnm_random_graph(len(nodes), UG.number_of_edges(), seed=seed)
    R = nx.relabel_nodes(R, {i: n for i, n in enumerate(nodes)})

    pairs = [(d["weight"], d["lw"]) for _, _, d in UG.edges(data=True)]
    np.random.default_rng(seed).shuffle(pairs)
    for (u, v), (w, lw) in zip(R.edges(), pairs):
        R[u][v]["weight"] = float(w)
        R[u][v]["lw"] = float(lw)

    if R.number_of_nodes():
        giant = max(nx.connected_components(R), key=len)
        R = R.subgraph(giant).copy()
    return R


def best_k(eigenvalues, kmax=8):
    """
    The eigengap heuristic, stated plainly: sort the Laplacian eigenvalues and
    find where the biggest jump is.  If the graph really contains k well
    separated blocs, the first k eigenvalues are all near zero and the (k+1)th
    is clearly bigger -- so the biggest jump lands exactly at k.
    """
    gaps = {k: float(eigenvalues[k] - eigenvalues[k - 1]) for k in range(2, kmax + 1)}
    return max(gaps, key=gaps.get), gaps


def analyse_random(UG, k, prev_rand):
    """
    Run the IDENTICAL spectral pipeline on N_NULL random twins.

    One random graph proves nothing (it might get lucky), so we build ten and
    turn the spectral gaps into a proper null distribution.  The headline
    number is then a z-score:

        z = (gap_real - mean(gap_random)) / std(gap_random)

    i.e. "the real network's spectral gap is z standard deviations larger
    than anything random wiring produces."

    Replica 0 is also returned in full so the website can draw the random
    network on the globe next to the real one.
    """
    gaps = {kk: [] for kk in K_LIST}
    mods, ncuts = [], []
    rep = None

    for s in range(N_NULL):
        R = random_twin(UG, SEED + s)
        if R.number_of_nodes() < max(K_LIST) + 2:
            continue
        nodes = list(R.nodes())
        W = nx.to_numpy_array(R, nodelist=nodes, weight="lw")
        labels, eigs, _ = spectral_partition(W, k)

        # the eigenvalues do not depend on k, so one decomposition serves both
        for kk in K_LIST:
            gaps[kk].append(float(eigs[kk] - eigs[kk - 1]))

        comms = [set(np.array(nodes)[labels == c]) for c in range(k)]
        comms = [c for c in comms if c]
        ncuts.append(normalised_cut(W, labels, k))
        mods.append(float(nx.community.modularity(R, comms, weight="lw")))

        if rep is None:
            # Partition the SAME random twin at every k we report, so the
            # "stayed in the same group" comparison is like-for-like against
            # the real network at that same k.
            order = {}
            for kk in K_LIST:
                lb, _, _ = spectral_partition(W, kk)
                prev = prev_rand.get(kk) if prev_rand else None
                lb = align_labels(prev[1] if prev else None,
                                  prev[0] if prev else None, lb, nodes, kk)
                order[kk] = (nodes, lb)
            labels = order[k][1]
            cluster_of = dict(zip(nodes, (int(c) for c in labels)))
            links = sorted(R.edges(data=True), key=lambda e: -e[2]["weight"])[:MAX_RAND_LINKS]
            rep = {
                "eig": [round(float(v), 5) for v in eigs[:N_EIGS_OUT]],
                "nodes": [{"id": n, "lat": COORDS[n][0], "lng": COORDS[n][1],
                           "c": cluster_of[n]} for n in nodes],
                "links": [{"s": u, "t": v, "v": round(d["weight"], 1),
                           "c": cluster_of.get(u, 0)} for u, v, d in links],
                "labels": order,
            }

    if rep is None:
        return None, prev_rand

    order = rep.pop("labels")
    rep["gap_mean"] = {str(kk): round(float(np.mean(v)), 5) for kk, v in gaps.items()}
    rep["gap_std"] = {str(kk): round(float(np.std(v)), 5) for kk, v in gaps.items()}
    rep["ncut"] = round(float(np.mean(ncuts)), 4)
    rep["modularity"] = round(float(np.mean(mods)), 4)
    rep["n_replicas"] = len(ncuts)
    return rep, order


def persistence(prev_nodes, prev_labels, nodes, labels):
    """
    Fraction of countries that stay in the SAME bloc from one year to the next.

    This is the most human-readable proof that the blocs are real: genuine
    alliances persist, noise does not.  Pure chance would give about 1/k.
    """
    if prev_labels is None:
        return None
    prev_map = dict(zip(prev_nodes, prev_labels))
    hits = [prev_map[n] == c for n, c in zip(nodes, labels) if n in prev_map]
    return float(np.mean(hits)) if hits else None



# ==========================================================================
# MAIN
# ==========================================================================
def main():
    t0 = time.time()
    print("=" * 70)
    print("GLOBAL ARMS TRADE NETWORK -- SPECTRAL PARTITIONING")
    print("=" * 70)

    # ---- stages 1-3 ------------------------------------------------------
    transfers, stats = load_transfers()
    print(f"[1] raw CSV rows              : {stats['rows']:,}")
    print(f"    dropped, non-state actor  : {stats['nonstate']:,}")
    print(f"    dropped, no delivery year : {stats['noyear']:,}")
    print(f"    dropped, zero volume      : {stats['novalue']:,}")
    print(f"    kept records              : {stats['kept']:,}")
    print(f"[3] year-level transfer rows  : {len(transfers):,}")

    by_year = defaultdict(lambda: defaultdict(float))
    for sup, rec, y, v in transfers:
        by_year[y][(sup, rec)] += v

    all_countries = sorted({c for s, r, _, _ in transfers for c in (s, r)})
    all_pairs = {(s, r) for s, r, _, _ in transfers}
    total_tiv = sum(v for *_, v in transfers)
    print(f"    countries (vertices)      : {len(all_countries)}")
    print(f"    directed pairs (edges)    : {len(all_pairs):,}")
    print(f"    total volume (TIV, mn)    : {total_tiv:,.0f}")

    # ---- stages 4-7, one snapshot per year -------------------------------
    years_out, frames = [], {}
    prev = {kk: (None, None) for kk in K_LIST}   # (nodes, labels) per k
    prev_rand = None   # {k: (nodes, labels)} of the representative twin

    for year in range(FIRST_YEAR, LAST_YEAR + 1):
        edges = snapshot_edges(by_year, year)
        if len(edges) < 20:
            continue
        DG, UG, nodes = build_graphs(edges)
        if len(nodes) < K_CLUSTERS + 2:
            continue

        # cluster on the LOG weights (see build_graphs for why)
        W = nx.to_numpy_array(UG, nodelist=nodes, weight="lw")

        # ---- run the partition at BOTH k values --------------------------
        part = {}
        for kk in K_LIST:
            lab, eigs, _ = spectral_partition(W, kk)
            lab = align_labels(prev[kk][1], prev[kk][0], lab, nodes, kk)
            part[kk] = {
                "labels": lab,
                "persist": persistence(prev[kk][0], prev[kk][1], nodes, lab),
                "cluster_of": dict(zip(nodes, (int(c) for c in lab))),
                "ncut": normalised_cut(W, lab, kk),
                "gap": float(eigs[kk] - eigs[kk - 1]),
            }
            prev[kk] = (nodes, lab)

        labels = part[K_REFINED]["labels"]
        persist = part[K_REFINED]["persist"]
        cluster_of = part[K_REFINED]["cluster_of"]
        suggested_k, gap_by_k = best_k(eigs)

        btw = betweenness(UG)
        bridges = bridge_scores(UG, cluster_of)

        # per-country import / export volume inside this window
        exp_v, imp_v, partners = defaultdict(float), defaultdict(float), defaultdict(list)
        for (s, t), w in edges.items():
            exp_v[s] += w
            imp_v[t] += w
            partners[s].append((t, w, "out"))
            partners[t].append((s, w, "in"))

        comms = [set(np.array(nodes)[labels == c]) for c in range(K_CLUSTERS)]
        comms = [c for c in comms if c]
        modularity = float(nx.community.modularity(UG, comms, weight="lw"))
        ncut = part[K_REFINED]["ncut"]
        gap = part[K_REFINED]["gap"]

        # identical pipeline on ten random twins -> null distribution
        rand, new_rand = analyse_random(UG, K_CLUSTERS, prev_rand)
        if rand is not None:
            rand["persist"] = {}
            for kk in K_LIST:
                rp = None
                if prev_rand is not None:
                    rp = persistence(prev_rand[kk][0], prev_rand[kk][1],
                                     new_rand[kk][0], new_rand[kk][1])
                rand["persist"][str(kk)] = round(rp, 4) if rp is not None else None
            # z = how many standard deviations the real gap beats random by
            rand["z"] = {
                str(kk): round((part[kk]["gap"] - rand["gap_mean"][str(kk)])
                               / max(rand["gap_std"][str(kk)], 1e-9), 2)
                for kk in K_LIST
            }
            prev_rand = new_rand

        # name each bloc after its heaviest member -> "US-led bloc" etc.
        cluster_names = {}
        for kk in K_LIST:
            co = part[kk]["cluster_of"]
            names = {}
            for c in range(kk):
                members = [n for n in nodes if co[n] == c]
                if members:
                    names[str(c)] = max(members, key=lambda n: exp_v[n] + imp_v[n])
            cluster_names[str(kk)] = names

        # bridge nations: top betweenness AND genuinely cross-bloc trade
        ranked = sorted(nodes, key=lambda n: btw.get(n, 0), reverse=True)
        bridge_set = {n for n in ranked[:12] if bridges.get(n, 0) > 0.35}

        node_out = []
        for n in nodes:
            tp = sorted(partners[n], key=lambda x: -x[1])[:10]
            node_out.append({
                "id": n,
                "lat": COORDS[n][0], "lng": COORDS[n][1],
                "c": cluster_of[n],                      # k = 4 (globe colours)
                "c2": part[K_PRIMARY]["cluster_of"][n],  # k = 2 (eigengap-optimal)
                "ex": round(exp_v[n], 1), "im": round(imp_v[n], 1),
                "bt": round(btw.get(n, 0.0), 4),
                "cr": round(bridges.get(n, 0.0), 3),
                "br": 1 if n in bridge_set else 0,
                "tp": [[p, round(w, 1), d] for p, w, d in tp],
            })

        top_links = sorted(edges.items(), key=lambda kv: -kv[1])[:MAX_LINKS_OUT]
        c2 = part[K_PRIMARY]["cluster_of"]
        link_out = [{
            "s": s, "t": t, "v": round(w, 1),
            "c": cluster_of.get(s, cluster_of.get(t, 0)),
            "c2": c2.get(s, c2.get(t, 0)),
        } for (s, t), w in top_links]

        frames[year] = {
            "nodes": node_out,
            "links": link_out,
            "eig": [round(float(v), 5) for v in eigs[:N_EIGS_OUT]],
            "names": cluster_names,
            "stats": {
                "n": len(nodes),
                "m": UG.number_of_edges(),
                "dm": DG.number_of_edges(),
                "vol": round(sum(edges.values()), 1),
                "mod": round(modularity, 4),
                "ncut": round(ncut, 4),
                "gap": round(gap, 5),
                "gap2": round(part[K_PRIMARY]["gap"], 5),
                "ncut2": round(part[K_PRIMARY]["ncut"], 4),
                "dens": round(nx.density(UG), 4),
                "persist": round(persist, 4) if persist is not None else None,
                "persist2": (round(part[K_PRIMARY]["persist"], 4)
                             if part[K_PRIMARY]["persist"] is not None else None),
                "bestk": suggested_k,
                "gapk": {str(kk): round(v, 5) for kk, v in gap_by_k.items()},
            },
            "random": rand,
        }
        years_out.append(year)

        if year % 10 == 0 or year in (FIRST_YEAR, LAST_YEAR):
            z2 = rand["z"]["2"] if rand else 0
            z4 = rand["z"]["4"] if rand else 0
            p = f"{persist:.2f}" if persist is not None else "  - "
            print(f"[5] {year}  n={len(nodes):3d} m={UG.number_of_edges():4d} "
                  f" k=2: gap={part[K_PRIMARY]['gap']:.3f} z={z2:+6.1f} | "
                  f"k=4: gap={gap:.3f} z={z4:+5.1f} | persist={p}")

    payload = {
        "meta": {
            "k": K_CLUSTERS,
            "k_primary": K_PRIMARY,
            "k_refined": K_REFINED,
            "n_null": N_NULL,
            "window": WINDOW,
            "years": years_out,
            "source": "SIPRI Arms Transfers Database",
            "total_countries": len(all_countries),
            "total_pairs": len(all_pairs),
            "total_tiv": round(total_tiv, 1),
            "raw_rows": stats["rows"],
            "kept_rows": stats["kept"],
        },
        "frames": {str(y): frames[y] for y in years_out},
    }

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, separators=(",", ":"))

    size_mb = os.path.getsize(OUT_JSON) / 1e6
    print("-" * 70)
    print(f"[8] wrote {OUT_JSON}  ({size_mb:.2f} MB, {len(years_out)} snapshots)")
    print(f"    finished in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
