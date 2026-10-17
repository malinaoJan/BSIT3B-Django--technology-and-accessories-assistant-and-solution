"""Attach images to the legacy (old) products and accessories.

Strategy (accuracy first):
  1. Search Wikimedia Commons for real photos. A candidate is accepted only when
     EVERY significant model token of the item name appears in the file name and
     the file name does not mention another model or variant that is not ours
     (mini / neo / plus / ultra / other digits ...). This avoids look-alike
     mismatches such as "Galaxy S8" vs "Galaxy Tab S8".
  2. Items without an exact match get a branded placeholder tile drawn with
     Pillow using the site palette (.pt-0..pt-7), so every card still has art.

Run from the TECHFIX project root:
    venv\\Scripts\\python.exe manage.py shell -c "exec(open('projectv3/fetch_old_images.py', encoding='utf-8').read())"

Env knobs (all optional):
    TECHFIX_IMG_LIMIT=50     process at most N items
    TECHFIX_IMG_OFFSET=50    start after the first N items
    TECHFIX_IMG_REDO=1       also redo items that already have an image
    TECHFIX_IMG_REDO_TILES=1 retry only items currently holding a placeholder tile

Only items with an empty image field are touched by default, so re-runs are safe.
"""
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from django.core.files.base import ContentFile
from django.db.models import Q

from apps.core.models import Accessory, Product

UA = "TechFixCatalogBot/1.0 (local educational catalog project; python-urllib)"
LIMIT = int(os.environ.get("TECHFIX_IMG_LIMIT", "0")) or None
OFFSET = int(os.environ.get("TECHFIX_IMG_OFFSET", "0"))
REDO = os.environ.get("TECHFIX_IMG_REDO") == "1"
REDO_TILES = os.environ.get("TECHFIX_IMG_REDO_TILES") == "1"
COMMONS = "https://commons.wikimedia.org/w/api.php"
SLEEP = 1.2          # polite pause between items
RETRIES = 4

# ---------------------------------------------------------------------------
# brand / model matching helpers
# ---------------------------------------------------------------------------

BRAND_ALIASES = {
    "apple": {"apple", "iphone", "ipad", "ipod", "imac", "macbook", "airpods"},
    "samsung": {"samsung", "galaxy", "syncmaster"},
    "xiaomi": {"xiaomi", "redmi", "miband"},
    "huawei": {"huawei", "mate", "nova", "mediapad", "ascend"},
    "oppo": {"oppo"},
    "oneplus": {"oneplus", "one"},
    "vivo": {"vivo"},
    "realme": {"realme"},
    "infinix": {"infinix"},
    "itel": {"itel"},
    "tecno": {"tecno", "camon", "spark", "phantom", "pova"},
    "honor": {"honor"},
    "asus": {"asus", "zenfone", "zenbook", "zenpad", "zenwatch", "transformer", "rog"},
    "acer": {"acer", "aspire", "iconia", "liquid", "predator", "chromebook"},
    "dell": {"dell", "inspiron", "latitude", "xps", "alienware", "vostro",
             "optiplex", "ultrasharp", "venue", "streak"},
    "hp": {"hp", "pavilion", "envy", "elitebook", "probook", "stream",
           "officejet", "deskjet", "compaq", "slate"},
    "lenovo": {"lenovo", "thinkpad", "ideapad", "thinkvision", "vibe", "yoga"},
    "microsoft": {"microsoft", "surface", "lumia", "xbox", "kinect", "lifecam"},
    "google": {"google", "nexus", "pixel", "pixelbook", "chromecast", "home"},
    "lg": {"lg", "tone", "gram"},
    "gigabyte": {"gigabyte", "aivia", "brix", "aero"},
    "msi": {"msi", "trident", "apache", "titan", "prestige", "ghost"},
    "razer": {"razer", "blade", "kraken", "seiren", "nabu", "nostromo", "sabertooth"},
    "redmagic": {"redmagic", "nubia"},
    "canon": {"canon", "eos", "powershot", "ixus", "pixma"},
    "epson": {"epson", "perfection", "powerlite"},
    "tp-link": {"tplink", "tp", "archer", "neffos", "deco"},
    "anker": {"anker", "powercore", "soundcore", "powerline", "roav", "soundbuds"},
    "baseus": {"baseus"},
    "ugreen": {"ugreen"},
    "logitech": {"logitech", "harmony"},
    "jbl": {"jbl", "flip", "xtreme", "pulse"},
    "sony": {"sony", "xperia", "bravia", "alpha", "mdr", "walkman"},
    "techfix": set(),
}

# words that carry no model information and are safe to ignore on both sides
STOP_WORDS = {
    "the", "and", "for", "with", "of", "in", "to", "new", "original", "genuine",
    "inch", "inches", "gen", "series", "edition", "version", "generation",
    "1st", "2nd", "3rd", "4th", "5th", "first", "second", "third", "model",
    "variant", "full", "portable", "digital", "slim", "home",
}

