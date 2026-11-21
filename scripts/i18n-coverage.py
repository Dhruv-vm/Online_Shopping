#!/usr/bin/env python3
"""Measure multilingual coverage (final cycle, Part 11).

1. Dictionary completeness: keys present in each locale vs en.json.
2. UI wiring: per area, visible strings that go through t()/tActive vs strings
   hard-coded in JSX (text nodes and placeholder/title/aria-label/alt literals).
Usage: scripts/i18n-coverage.py [--json] [--list AREA]
"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "frontend"
LOC = ROOT / "locales"
AREAS = {
    "checkout": ["app/checkout", "app/cart", "components/checkout"],
    "orders": ["app/orders"],
    "account": ["app/account", "components/account", "components/intent"],
    "catalogue": ["app/products", "app/categories", "app/retailers", "app/compare", "components/catalogue", "components/products"],
    "marketplace": ["app/community-buying", "app/auctions", "app/exchange", "app/missions", "app/list-to-basket", "app/assistant", "components/phase3"],
    "retailer": ["app/retailer", "components/retailer"],
    "admin": ["app/admin"],
    "shell": ["app/page.tsx", "app/login", "app/register", "components/shared", "components/auth"],
}
TEXT = re.compile(r">\s*([^<>{}\n]*[A-Za-z]{2,}[^<>{}\n]*?)\s*<")
ATTR = re.compile(r'\b(?:placeholder|title|aria-label|alt)="([^"]*[A-Za-z]{2,}[^"]*)"')
TCALL = re.compile(r"\b(?:t|tActive)\(\s*[\"'`]")
IGNORE = re.compile(r"^(?:&[a-z]+;|[A-Z]{2,5}|BASKET|Basket|GSTIN|UPI|PIN|OTP|SKU|HSN|ID|OK|₹)$")


def files(paths):
    for p in paths:
        f = ROOT / p
        if f.is_file():
            yield f
        elif f.is_dir():
            yield from (x for x in f.rglob("*.tsx") if ".test." not in x.name)


def scan(f):
    src = f.read_text(encoding="utf-8")
    # drop comments
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    src = re.sub(r"(?m)^\s*//.*$", "", src)
    hard = [m.strip() for m in TEXT.findall(src) if not IGNORE.match(m.strip())]
    hard += [m for m in ATTR.findall(src) if not IGNORE.match(m)]
    return len(TCALL.findall(src)), hard


def main():
    en = json.loads((LOC / "en.json").read_text())
    langs = sorted(p.stem for p in LOC.glob("*.json") if p.stem != "core-keys")
    dict_cov = {}
    for l in langs:
        d = json.loads((LOC / f"{l}.json").read_text())
        dict_cov[l] = round(100 * sum(1 for k in en if k in d) / len(en), 1)
    areas, tot_t, tot_h = {}, 0, 0
    detail = {}
    for a, paths in AREAS.items():
        nt = nh = 0
        hs = []
        for f in files(paths):
            t, h = scan(f)
            nt += t
            nh += len(h)
            hs += [(str(f.relative_to(ROOT)), x) for x in h]
        areas[a] = {"t_calls": nt, "hardcoded": nh, "wired_pct": round(100 * nt / (nt + nh), 1) if nt + nh else 100.0}
        detail[a] = hs
        tot_t += nt
        tot_h += nh
    overall = round(100 * tot_t / (tot_t + tot_h), 1) if tot_t + tot_h else 100.0
    out = {"en_keys": len(en), "dictionary_pct": dict_cov, "areas": areas, "overall_wired_pct": overall}
    if "--list" in sys.argv:
        a = sys.argv[sys.argv.index("--list") + 1]
        for f, s in detail[a]:
            print(f"{f}: {s}")
        return
    if "--json" in sys.argv:
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return
    print(f"en keys: {len(en)}")
    print("dictionary completeness:", ", ".join(f"{l} {p}%" for l, p in dict_cov.items()))
    for a, v in areas.items():
        print(f"  {a:12s} wired {v['wired_pct']:5.1f}%  (t() {v['t_calls']}, hard-coded {v['hardcoded']})")
    print(f"overall UI wired: {overall}%")


if __name__ == "__main__":
    main()
