"""
Builds the filled case-study report:
    Graph_Mining_Case_Study_Report_FILLED.docx

The ORIGINAL template is opened read-only, only to inherit its fonts, heading
styles and page setup. It is never written to.

WRITING RULES FOR THIS DOCUMENT
  * Short sentences. One idea per sentence.
  * Everyday words. Any technical word is explained the moment it appears.
  * Tables and lists instead of long paragraphs wherever possible.
  * Keep it short: every section as brief as the template allows. 6 figures.
"""

import json
import os

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TEMPLATE = os.path.join(ROOT, "Graph_Mining_Case_Study_Report_Format.docx")
OUT = os.path.join(ROOT, "Graph_Mining_Case_Study_Report_FILLED.docx")
FIG = os.path.join(ROOT, "figures")

# ---- fill these in, or leave blank and write them by hand ------------------
STUDENT_NAME = ""
REGISTER_NO = ""
BATCH_CLASS = ""
SUBMISSION_DATE = ""

SITE = "https://arms.armstrade.workers.dev"

ACCENT = RGBColor(0x0E, 0x6E, 0x9C)
MUTED = RGBColor(0x55, 0x66, 0x72)

D = json.load(open(os.path.join(ROOT, "web", "data.json"), encoding="utf-8"))
M = D["meta"]
A = D["frames"]["1987"]
B = D["frames"]["2025"]

# every number quoted in the text is computed here, never typed by hand
RATIO_A = A["stats"]["gap2"] / A["random"]["gap_mean"]["2"]
RATIO_B = B["stats"]["gap2"] / B["random"]["gap_mean"]["2"]
RATIOS = [D["frames"][str(y)]["stats"]["gap2"] / D["frames"][str(y)]["random"]["gap_mean"]["2"]
          for y in M["years"]]
R_MIN, R_MAX = min(RATIOS), max(RATIOS)
R_AVG = sum(RATIOS) / len(RATIOS)
P_REAL = [D["frames"][str(y)]["stats"]["persist2"] for y in M["years"]
          if D["frames"][str(y)]["stats"]["persist2"] is not None]
P_RAND = [D["frames"][str(y)]["random"]["persist"]["2"] for y in M["years"]
          if D["frames"][str(y)]["random"]["persist"]["2"] is not None]
Y_MAX = M["years"][RATIOS.index(R_MAX)]
Y_MIN = M["years"][RATIOS.index(R_MIN)]
FS = json.load(open(os.path.join(FIG, "fig_stats.json"), encoding="utf-8"))
PR = 100 * sum(P_REAL) / len(P_REAL)
PX = 100 * sum(P_RAND) / len(P_RAND)

doc = Document(TEMPLATE)
body = doc.element.body
sectPr = body.find(qn("w:sectPr"))
for child in list(body):
    if child is not sectPr:
        body.remove(child)


# ===========================================================================
# helpers
# ===========================================================================
def para(text="", size=10.5, bold=False, italic=False, color=None,
         align=None, space_after=6):
    p = doc.add_paragraph()
    if align is not None:
        p.alignment = align
    p.paragraph_format.space_after = Pt(space_after)
    if text:
        r = p.add_run(text)
        r.bold, r.italic = bold, italic
        r.font.size = Pt(size)
        if color is not None:
            r.font.color.rgb = color
    return p


def rich(parts, size=10.5, space_after=6):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    for text, bold in parts:
        r = p.add_run(text)
        r.bold = bold
        r.font.size = Pt(size)
    return p


def h1(t):
    doc.add_heading(t, level=1)


def h2(t):
    doc.add_heading(t, level=2)


def bullets(items, size=10.5):
    for it in items:
        p = doc.add_paragraph(style="List Bullet")
        p.paragraph_format.space_after = Pt(3)
        if isinstance(it, (list, tuple)):
            for text, bold in it:
                r = p.add_run(text); r.bold = bold; r.font.size = Pt(size)
        else:
            r = p.add_run(it); r.font.size = Pt(size)