# words that identify a DIFFERENT model when they appear in a file name but not
# in the item name (so the candidate must be rejected)
VARIANT_WORDS = {
    "mini", "neo", "lite", "ultra", "se", "active", "prime", "plus", "max",
    "tab", "note", "studio", "duo", "fold", "flip", "sport", "air", "pro",
    "live", "band", "buds", "inside", "lte", "classic", "touch", "xl",
    "essential", "edge", "play", "watch", "tv", "phone", "tablet", "laptop",
    "ace", "gt", "rs", "t", "x", "s", "a", "c", "nord", "zenfone",
    "magic", "chromebook", "legion", "mate", "nova", "pixelbook", "surface",
    "thinkpad", "ideapad", "aspire", "inspiron", "pavilion", "vaio", "compact",
    "psd", "deluxe", "memorial", "medal", "monument", "military", "camera",
    "royal", "ancient", "bronze", "marble",
    "ii", "iii", "iv", "vi", "vii", "viii", "ix", "xi", "xii", "xiii", "xiv",
    "xv", "xvi", "xvii", "xviii", "xix", "xx", "series", "gen",
}

CANDIDATE_BAD = (
    "logo", "wordmark", "icon", "diagram", "schematic", "patent", "screenshot",
    "manual", "packaging", "poster", "svg", "map", "chart", " vs ", "comparison",
    "teardown", "disassembled", "unboxing", "advert", "box art", "side by side",
    "inside", "sample", "shot on", "portrait mode", "night mode", "internals",
    "disassembly", "motherboard", "pcb", "circuit board", "rear panel",
    "lineage", "bootloop", "rusak", "broken", "damaged", "cracked", "shattered",
    "gnome", "running on", "custom rom", " rom ", "waterdamage", "repair",
    "photo taken", "taken via", "taken with", "photography", "sample photo",
    "camera sample", "low light", "museum", "painting", "statue",
)

GENERIC_SINGLE = {"a", "an", "s", "x", "z", "i", "e", "d", "g", "k", "j", "c", "v", "u"}


def tokens(text, drop_single=True):
    text = (text or "").replace("+", " plus ")
    parts = re.split(r"[^a-z0-9]+", text.lower())
    out = []
    for part in parts:
        if not part or part in STOP_WORDS:
            continue
        if re.fullmatch(r"(19|20)\d{2}", part):
            continue
        # single letters are meaningful model markers (Galaxy S, Pixel C, Xperia L);
        # only the articles are noise
        if drop_single and part in ("a", "an"):
            continue
        out.append(part)
    return out


def item_year(name):
    match = re.search(r"\b(19|20)\d{2}\b", name or "")
    return match.group(0) if match else None


def brand_anchor(brand):
    raw = (brand or "").strip().lower()
    aliases = set(BRAND_ALIASES.get(raw, set()))
    aliases |= set(BRAND_ALIASES.get(raw.replace("-", ""), set()))
    aliases.add(raw.replace("-", ""))
    aliases.add(raw)
    return {a for a in aliases if a}


def has_extra_model_token(extra):
    """True when an extra file-name token means another variant/model."""
    if extra in VARIANT_WORDS:
        return True
    if any(ch.isdigit() for ch in extra):   # other model numbers / flickr ids
        return True
    return False


def evaluate(title, brand, query_tokens, year=None):
    """Return a ranking tuple when the candidate is an exact-model match."""
    low = " " + title.lower() + " "
    if any(bad in low for bad in CANDIDATE_BAD):
        return None
    if year:
        title_years = re.findall(r"\b(?:19|20)\d{2}\b", title)
        if any(y != year for y in title_years):
            return None
    title_tokens = tokens(title)
    title_set = set(title_tokens)
    if not query_tokens:
        return None

    anchors = brand_anchor(brand)
    # brand words act as an anchor to confirm the maker, not as model tokens
    required = [t for t in query_tokens if t not in anchors]
    missing = [t for t in required if t not in title_set]
    if missing:
        return None

    if anchors and not (anchors & title_set):
        return None

    extra = [t for t in title_set if t not in set(query_tokens)]
    if any(has_extra_model_token(t) for t in extra):
        return None

    # fewer extra words = cleaner product shot; "front"/"top" shots preferred
    front_bonus = 1 if ("front" in low or "top" in low) else 0
    return (-len(extra), front_bonus)


def best_candidate(brand, query, candidates, year=None):
    query_tokens = list(dict.fromkeys(tokens(query)))
    best = None
    for title, url in candidates:
        rank = evaluate(title, brand, query_tokens, year)
        if rank is None:
            continue
        if best is None or rank > best[0]:
            best = (rank, title, url)
    return best


