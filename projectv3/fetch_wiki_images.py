"""Attach real photos from Wikipedia article infoboxes to legacy items.

Used for brands where Wikimedia Commons *search* did not find an exact file but
Wikipedia has an article with a lead image (e.g. "Apple TV HD", "IPad Air 2").

It reuses the matching helpers of fetch_old_images.py (loaded with its main loop
disabled) and by default only replaces placeholder tiles, never good photos.

Run from the TECHFIX project root:
    venv\\Scripts\\python.exe manage.py shell -c "exec(open('projectv3/fetch_wiki_images.py', encoding='utf-8').read())"

Env knobs:
    TECHFIX_WIKI_BRANDS=apple,Acer,...   brand keys to process (default: all)
    TECHFIX_WIKI_DRY=1                   only report, do not download/save
    TECHFIX_WIKI_INCLUDE_PHOTOS=1        also replace existing photos (default: tiles only)
"""
import json
import os
import re
import time

os.environ.setdefault("TECHFIX_IMG_NO_RUN", "1")

# load the helper module without triggering its main loop
_helpers = globals()
with open("projectv3/fetch_old_images.py", encoding="utf-8") as _fh:
    exec(_fh.read(), _helpers)

WIKI = "https://en.wikipedia.org/w/api.php"


def wiki_search(query, limit=10):
    key = f"WIKI|{query}|{limit}"
    if key in _SEARCH_CACHE:
        return _SEARCH_CACHE[key]
    raw = fetch(WIKI, {
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": query, "gsrnamespace": 0, "gsrlimit": limit,
        "prop": "pageimages", "piprop": "original|thumbnail", "pithumbsize": 900,
        "redirects": 1,
    })
    data = json.loads(raw)
    out = []
    for page in ((data.get("query") or {}).get("pages") or {}).values():
        source = (page.get("original") or {}).get("source")
        if not source:
            source = (page.get("thumbnail") or {}).get("source")
        title = page.get("title", "")
        if source and not source.lower().endswith(".svg"):
            out.append((title, source))
    _SEARCH_CACHE[key] = out
    _save_cache()
    return out


def load_seed(path, var):
    namespace = {}
    with open(path, encoding="utf-8") as handle:
        exec(handle.read(), namespace)
    return namespace[var]


OP = load_seed("projectv3/old_products_data.py", "OLD_PRODUCTS")
OA = load_seed("projectv3/old_accessories_data.py", "OLD_ACCESSORIES")

brands_env = os.environ.get("TECHFIX_WIKI_BRANDS", "")
brands = [b.strip() for b in brands_env.split(",") if b.strip()] or list(OP.keys())
DRY = os.environ.get("TECHFIX_WIKI_DRY") == "1"
INCLUDE_PHOTOS = os.environ.get("TECHFIX_WIKI_INCLUDE_PHOTOS") == "1"

product_names = {it[1] for b, items in OP.items() for it in items}
accessory_names = {it[1] for b, items in OA.items() for it in items}

targets = []
for brand_key in brands:
    for it in OP.get(brand_key, []):
        obj = Product.objects.filter(name=it[1]).first()
        if obj:
            targets.append(obj)
    for it in OA.get(brand_key, []):
        obj = Accessory.objects.filter(name=it[1]).first()
        if obj:
            targets.append(obj)

if not INCLUDE_PHOTOS:
    targets = [o for o in targets if not o.image or "_tile_" in o.image.name]

wiki_limit = int(os.environ.get("TECHFIX_WIKI_LIMIT", "0")) or None
wiki_offset = int(os.environ.get("TECHFIX_WIKI_OFFSET", "0"))
targets = targets[wiki_offset:]
if wiki_limit:
    targets = targets[:wiki_limit]

print(f"brands: {brands}", flush=True)
print(f"tile (or empty) items to try: {len(targets)}", flush=True)

stats = {"photo": 0, "kept": 0, "failed": 0}
for index, obj in enumerate(targets, 1):
    name = obj.name
    brand = obj.brand or ""
    year = item_year(name)
    query = re.sub(r"\s+", " ", re.sub(r"\([^)]*\)", " ", name)).strip()

    net_before = _NETWORK_HITS
    candidates = []
    try:
        candidates += wiki_search(query)
    except Exception as exc:
        print(f"  ! wiki search failed for {name}: {exc}", flush=True)
    candidates = list(dict.fromkeys(tuple(c) for c in candidates))

    match = best_candidate(brand, query, candidates, year)
    if not match:
        stats["kept"] += 1
        print(f"[{index}/{len(targets)}] keep  {name}", flush=True)
    else:
        _, title, url = match
        if DRY:
            stats["photo"] += 1
            print(f"[{index}/{len(targets)}] WIKI  {name} <- {title}", flush=True)
        else:
            try:
                save_image(obj, fetch(url, binary=True), folder_for(obj), "photo")
                stats["photo"] += 1
                print(f"[{index}/{len(targets)}] PHOTO {name} <- {title}", flush=True)
            except Exception as exc:
                stats["failed"] += 1
                print(f"[{index}/{len(targets)}] FAIL  {name}: {exc}", flush=True)

    if _NETWORK_HITS != net_before:
        time.sleep(2.0)

print("done:", stats, flush=True)