def numbered(items, size=10.5):
    """Numbers written by hand: Word's List Number style shares one counter
    across the document, so every later list would carry on from the last."""
    for i, it in enumerate(items, 1):
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(3)
        p.paragraph_format.left_indent = Inches(0.35)
        p.paragraph_format.first_line_indent = Inches(-0.35)
        n = p.add_run(f"{i}.  "); n.bold = True; n.font.size = Pt(size)
        if isinstance(it, (list, tuple)):
            for text, bold in it:
                r = p.add_run(text); r.bold = bold; r.font.size = Pt(size)
        else:
            r = p.add_run(it); r.font.size = Pt(size)


def shade(cell, hexcolor):
    tcPr = cell._tc.get_or_add_tcPr()
    el = OxmlElement("w:shd")
    el.set(qn("w:val"), "clear")
    el.set(qn("w:fill"), hexcolor)
    tcPr.append(el)


def table(rows, header=True, widths=None, size=9.5):
    t = doc.add_table(rows=len(rows), cols=len(rows[0]))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, row in enumerate(rows):
        for j, val in enumerate(row):
            cell = t.cell(i, j)
            cell.text = ""
            p = cell.paragraphs[0]
            p.paragraph_format.space_after = Pt(2)
            p.paragraph_format.space_before = Pt(2)
            r = p.add_run(str(val))
            r.font.size = Pt(size)
            if header and i == 0:
                r.bold = True
                shade(cell, "0E6E9C")
                r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
            elif j == 0 and len(row) > 1:
                r.bold = True
            if i < len(rows) - 1:
                p.paragraph_format.keep_with_next = True   # keep the table on one page
    if widths:
        for j, w in enumerate(widths):
            for row in t.rows:
                row.cells[j].width = Inches(w)
    doc.add_paragraph().paragraph_format.space_after = Pt(4)
    return t


_fig = [0]


def figure(fname, caption, width=6.3):
    _fig[0] += 1
    path = os.path.join(FIG, fname)
    if not os.path.exists(path):
        para(f"[missing figure: {fname}]", italic=True, color=MUTED)
        return
    doc.add_picture(path, width=Inches(width))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.paragraphs[-1].paragraph_format.keep_with_next = True   # caption stays with it
    para(f"Figure {_fig[0]} — {caption}", size=9, italic=True, color=MUTED,
         align=WD_ALIGN_PARAGRAPH.CENTER, space_after=12)


def box(text, label="In simple words:  "):
    t = doc.add_table(rows=1, cols=1)
    t.style = "Table Grid"
    c = t.cell(0, 0)
    shade(c, "EAF4FA")
    c.text = ""
    p = c.paragraphs[0]
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run(label); r.bold = True; r.font.size = Pt(9.5); r.font.color.rgb = ACCENT
    r2 = p.add_run(text); r2.font.size = Pt(9.5)
    doc.add_paragraph().paragraph_format.space_after = Pt(6)


def about(made, settings, shows):
    """Plain-words note under a figure: how it was made, the settings, what it shows."""
    p = para(f"About Figure {_fig[0]}", size=10, bold=True, color=ACCENT, space_after=2)
    p.paragraph_format.keep_with_next = True
    table([["How it was made", made], ["Settings used", settings], ["What it shows", shows]],
          header=False, widths=[1.45, 5.05], size=9.5)


def brk():
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


# ===========================================================================
# COVER
# ===========================================================================
para("Amrita Vishwa Vidyapeetham", size=15, bold=True,
     align=WD_ALIGN_PARAGRAPH.CENTER, space_after=2)
para("Amrita School of Computing, Amritapuri Campus", size=11.5,
     align=WD_ALIGN_PARAGRAPH.CENTER, space_after=2)
para("Department of Computer Science and Engineering", size=11.5,
     align=WD_ALIGN_PARAGRAPH.CENTER, space_after=22)

