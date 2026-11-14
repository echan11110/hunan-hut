#!/usr/bin/env python3
"""Rebuild the Menu JSON-LD in menu/index.html from the visible menu on that page.

Run after ANY menu edit (prices, items, descriptions):
    python3 tools/menu_schema.py           # rewrite the block between the MENU-SCHEMA markers
    python3 tools/menu_schema.py --check   # exit 1 if the block is out of date (no write)

The visible HTML is the single source of truth; this never invents data.
Self-check: every "$X.XX" price inside the menu sections must become exactly one Offer.
Needs BeautifulSoup (pip install beautifulsoup4).
"""
import json, re, sys
from pathlib import Path
from bs4 import BeautifulSoup, NavigableString

PAGE = Path(__file__).resolve().parent.parent / "menu" / "index.html"
START, END = "<!-- MENU-SCHEMA:START", "<!-- MENU-SCHEMA:END -->"
BASE = "https://hunan-hut.com"
CODE = re.compile(r"^([A-Z]{1,2}\d{1,2})\b")
PRICE = re.compile(r"\$(\d+\.\d\d)")
SIZES = {"S": "Small", "M": "Medium", "L": "Large"}
# Sections whose rows only name the protein ("Vegetable", "Combination"): append the dish type.
DISH_TYPE = {"cat-friedrice": "Fried Rice", "cat-lomein": "Lo Mein", "cat-ricenoodle": "Rice Noodle",
             "cat-chowfun": "Chow Fun or Drunken Noodle", "cat-efyoung": "Egg Foo Young"}
LABEL_PREFIXES = ("m_p_", "m_pc", "m_sz_", "m_w", "m_br", "m_lg", "m_th", "m_c_")
# Real photos on the site (homepage Customer Favorites), keyed by menu code / wings item.
IMAGES = {"CS10": "triple-delight", "CF2": "buffalo-wings", "C2": "chicken-broccoli",
          "RN5": "singapore-noodle", "L2": "shrimp-lo-mein", "Wings (Fried Chicken Only)": "wings-mambo"}


def clean(t):
    return " ".join(t.replace(" ", " ").split())


def offers_from(text, label):
    """'$14.95' | 'S $11.50 · L $12.50' | '½ lb $14.95 · 1 lb $27.95' -> [(name|None, '14.95'), ...]"""
    out = []
    for part in text.split("·"):
        m = PRICE.search(part)
        if not m:
            continue
        name = clean(part[:m.start()]) or label
        out.append((SIZES.get(name, name), m.group(1)))
    return out


