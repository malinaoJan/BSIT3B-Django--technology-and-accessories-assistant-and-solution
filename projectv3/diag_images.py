"""Diagnostic: why do wiki/commons candidates get rejected for tile items?

Run from the TECHFIX project root:
    venv\\Scripts\\python.exe projectv3\\manage.py shell -c "exec(open('projectv3/diag_images.py', encoding='utf-8').read())"

Env:
    TECHFIX_DIAG_LIMIT=50   how many tile items to inspect
    TECHFIX_DIAG_OFFSET=0
"""
import os
import re

os.environ.setdefault("TECHFIX_IMG_NO_RUN", "1")
# keep fetch_wiki_images.py's main loop from processing anything while we borrow
# its helpers (empty brand match => no targets)
os.environ.setdefault("TECHFIX_WIKI_BRANDS", "__diag__")

_helpers = globals()
with open("projectv3/fetch_wiki_images.py", encoding="utf-8") as _fh:
    exec(_fh.read(), _helpers)

LIMIT = int(os.environ.get("TECHFIX_DIAG_LIMIT", "40"))
OFFSET = int(os.environ.get("TECHFIX_DIAG_OFFSET", "0"))


def load_seed(path, var):
    namespace = {}
    with open(path, encoding="utf-8") as handle:
        exec(handle.read(), namespace)
    return namespace[var]


OP = load_seed("projectv3/old_products_data.py", "OLD_PRODUCTS")
OA = load_seed("projectv3/old_accessories_data.py", "OLD_ACCESSORIES")

targets = []
for brand_key in OP:
    for it in OP[brand_key]:
        obj = Product.objects.filter(name=it[1]).first()
        if obj and obj.image and "_tile_" in obj.image.name:
            targets.append(obj)
for brand_key in OA:
    for it in OA[brand_key]:
        obj = Accessory.objects.filter(name=it[1]).first()
        if obj and obj.image and "_tile_" in obj.image.name:
            targets.append(obj)

targets = targets[OFFSET:OFFSET + LIMIT]
print(f"inspecting {len(targets)} tile items", flush=True)

miss_counts = {}
digit_rejects = 0

for obj in targets:
    name = obj.name
    brand = obj.brand or ""
    year = item_year(name)
    query = re.sub(r"\s+", " ", re.sub(r"\([^)]*\)", " ", name)).strip()
    cleaned_query, removed = strip_size_period(query)
    removed_tokens = tokens(removed)
    optional_tokens = set(removed_tokens)
    size_tokens = {t for t in removed_tokens if t not in OPTIONAL_PERIOD_WORDS}
    qtok = list(dict.fromkeys(tokens(cleaned_query)))
    anchors = brand_anchor(brand)
    required = [t for t in qtok if t not in anchors and t not in optional_tokens]

    try:
        cands = wiki_search(cleaned_query)
    except Exception as exc:
        print(f"!! {name}: wiki search error {exc}", flush=True)
        continue
    try:
        cands += wiki_exact(cleaned_query)
    except Exception:
        pass

    if best_candidate(brand, cleaned_query, cands, year, optional_tokens, size_tokens):
        print(f"OK  {name}", flush=True)
        continue

    # find the closest candidate and why it fails
    shown = 0
    print(f"--  {name}  (required: {required})", flush=True)
    for title, url in cands[:4]:
        low = " " + title.lower() + " "
        if any(bad in low for bad in CANDIDATE_BAD):
            print(f"      reject(bad-word)   {title}", flush=True)
            continue
        tset = set(tokens(title))
        missing = [t for t in required if t not in tset]
        extra = [t for t in tset if t not in set(qtok) and t not in optional_tokens]
        anchor_hit = bool(anchors & tset)
        digit_extra = any(any(ch.isdigit() for ch in t) or t in VARIANT_WORDS for t in extra)
        for t in missing:
            miss_counts[t] = miss_counts.get(t, 0) + 1
        print(f"      {title} | missing={missing} | extra={extra} "
              f"| anchor={anchor_hit} | variant/digit={digit_extra}", flush=True)
        shown += 1
        if shown >= 3:
            break

print("\n=== most common MISSING required tokens ===", flush=True)
for tok, cnt in sorted(miss_counts.items(), key=lambda kv: -kv[1])[:40]:
    print(f"  {cnt:4d}  {tok}", flush=True)