# ---------------------------------------------------------------------------
# network helpers
# ---------------------------------------------------------------------------

def fetch(url, params=None, binary=False):
    global _NETWORK_HITS
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    url = urllib.parse.quote(url, safe=":/?#[]@!$&'()*+,;=%")
    last_error = None
    _NETWORK_HITS += 1
    for attempt in range(RETRIES):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=40) as resp:
                data = resp.read()
            return data if binary else data.decode("utf-8", "ignore")
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code == 429:
                wait = 5 * (attempt + 1)
                print(f"    (rate limited, waiting {wait}s)", flush=True)
                time.sleep(wait)
                continue
            raise
        except Exception as exc:
            last_error = exc
            time.sleep(2 * (attempt + 1))
    raise last_error


def commons_search(query, limit=15):
    key = f"{query}|{limit}"
    if key in _SEARCH_CACHE:
        return _SEARCH_CACHE[key]
    raw = fetch(COMMONS, {
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": query, "gsrnamespace": 6, "gsrlimit": limit,
        "prop": "imageinfo", "iiprop": "url|mime", "iiurlwidth": 900,
    })
    data = json.loads(raw)
    out = []
    for page in ((data.get("query") or {}).get("pages") or {}).values():
        info = (page.get("imageinfo") or [{}])[0]
        mime = info.get("mime") or ""
        url = info.get("thumburl") or info.get("url")
        if url and mime in ("image/jpeg", "image/png"):
            out.append((page.get("title", ""), url))
    _SEARCH_CACHE[key] = out
    _save_cache()
    return out


CACHE_PATH = os.environ.get(
    "TECHFIX_IMG_CACHE",
    os.path.join(os.environ.get("TEMP", "."), "techfix_commons_cache.json"),
)


def _load_cache():
    try:
        with open(CACHE_PATH, encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return {}


def _save_cache():
    try:
        with open(CACHE_PATH, "w", encoding="utf-8") as handle:
            json.dump(_SEARCH_CACHE, handle)
    except Exception:
        pass


_SEARCH_CACHE = _load_cache()
_NETWORK_HITS = 0


# ---------------------------------------------------------------------------
# branded placeholder tiles
# ---------------------------------------------------------------------------

PALETTE = {
    0: ("#6366f1", "#4338ca"), 1: ("#0ea5e9", "#0369a1"),
    2: ("#f97316", "#c2410c"), 3: ("#10b981", "#047857"),
    4: ("#ec4899", "#9d174d"), 5: ("#8b5cf6", "#6d28d9"),
    6: ("#f59e0b", "#b45309"), 7: ("#14b8a6", "#0f766e"),
}
FONT_BOLD = [r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\seguisb.ttf",
             r"C:\Windows\Fonts\calibrib.ttf"]
FONT_REG = [r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\segoeui.ttf"]


def brand_tint(brand):
    code = 0
    for char in (brand or "").lower():
        code = (code * 31 + ord(char)) % 100003
    return code % 8


def hex_rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def load_font(candidates, size):
    from PIL import ImageFont
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def wrap(draw, text, font, max_width):
    lines, current = [], ""
    for word in text.split():
        trial = (current + " " + word).strip()
        if draw.textlength(trial, font=font) <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def make_tile(brand, name, category, size=800):
    from PIL import Image, ImageDraw

    start_rgb = hex_rgb(PALETTE[brand_tint(brand)][0])
    end_rgb = hex_rgb(PALETTE[brand_tint(brand)][1])

    base = Image.new("RGB", (size, size), start_rgb)
    top = Image.new("RGB", (size, size), end_rgb)
    mask = Image.new("L", (size, size))
    mask.putdata([min(255, int((x + y) / (2 * size) * 255))
                  for y in range(size) for x in range(size)])
    image = Image.composite(top, base, mask)

    draw = ImageDraw.Draw(image, "RGBA")
    pad = int(size * 0.09)

    brand_font = load_font(FONT_BOLD, int(size * 0.085))
    name_font = load_font(FONT_BOLD, int(size * 0.10))
    cat_font = load_font(FONT_REG, int(size * 0.045))

    draw.rectangle([pad, pad, size - pad, size - pad],
                   outline=(255, 255, 255, 90), width=3)

    brand_text = (brand or "").upper()
    bbox = draw.textbbox((0, 0), brand_text, font=brand_font)
    draw.text(((size - (bbox[2] - bbox[0])) / 2, pad + size * 0.05),
              brand_text, font=brand_font, fill=(255, 255, 255, 230))

    lines = wrap(draw, name, name_font, size - 2 * pad - 40)[:4]
    y = (size - len(lines) * (name_font.size + 12)) / 2 + size * 0.02
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=name_font)
        draw.text(((size - (bbox[2] - bbox[0])) / 2, y), line,
                  font=name_font, fill=(255, 255, 255, 245))
        y += name_font.size + 12

    if category:
        bbox = draw.textbbox((0, 0), category, font=cat_font)
        draw.text(((size - (bbox[2] - bbox[0])) / 2, size - pad - size * 0.075),
                  category, font=cat_font, fill=(255, 255, 255, 205))

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=88, optimize=True)
    return buffer.getvalue()


