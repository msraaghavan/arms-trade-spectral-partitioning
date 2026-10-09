"""
Screenshots the website for the report.
Needs the local server running:  python -m http.server 8000 --directory web
Writes figures/shot_village.png and figures/shot_globe.png
"""
import os
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIG = os.path.join(ROOT, "figures")
URL = "http://localhost:8000/?step="


def main():
    os.makedirs(FIG, exist_ok=True)
    with sync_playwright() as p:
        br = p.chromium.launch()
        pg = br.new_page(viewport={"width": 1440, "height": 810})

        # 1. the toy village: houses lined up by their wobble and cut at zero (step 4)
        pg.goto(URL + "4")
        pg.wait_for_timeout(8000)
        pg.screenshot(path=os.path.join(FIG, "shot_village.png"))
        print("  wrote shot_village.png")

        # 2. the real data on the 3D globe, two teams coloured (step 7)
        pg.goto(URL + "7")
        pg.wait_for_function("typeof GL!=='undefined'&&!!GL", timeout=90_000)
        pg.wait_for_timeout(7000)
        pg.screenshot(path=os.path.join(FIG, "shot_globe.png"))
        print("  wrote shot_globe.png")

        br.close()


if __name__ == "__main__":
    main()