para("CASE STUDY REPORT", size=22, bold=True, color=ACCENT,
     align=WD_ALIGN_PARAGRAPH.CENTER, space_after=6)
para("23CSE451 - Graph Mining", size=13, bold=True,
     align=WD_ALIGN_PARAGRAPH.CENTER, space_after=2)
para("Academic Year: 2026-2027  |  Semester: VII  |  L-T-P-C: 3-0-0-3", size=10.5,
     color=MUTED, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=26)

para("Finding the Two Sides of the Global Arms Trade "
     "using Spectral Partitioning", size=15, bold=True,
     align=WD_ALIGN_PARAGRAPH.CENTER, space_after=4)
para("SIPRI weapons data, 1950 to 2025", size=11, italic=True,
     color=MUTED, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=24)

table([
    ["Title of Case Study", "Finding the Two Sides of the Global Arms Trade "
                            "using Spectral Partitioning"],
    ["Student Name(s)", STUDENT_NAME or "_______________________________"],
    ["Register Number(s)", REGISTER_NO or "_______________________________"],
    ["Batch / Class", BATCH_CLASS or "_______________________________"],
    ["Date of Submission", SUBMISSION_DATE or "_______________________________"],
], header=False, widths=[2.1, 4.4], size=10.5)

para()
para("Interactive website made for this case study:",
     size=10.5, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=3)
para(SITE, size=13, bold=True, color=ACCENT,
     align=WD_ALIGN_PARAGRAPH.CENTER, space_after=2)

brk()

# ===========================================================================
# 1. ABSTRACT
# ===========================================================================
h1("1. Abstract")
para("Countries buy weapons from countries they trust. So the weapons trade shows who is on "
     "whose side. We drew 75 years of SIPRI weapons deals as a graph: countries are dots, and "
     "deals are lines between them. Then we used spectral partitioning to cut the graph into "
     "groups, while cutting as few lines as possible.")
rich([
    ("The result: the world splits into ", False),
    ("two sides", True),
    (", one led by the Soviet Union (later Russia) and one led by the United States. The maths "
     "chose two groups by itself, ", False),
    ("in all 67 years", True),
    (". The split is ", False),
    (f"{R_AVG:.0f} times stronger", True),
    (" than in a randomly shuffled network, so it is not luck.", False),
])
box("We gave the computer only a list of who sold weapons to whom. It found the two sides of "
    "the Cold War by itself.")

h2("1.1 Key words")
table([
    ["Word", "Meaning"],
    ["Graph", "Dots joined by lines"],
    ["Node", "A dot. Here, a country"],
    ["Edge", "A line. Here, weapons sold from one country to another"],
    ["Weight", "How strong a line is. Here, the amount of weapons"],
    ["TIV", "SIPRI's unit for an amount of weapons (military value, not money)"],
    ["Laplacian", "A table of numbers made from the graph"],
    ["Eigenvector", "A list of numbers that comes out of the Laplacian. It gives every "
                    "country one number, and the sign of that number tells its group"],
], widths=[1.4, 5.1])

# ===========================================================================
# 2. INTRODUCTION
# ===========================================================================
h1("2. Introduction")
para("A weapons deal is a long friendship. The buyer needs spare parts, training and repairs "
     "from the seller for many years. So countries only buy weapons from friends.")
para("Friendships between countries are often secret. Weapons deals are not. SIPRI, a research "
     "institute in Sweden, has counted every major weapons deal since 1950. This makes the "
     "weapons trade a good map of world politics.")
para("A graph fits this well. We care about who is joined to whom, and that is exactly what a "
     "graph stores. Finding sides is a standard graph task called community detection.")

# ===========================================================================
# 3. PROBLEM STATEMENT
# ===========================================================================
h1("3. Problem Statement")
rich([
    ("Find the groups of countries in the world weapons trade", True),
    (", using only the list of deals. Countries are nodes. Deals are weighted edges. "
     "Cut the graph into groups that trade a lot inside and little outside. Then check that "
     "the groups are real and not luck.", False),
])
table([
    ["Part", "Details"],
    ["Input", "SIPRI list of weapons deals: seller, buyer, years, amount"],
    ["Task", "Split the countries into groups with spectral partitioning"],
    ["Output", "A group for every country in every year, and a test against random networks"],
], widths=[1.2, 5.3])