def save_image(obj, content, tag, kind):
    content = normalize_jpeg(content)
    name = f"old_{tag}_{kind}_{obj.pk}.jpg"
    obj.image.save(name, ContentFile(content), save=True)


def normalize_jpeg(content, max_side=1000, quality=85):
    """Re-encode arbitrary image bytes to a sane, web-friendly JPEG."""
    from PIL import Image
    try:
        image = Image.open(io.BytesIO(content))
        image.load()
    except Exception:
        return content
    if image.mode in ("RGBA", "LA", "P"):
        image = image.convert("RGBA")
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image, mask=image.split()[-1])
        image = background
    elif image.mode != "RGB":
        image = image.convert("RGB")
    if max(image.size) > max_side:
        image.thumbnail((max_side, max_side), Image.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=quality, optimize=True)
    return buffer.getvalue()


def folder_for(obj):
    return "accessories" if isinstance(obj, Accessory) else "products"


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------

# only ever touch the legacy items described in the two data modules
def _load_names(path):
    namespace = {}
    with open(path, encoding="utf-8") as handle:
        exec(handle.read(), namespace)
    return namespace


PRODUCT_NAMES = {
    item[1] for items in _load_names("projectv3/old_products_data.py")["OLD_PRODUCTS"].values()
    for item in items
}
ACCESSORY_NAMES = {
    item[1] for items in _load_names("projectv3/old_accessories_data.py")["OLD_ACCESSORIES"].values()
    for item in items
}

def run():
    stats = {"matched": 0, "tile": 0, "failed": 0}
    # names to (re)process even though they are not part of the legacy seed set
    extra_names = {
        chunk.strip() for chunk in os.environ.get("TECHFIX_IMG_EXTRA_NAMES", "").split("|") if chunk.strip()
    }
    product_base = Product.objects.filter(Q(name__in=PRODUCT_NAMES) | Q(name__in=extra_names))
    accessory_base = Accessory.objects.filter(Q(name__in=ACCESSORY_NAMES) | Q(name__in=extra_names))
    if REDO:
        product_query = product_base
        accessory_query = accessory_base
    elif REDO_TILES:
        product_query = product_base.filter(image__icontains="_tile_")
        accessory_query = accessory_base.filter(image__icontains="_tile_")
    else:
        product_query = product_base.filter(image="")
        accessory_query = accessory_base.filter(image="")
    queue = list(product_query.order_by("pk")) + list(accessory_query.order_by("pk"))
    queue = queue[OFFSET:]
    if LIMIT:
        queue = queue[:LIMIT]

    print(f"items to illustrate: {len(queue)} (offset {OFFSET})", flush=True)

    for index, obj in enumerate(queue, 1):
        name = obj.name
        brand = obj.brand or ""
        year = item_year(name)
        query = re.sub(r"\s+", " ", re.sub(r"\([^)]*\)", " ", name)).strip()

        candidates = []
        net_before = _NETWORK_HITS
        queries = [query]
        qualified = f"{query} {brand}".strip()
        if qualified.lower() != query.lower():
            queries.append(qualified)
        for search_query in queries:
            try:
                candidates += commons_search(search_query)
                if best_candidate(brand, query, candidates, year):
                    break
            except Exception as exc:
                print(f"  ! search failed for {name}: {exc}", flush=True)

        match = best_candidate(brand, query, candidates, year)
        saved = False
        if match:
            _, title, url = match
            try:
                save_image(obj, fetch(url, binary=True), folder_for(obj), "photo")
                stats["matched"] += 1
                saved = True
                print(f"[{index}/{len(queue)}] PHOTO {name} <- {title}", flush=True)
            except Exception as exc:
                print(f"  ! download failed for {name}: {exc}", flush=True)

        if not saved:
            try:
                tile = make_tile(brand, name, obj.category.name if obj.category else "")
                save_image(obj, tile, folder_for(obj), "tile")
                stats["tile"] += 1
                print(f"[{index}/{len(queue)}] TILE  {name}", flush=True)
            except Exception as exc:
                stats["failed"] += 1
                print(f"[{index}/{len(queue)}] FAIL  {name}: {exc}", flush=True)

        if _NETWORK_HITS != net_before:
            time.sleep(SLEEP)

    print("done:", stats, flush=True)
    print("still without image:",
          Product.objects.filter(image="").count() + Accessory.objects.filter(image="").count(),
          flush=True)


if os.environ.get("TECHFIX_IMG_NO_RUN") != "1":
    run()