def build(html):
    soup = BeautifulSoup(html, "html.parser")
    sections, n_prices = [], 0
    for sec in soup.select('main section[id^="cat-"]'):
        sid = sec["id"]
        n_prices += len(PRICE.findall(sec.get_text(" ")))
        title = clean(sec.find(attrs={"data-i18n": re.compile(r"^cat_")}).get_text())
        # section note = the line under the heading; the wings section has none, so use its sauce list
        note = sec.find("h2").parent.find(attrs={"data-i18n": re.compile(r"^note_")})
        note = clean(note.get_text()) if note else None
        sauces = sec.find_all(attrs={"data-i18n": re.compile(r"^m_s_")})
        if not note and sauces:
            extra = sec.find(attrs={"data-i18n": "sauce_extra"})
            note = "Sauce options: " + ", ".join(clean(s.get_text()) for s in sauces) + (f". {clean(extra.get_text())}." if extra else "")
        items, cur, label, group, group_note = [], None, None, None, None
        for el in sec.find_all(True):
            key = el.get("data-i18n", "")
            own = clean("".join(c for c in el.contents if isinstance(c, NavigableString)))
            if key in ("wings_fried_only", "wings_with_sides"):
                group, group_note = clean(el.get_text()), None
            elif key == "note_chicken_special":
                group_note = clean(el.get_text())
            elif key.startswith("m_g_"):
                cur = {"name": f"{clean(el.get_text())} ({group})", "desc": group_note, "offers": []}
                items.append(cur)
            elif el.name == "span" and not key and CODE.match(own):
                cur = {"code": CODE.match(own).group(1), "name": None, "desc": None, "offers": []}
                items.append(cur)
            elif key.startswith(("d_", "m_e_", "m_p_")) and cur is not None and cur["name"] is None:
                # m_p_* is a protein label, except on Egg Foo Young rows where it is the item name
                cur["name"] = clean(el.get_text())
            elif key.startswith("desc") and cur is not None:
                cur["desc"] = clean(el.get_text())
            elif key.startswith(LABEL_PREFIXES):
                label = clean(el.get_text())
            elif el.name == "span" and not key and not el.find(True) and PRICE.search(el.get_text()):
                cur["offers"] += offers_from(el.get_text(), label)
                label = None
        menu_items = []
        for it in items:
            name, desc = it["name"], it["desc"]
            spicy = "🌶" in name
            name = clean(name.replace("🌶️", "").replace("🌶", ""))
            if sid in DISH_TYPE and DISH_TYPE[sid].split()[0].lower() not in name.lower():
                parts = name.split(" / ")
                name = (", ".join(parts[:-1]) + ", or " + parts[-1] if len(parts) > 1 else name) + f" {DISH_TYPE[sid]}"
            if spicy:
                desc = f"{desc}. Spicy." if desc else "Spicy."
            mi = {"@type": "MenuItem", "name": name}
            if it.get("code"):
                mi["identifier"] = it["code"]
            if desc:
                mi["description"] = desc
            img = IMAGES.get(it.get("code")) or IMAGES.get(it["name"])
            if img:
                mi["image"] = f"{BASE}/images/menu/{img}.jpg"
            offers = [{"@type": "Offer", **({"name": n} if n else {}), "price": p, "priceCurrency": "USD"}
                      for n, p in it["offers"]]
            assert offers, f"{sid}: no price found for {name!r}"
            assert len(offers) == 1 or all("name" in o for o in offers), f"{sid}: unlabeled price option on {name!r}"
            mi["offers"] = offers[0] if len(offers) == 1 else offers
            menu_items.append(mi)
        ms = {"@type": "MenuSection", "name": title, "url": f"{BASE}/menu/#{sid}"}
        if note:
            ms["description"] = note
        ms["hasMenuItem"] = menu_items
        sections.append(ms)
    n_offers = sum(len(i["offers"]) if isinstance(i["offers"], list) else 1
                   for s in sections for i in s["hasMenuItem"])
    assert n_offers == n_prices, f"self-check failed: {n_prices} prices on the page, {n_offers} offers in schema"
    assert len(sections) >= 10, "menu sections not found"
    menu = {"@context": "https://schema.org", "@type": "Menu", "@id": f"{BASE}/menu/#menu",
            "name": "Hunan Hut Menu", "url": f"{BASE}/menu/", "inLanguage": "en",
            "description": "Carry-out menu for Hunan Hut, 7967 New Hampshire Ave, Adelphi, MD. All menu prices include tax. Delivery app prices are higher.",
            "provider": {"@id": f"{BASE}/#restaurant"}, "hasMenuSection": sections}
    block = (f'{START} generated by tools/menu_schema.py from the menu below; do not edit by hand -->\n'
             f'  <script type="application/ld+json">{json.dumps(menu, ensure_ascii=False, separators=(",", ":"))}</script>\n'
             f'  {END}')
    return block, len(sections), sum(len(s["hasMenuItem"]) for s in sections), n_offers


def main():
    html = PAGE.read_text(encoding="utf-8")
    block, n_sec, n_items, n_offers = build(html)
    if START in html:
        a, b = html.index(START), html.index(END) + len(END)
        new = html[:a] + block + html[b:]
    else:  # first run: end of <body>, so the 30 KB of JSON never delays rendering
        anchor = "</body>"
        assert html.count(anchor) == 1
        new = html.replace(anchor, "  " + block + "\n" + anchor)
    if "--check" in sys.argv:
        ok = new == html
        print(("up to date" if ok else "OUT OF DATE: run python3 tools/menu_schema.py") + f" ({n_sec} sections, {n_items} items, {n_offers} prices)")
        sys.exit(0 if ok else 1)
    PAGE.write_text(new, encoding="utf-8")
    print(f"wrote Menu JSON-LD: {n_sec} sections, {n_items} items, {n_offers} prices")


if __name__ == "__main__":
    main()