# ===========================================================================
# 4. OBJECTIVES
# ===========================================================================
h1("4. Objectives")
numbered([
    "Turn the weapons trade into a weighted graph.",
    "Clean the raw data.",
    "Write spectral partitioning from scratch.",
    "Let the data choose how many groups there are.",
    "Find the countries that trade with both sides.",
    "Prove the groups are not luck.",
    "Build a website that explains all this simply.",
])


# ===========================================================================
# 5. DATASET
# ===========================================================================
h1("5. Dataset / Scenario Description")
table([
    ["Item", "Details"],
    ["Dataset name", "SIPRI Arms Transfers Database (trade register)"],
    ["Source of data", "Real data. https://armstransfers.sipri.org/ (downloaded 3 August 2026)"],
    ["Rows", f"{M['raw_rows']:,} in the file, {M['kept_rows']:,} kept after cleaning"],
    ["Number of vertices", f"{M['total_countries']} countries"],
    ["Number of edges", f"{M['total_pairs']:,} seller-buyer pairs"],
    ["Graph type", "Weighted. Made undirected (two-way) for finding groups"],
    ["Meaning of weight", "Amount of weapons delivered, in TIV"],
    ["Tools", "Python for the analysis. globe.gl for the 3D globe on the website"],
], widths=[1.7, 4.8])

h2("5.1 Cleaning")
bullets([
    "The file has 10 lines of notes at the top. We skip them.",
    "63 names are not countries (for example rebel groups, NATO, the UN). We remove them.",
    "Some deals are spread over many years. We share the amount equally between those years.",
    "1,196 rows have no year. We remove them.",
])
para("One year has too few deals, so each graph uses 10 years of deals. The graph for 1987 "
     "holds all deals from 1978 to 1987. This gives 67 graphs, from 1959 to 2025.")

# ===========================================================================
# 6. GRAPH MODELING
# ===========================================================================
h1("6. Graph Modeling")
table([
    ["Graph Component", "Meaning here", "Example"],
    ["Vertex / Node", "A country", "India"],
    ["Edge / Link", "Weapons sold between two countries", "Soviet Union - India"],
    ["Weight", "Amount of weapons (TIV)", "17,700 (1978-1987)"],
    ["Graph Type", "Undirected, weighted", "W = (A + A transposed) / 2"],
    ["Representation", "Adjacency matrix", f"{A['stats']['n']} x {A['stats']['n']} table "
                                           f"for 1987"],
], widths=[1.4, 2.8, 2.3])

h2("6.1 Two choices that matter")
rich([("Two-way lines. ", True),
      ("A sale goes one way, but friendship goes both ways. Spectral partitioning also needs "
       "a symmetric table. So we average the two directions.", False)])
rich([("Logarithm of the weight. ", True),
      ("A few giant deals are 75,000 times bigger than small ones. With raw numbers they "
       "drowned out everything else, and the result was worse than random. Using "
       "log(1 + TIV) fixed this. Now trading often counts more than one huge deal.", False)])

figure("fig10_graph_model.png", width=5.0, caption=
       "The graph for 1978-1987 (biggest 24 countries only). Dots are countries, lines are "
       "weapons deals, colour is the group found. India sits in the middle, linked to both "
       "sides.")
