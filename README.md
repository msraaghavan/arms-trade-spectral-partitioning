# Analyzing Global Arms Trade using Spectral Partitioning

**23CSE451 Graph Mining – Case Study**
Amrita School of Computing, Amritapuri · CSE-D · Semester VII, 2026–27

| Name | Roll number |
|---|---|
| Raaghavan M S | AM.SC.U4CSE23330 |
| V Sriman Vashishta | AM.SC.U4CSE23368 |

We turned the SIPRI arms-transfer data (1950–2025) into 67 yearly graphs, where countries are nodes and weapon deals are weighted edges. We then used spectral partitioning to split each graph into groups. The data picks two groups in every year, and these match the real Cold War sides. To check that the split is real, we compared it with randomly shuffled networks.

**Live website:** https://arms.armstrade.workers.dev

## Folder contents

```
Graph Mining/
├── Graph_Mining_Case_Study_Report.docx      the report
├── Arms_Trade_Spectral_Partitioning.pptx    the presentation (7 slides, with speaker notes)
├── README.md
├── requirements.txt
├── data/
│   └── sipri_trade_register.csv             raw SIPRI Arms Transfers data
├── analysis/
│   ├── build_graph.py                       cleans the data, builds the graphs, finds the groups
│   ├── country_coords.py                    country locations for the globe
│   ├── make_figures.py                      makes the report figures
│   ├── build_report.py                      makes the report
│   └── shoot_site.py                        takes the website screenshots used in the report
├── figures/                                 figures used in the report and slides
└── web/
    ├── index.html                           the interactive website
    └── data.json                            results produced by build_graph.py
```

## How to run

```bash
pip install -r requirements.txt
python analysis/build_graph.py                  # data -> web/data.json
python analysis/make_figures.py                 # figures/
python -m http.server 8000 --directory web      # website at http://localhost:8000
```

You need the local server for the website because `index.html` loads `data.json`. If you open the file directly by double-clicking it, the data will not load.