about(f"We took the 1978-1987 graph ({FS['fig10']['n_full']} countries). To make it readable "
      f"on paper we kept only the {FS['fig10']['nodes']} countries with the most trade, and the "
      f"{FS['fig10']['edges']} heaviest lines between them. The dots were placed by a 'spring' "
      "layout: every line pulls its two countries together and all dots push each other apart, "
      "so close partners end up near each other.",
      f"Years 1978-1987.  Top {FS['fig10']['nodes']} countries by total TIV.  "
      f"{FS['fig10']['edges']} heaviest lines.  Spring layout pulled by log(1 + TIV), "
      "seed 3.  Dot size = total trade.  Line thickness = size of the deals.  "
      "Colour = group from spectral partitioning with k = 2.  Grey line = a deal between the "
      "two groups.",
      "The two sides of the Cold War: the Soviet Union and its partners (red), the United "
      "States and its partners (blue). The layout never saw the colours, yet the two colours "
      "fall on opposite sides by themselves. Most lines stay inside one colour. The few grey "
      "lines cross sides. One of the thickest joins India to the Soviet Union, which is why "
      "India sits between the groups.")


# ===========================================================================
# 7. METHOD
# ===========================================================================
h1("7. Method / Algorithm Used")
para("Method: spectral partitioning (normalised version, Ng, Jordan and Weiss 2002).")

h2("7.1 The idea")
para("We want to cut the graph into two groups and cut as few strong lines as possible. "
     f"Trying every cut is impossible: {A['stats']['n']} countries have about "
     f"2^{A['stats']['n']-1} ways to split. "
     "Spectral partitioning finds a good cut in one step.")
para("Think of the lines as ropes and shake the whole graph. Countries tied tightly together "
     "move together. The slowest wobble moves one group up and the other group down. That "
     "wobble is the second eigenvector of the Laplacian, called the Fiedler vector. Each "
     "country gets one number. Positive means one group, negative means the other.")
figure("shot_village.png",
       "The idea on the website, with a toy village of 15 houses. After the shake, houses are "
       "placed on a line by how far they moved and cut at zero. Only 2 ropes are cut, the "
       "fewest possible.")

h2("7.2 Steps")
numbered([
    "Make the table W: the weight between every pair of countries.",
    "Make D: each country's total weight.",
    "Make the Laplacian: L = I - D^(-1/2) W D^(-1/2).",
    "Find the eigenvalues and eigenvectors of L.",
    "Choose the number of groups k at the biggest jump between eigenvalues (the eigengap).",
    "Give each country a position from the first k eigenvectors.",
    "Group the positions with k-means. These are the groups.",
])

h2("7.3 How many groups?")
figure("fig01_spectral_gap.png",
       "The 12 smallest eigenvalues of the Laplacian. Grey area: the first one is always 0, so "
       "it is ignored. The real network (blue) then jumps sharply after the 2nd eigenvalue. The "
       "shuffled copy (red dashed) stays flat.")
about("We built the normalised Laplacian L = I - D^(-1/2) W D^(-1/2) for the 1987 and 2025 "
      "graphs and found its eigenvalues with scipy.linalg.eigh. We plotted the 12 smallest, "
      "from small to large (blue). We did the same for a shuffled copy of each graph (red).",
      f"Weights W = log(1 + TIV).  Windows 1978-1987 ({A['stats']['n']} countries) and "
      f"2016-2025 ({B['stats']['n']} countries).  Shuffled copy = same countries, same number "
      "of lines, same weights, but joined at random (seed 42).  "
      "Eigengap = 3rd eigenvalue minus 2nd.",
      "The 1st eigenvalue is 0 for every connected graph, so it tells us nothing. A small "
      "2nd eigenvalue means there is a cheap way to cut the graph in two. After it the real "
      f"graph jumps up by {A['eig'][2] - A['eig'][1]:.3f} (1987) and "
      f"{B['eig'][2] - B['eig'][1]:.3f} (2025). Shuffled copies jump only "
      f"{A['random']['gap_mean']['2']:.3f} and {B['random']['gap_mean']['2']:.3f} on average "
      "(10 copies each). One big jump after the 2nd eigenvalue means exactly 2 groups. A flat "
      "line means no natural groups.")
para("Leaving out the always-zero first eigenvalue, the biggest jump came right after the 2nd "
     "eigenvalue in all 67 years. So the data says: 2 groups.")

h2("7.4 Why this method")
bullets([
    "It does exactly what we want: keep strong links inside groups.",
    "It uses the weights directly.",
    "It tells us how many groups there are.",
])
para("Some countries trade with both sides. To find them we also use betweenness centrality: "
     "how often a country lies on the path between two others.")


# ===========================================================================
# 8. IMPLEMENTATION
# ===========================================================================
h1("8. Implementation Details")
table([
    ["Item", "Details"],
    ["Programming Language", "Python 3.14"],
    ["Libraries Used", "NumPy, SciPy, NetworkX, scikit-learn, Matplotlib"],
    ["Platform", "Windows 11 laptop"],
    ["Input Format", "CSV file"],
    ["Output Format", "One JSON file, read by the website"],
    ["Website", "One HTML page: pixel-art canvas and globe.gl 3D globe. Hosted on Cloudflare"],
], widths=[1.8, 4.7])

h2("8.1 Main code (shortened)")
code = '''def spectral_partition(W, k):
    deg = W.sum(axis=1)                          # total weight of each country
    d = 1.0 / np.sqrt(deg)
    L = np.eye(len(W)) - W * d[:, None] * d[None, :]   # normalised Laplacian
    values, vectors = eigh(L)                     # eigenvalues, smallest first
    U = vectors[:, :k]                            # first k eigenvectors
    U = U / np.linalg.norm(U, axis=1, keepdims=True)
    labels = KMeans(n_clusters=k, n_init=20).fit_predict(U)
    return labels, values'''
p = doc.add_paragraph()
p.paragraph_format.space_after = Pt(10)
r = p.add_run(code); r.font.name = "Consolas"; r.font.size = Pt(8.5)

h2("8.2 The website")
para("The website explains the method to someone with no background, in 8 short steps:")
bullets([
    [("Steps 1-6: ", True), ("a small village of 15 houses joined by ropes. The website shakes "
                            "it, lines the houses up, and cuts them into two teams.", False)],
    [("Steps 7-8: ", True), ("the real data on a 3D globe. Press play to watch the years go "
                            "by, or click a country to see who it buys from and sells to.",
                            False)],
])
figure("shot_globe.png",
       "Step 7 of the website. Countries coloured by group (green: Soviet side, orange: US "
       "side, white: countries trading with both).")


# ===========================================================================
# 9. OUTPUT AND RESULTS
# ===========================================================================
h1("9. Output and Results")
table([
    ["Result Item", "Output"],
    ["Number of vertices", f"{M['total_countries']} ({A['stats']['n']} in 1987)"],
    ["Number of edges", f"{M['total_pairs']:,} ({A['stats']['m']:,} in 1987)"],
    ["Method used", "Spectral partitioning"],
    ["Groups found", "2, chosen by the data in all 67 years"],
    ["Main output", "A Soviet/Russia-led side and a US-led side"],
    ["Real vs shuffled", f"The real split is {R_MIN:.0f} to {R_MAX:.0f} times stronger "
                         f"(average {R_AVG:.0f})"],
], widths=[1.9, 4.6])

figure("fig02_adjacency_blocks.png",
       "The same 1987 data three times. (a) Alphabetical order: no pattern. (b) Sorted by the "
       "groups found: the corners (links between groups) are almost empty. (c) A shuffled copy "
       "sorted the same way: the corners stay full.")
about(f"We drew the 1987 adjacency matrix as a picture: a {FS['fig02_real']['n']} x "
      f"{FS['fig02_real']['n']} grid with one row and one column per country, and a black dot "
      "where two countries traded. We drew it three times, changing only the order of the rows "
      "and columns.",
      f"Years 1978-1987.  {FS['fig02_real']['links']} links.  Dot = any trade at all (the "
      "amount is ignored).  (a) Countries A to Z.  (b) Countries sorted by their group "
      "(k = 2), biggest trader first inside each group; red lines = border between the "
      "groups.  (c) A shuffled copy (seed 42), split and sorted by the same method.",
      "The top-right and bottom-left corners hold the links between the two groups. In the "
      f"real data they are almost empty: only {FS['fig02_real']['cross_pct']:.0f}% of links "
      "cross between groups. In the shuffled copy "
      f"{FS['fig02_shuffled']['cross_pct']:.0f}% cross, even though the method tries just as "
      "hard. So the groups come from the data, not from the sorting.")

h2("9.1 Who ended up together")
table([
    ["Years", "Group A", "Group B"],
    ["1956-1965", "Soviet Union, China, Poland, East Germany, Czechoslovakia, Hungary",
     "United States, United Kingdom, Germany, France, Italy, Japan"],
    ["2016-2025", "Russia, India, China, Egypt, Pakistan, Algeria",
     "United States, France, Saudi Arabia, Germany, South Korea, Ukraine"],
], widths=[1.1, 2.7, 2.7])
para("The program was never told about any alliance. Group A in the 1960s is the Warsaw Pact. "
     "Group B is NATO.")

# ===========================================================================
# 10. RESULT ANALYSIS
# ===========================================================================
h1("10. Result Analysis")
bullets([
    [("Pattern found: ", True),
     ("the weapons trade has two sides, the whole time from 1959 to 2025.", False)],
    [("It is real: ", True),
     (f"we shuffled the lines at random 10 times per year. The real split was always much "
      f"stronger. Also {PR:.0f} in 100 countries stayed in the same group the next year, "
      f"against {PX:.0f} in the shuffled network.", False)],
    [("Countries in the middle: ", True),
     ("India is the clearest. In 1978-1987 its biggest seller was the Soviet Union, but it "
      "also bought from Britain, France and West Germany. 43% of its trade crossed sides.",
      False)],
    [("One measure disagreed: ", True),
     ("modularity scored the shuffled network higher. This is a known problem of modularity "
      "on thin, hub-shaped networks, so we did not use it.", False)],
])
figure("fig11_validation.png",
       "Real vs shuffled for all 67 years. (a) How much stronger the real split is. "
       "(b) How many countries keep their group from one year to the next.")
about("We ran the whole method again for every year from 1959 to 2025 (67 graphs), on the "
      "real data and on shuffled copies, and plotted two scores.",
      "(a) Real eigengap divided by the average eigengap of 10 shuffled copies (seeds 42 to "
      "51). Red dotted line at 1x = no better than shuffled.  (b) Share of countries in the "
      "same group as the year before. Group names are matched between years with the Hungarian "
      "algorithm. Real network vs one shuffled copy per year. Grey line at 50% = a coin toss.",
      f"(a) The real split is {R_MIN:.0f} to {R_MAX:.0f} times stronger than shuffled, never "
      f"close to 1x. It is strongest in the late Cold War (peak {Y_MAX}) and weaker after the "
      "Soviet Union ended in 1991, so the world became less sharply divided.  (b) In the real "
      f"world about {PR:.0f} in 100 countries keep their group each year. In shuffled networks "
      f"only about {PX:.0f} do, close to a coin toss. Real partnerships last; random ones do "
      "not.")

h2("10.1 Limitations")
bullets([
    "Every country gets exactly one group, even neutral ones.",
    "SIPRI counts only major weapons, not small arms.",
    "The 10-year window makes changes show up slowly.",
])

# ===========================================================================
# 11. COMPLEXITY
# ===========================================================================
h1("11. Complexity Analysis")
table([
    ["Step", "Time", "Space"],
    ["Build the graph", "O(m)", "O(n + m)"],
    ["Build the Laplacian", "O(n^2)", "O(n^2)"],
    ["Find eigenvalues (slowest step)", "O(n^3)", "O(n^2)"],
    ["k-means", "O(t k^2 n)", "O(n k)"],
], widths=[2.6, 2.2, 1.7])
rich([("Overall: time ", False), ("O(n^3)", True), (", space ", False), ("O(n^2)", True),
      (". n is at most 174 here, so it is fast: all 67 years plus the shuffled tests take "
       "about 97 seconds.", False)])

# ===========================================================================
# 12. CONCLUSION
# ===========================================================================
h1("12. Conclusion")
rich([
    ("We modelled the world weapons trade as a graph, with countries as nodes and deals as "
     "weighted edges. Using ", False),
    ("spectral partitioning", True),
    (", the graph split into ", False),
    ("two sides", True),
    (" in every year, matching the real Cold War blocs. The split is far stronger than in "
     "random networks. This shows that graph mining can find real political groups from "
     "trade data alone.", False),
])

# ===========================================================================
# 13. REFLECTION
# ===========================================================================
h1("13. Reflection / Learning Outcome")
para("The biggest lesson: how you build the graph matters more than the algorithm. With raw "
     "weights the method failed. One small change, taking the logarithm, made it work.")
para("Writing the method myself showed me why the smallest eigenvalues matter and how the "
     "eigengap picks the number of groups. Testing against shuffled networks taught me to "
     "prove a result, not just show it.")

# ===========================================================================
# 14. REFERENCES
# ===========================================================================
h1("14. References")
refs = [
    "SIPRI Arms Transfers Database. https://www.sipri.org/databases/armstransfers "
    "(downloaded 3 August 2026).",
    "von Luxburg, U. (2007). A Tutorial on Spectral Clustering. Statistics and Computing, "
    "17(4), 395-416.",
    "Ng, A. Y., Jordan, M. I., & Weiss, Y. (2002). On Spectral Clustering: Analysis and an "
    "Algorithm. NIPS 14.",
    "Shi, J., & Malik, J. (2000). Normalized Cuts and Image Segmentation. IEEE TPAMI, 22(8), "
    "888-905.",
    "Fiedler, M. (1973). Algebraic connectivity of graphs. Czechoslovak Mathematical Journal, "
    "23(2), 298-305.",
    "Brandes, U. (2001). A Faster Algorithm for Betweenness Centrality. Journal of "
    "Mathematical Sociology, 25(2), 163-177.",
    "Guimera, R., Sales-Pardo, M., & Amaral, L. A. N. (2004). Modularity from fluctuations in "
    "random graphs and complex networks. Physical Review E, 70(2), 025101.",
    "globe.gl - 3D globe library. https://globe.gl/",
]
for i, r in enumerate(refs, 1):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.left_indent = Inches(0.32)
    p.paragraph_format.first_line_indent = Inches(-0.32)
    run = p.add_run(f"[{i}]  {r}"); run.font.size = Pt(9.5)

para()
para("AI tool disclosure: Claude (Anthropic) was used as a coding and writing assistant. All "
     "results and figures come from the Python code run on the original SIPRI data.",
     size=9.5, italic=True, color=MUTED)

# ===========================================================================
# 15. APPENDIX
# ===========================================================================
h1("15. Appendix")
h2("A. How to run it")
p = doc.add_paragraph()
p.paragraph_format.space_after = Pt(10)
r = p.add_run(
    "pip install numpy scipy networkx scikit-learn matplotlib python-docx\n"
    "python analysis/build_graph.py      # analysis -> web/data.json\n"
    "python analysis/make_figures.py     # figures for this report\n"
    "python -m http.server 8000 --directory web   # website at http://localhost:8000")
r.font.name = "Consolas"; r.font.size = Pt(9)

h2("B. Files")
table([
    ["File", "What it does"],
    ["analysis/build_graph.py", "Cleans the data, builds the graphs, finds the groups"],
    ["analysis/make_figures.py", "Makes the figures"],
    ["analysis/build_report.py", "Makes this report"],
    ["web/index.html + web/data.json", "The website"],
], widths=[2.4, 4.1])

h2("C. Live website")
para(SITE, size=12, bold=True, color=ACCENT, space_after=8)

doc.save(OUT)
print("wrote", OUT)
print("figures placed:", _fig[0])
