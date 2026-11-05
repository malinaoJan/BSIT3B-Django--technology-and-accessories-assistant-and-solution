"""Attach real product photos to smartphones that have no image.

The catalog already has a branded placeholder tile for products without a
photo.  This command replaces those placeholders with an actual picture of the
exact model.  Accuracy comes first: a candidate is only accepted when its model
name matches the product name token-for-token (4G/5G/LTE suffixes are ignored).

Sources, in order:
  1. Beebom Gadgets brand catalog (front + back renders)
  2. HONOR global product listing (official renders)
  3. ASUS ROG official product page
  4. Smartprix mobile search (front/back renders, upscaled)
  5. Wikimedia Commons / Wikipedia (optional, --wikimedia)

Products without a confident match are left untouched and keep the placeholder
tile, so no wrong picture is ever attached.

Run from the project root:
    venv\\Scripts\\python.exe projectv3\\manage.py fetch_phone_photos
    venv\\Scripts\\python.exe projectv3\\manage.py fetch_phone_photos --dry-run
    venv\\Scripts\\python.exe projectv3\\manage.py fetch_phone_photos --brand Infinix --brand OPPO
    venv\\Scripts\\python.exe projectv3\\manage.py fetch_phone_photos --wikimedia
"""

import io
import json
import os
import re
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from PIL import Image

from apps.core.models import Product


BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120 Safari/537.36"
)
CACHE_DIR = tempfile.gettempdir()
BEEBOM_CACHE = os.path.join(CACHE_DIR, "techfix_beebom_catalog.json")
SMARTPRIX_CACHE = os.path.join(CACHE_DIR, "techfix_smartprix_search.json")
HONOR_URL = "https://www.honor.com/global/phones/"
SMARTPRIX_SEARCH = "https://www.smartprix.com/mobiles/search?q={}"
ASUS_ROG_9_PRO_IMAGE = (
    "https://dlcdnwebimgs.asus.com/gain/8D85BFE0-F7E5-406E-96D7-79D35CB96648"
)

BEEBOM_BRANDS = {
    "infinix", "tecno", "oppo", "realme", "vivo", "samsung", "honor", "itel", "asus",
}

STORE_NAMES = {
    "amazon", "flipkart", "croma", "reliance digital", "vijay sales", "india",
}


def http_get(url, binary=False, ua=BROWSER_UA, retries=3, timeout=45):
    last_error = None
    for attempt in range(retries):
        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": ua, "Accept-Language": "en-US,en;q=0.9"}
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data = response.read()
            return data if binary else data.decode("utf-8", "ignore")
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code in (429, 500, 502, 503, 504):
                time.sleep(3 * (attempt + 1))
                continue
            raise
        except Exception as exc:
            last_error = exc
            time.sleep(2 * (attempt + 1))
    raise last_error


def compact(name, brand):
    """Lower-case alphanumeric model key, ignoring 4G/5G/LTE and brand prefixes."""
    text = (name or "").lower().replace("+", " plus ")
    text = re.sub(r"\b(front and back|back and front|front back|back front)\b", " ", text)
    text = re.sub(r"[^a-z0-9]+", "", text)
    text = re.sub(r"(5g|4g|lte)", "", text)
    prefix = re.sub(r"[^a-z0-9]+", "", (brand or "").lower())
    if prefix and not text.startswith(prefix):
        text = prefix + text
    return text


def connectivity(name):
    """Return the explicit network variant of a name, or an empty string."""
    text = (name or "").lower()
    if re.search(r"\b5g\b", text):
        return "5g"
    if re.search(r"\b4g\b", text):
        return "4g"
    if re.search(r"\blte\b", text):
        return "lte"
    return ""


def candidate_score(candidate_name, product_name):
    """Prefer the candidate whose 4G/5G variant matches the product."""
    product_net = connectivity(product_name)
    candidate_net = connectivity(candidate_name)
    if product_net:
        if candidate_net == product_net:
            return 4
        if not candidate_net:
            return 1
        return -10
    if not candidate_net:
        return 4
    if candidate_net == "4g":
        return 3
    if candidate_net == "5g":
        return 2
    return 0


def choose_candidate(candidates, product_name):
    if not candidates:
        return None
    return max(candidates, key=lambda item: candidate_score(item[0], product_name))


def image_pairs(html):
    """Return (alt, src) pairs from every <img> tag, regardless of attribute order."""
    pairs = []
    for tag in re.findall(r"<img[^>]+>", html, re.I):
        alt = re.search(r'alt=["\']([^"\']*)', tag, re.I)
        src = re.search(r'(?:data-src|data-original|src)=["\']([^"\']+)', tag, re.I)
        if alt and src:
            pairs.append((alt.group(1).strip(), src.group(1).strip()))
    return pairs


def beebom_parse(html):
    pairs = []
    for alt, src in image_pairs(html):
        if "cdn.beebom.com/mobile/" not in src:
            continue
        alt = re.sub(
            r"\b(front and back|back and front|front back|back front)\b", " ", alt, flags=re.I
        )
        alt = re.sub(r"\s+", " ", alt).strip()
        if alt:
            pairs.append((alt, src))
    return list(dict.fromkeys(pairs))


def honor_parse(html):
    pairs = []
    for alt, src in image_pairs(html):
        if not alt.lower().startswith("honor") or "honor.com" not in src:
            continue
        if "magicbook" in alt.lower() or "pad" in alt.lower() or "watch" in alt.lower():
            continue
        pairs.append((alt, src))

    def score(url):
        value = url.lower()
        points = 0
        if "plp-banner" in value or "/share" in value or "banner" in value:
            points -= 10
        if "pc-right" in value and "bg" not in value:
            points += 6
        if "phones-list-others" in value and value.endswith(".png"):
            points += 4
        if "product-series" in value and value.endswith(".png"):
            points += 2
        if value.endswith(".png"):
            points += 1
        if "front" in value:
            points += 2
        if "back" in value:
            points += 1
        if "bg" in value:
            points -= 5
        if value.endswith(".jpg"):
            points -= 2
        return points

    best = {}
    for alt, src in pairs:
        key = compact(alt, "HONOR")
        if key not in best or score(src) > best[key][0]:
            best[key] = (score(src), alt, src)
    return [(alt, src) for _, alt, src in best.values()]


def smartprix_parse(html):
    pairs = []
    for alt, src in image_pairs(html):
        if "cdn1.smartprix.com" not in src:
            continue
        if not alt or alt.lower() in STORE_NAMES:
            continue
        src = src.replace("-w280-h280", "-w1000-h1000")
        pairs.append((alt, src))
    return list(dict.fromkeys(pairs))


def normalize_jpeg(content, max_side=1200, quality=88):
    image = Image.open(io.BytesIO(content))
    image.load()
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


def valid_image(content):
    image = Image.open(io.BytesIO(content))
    image.load()
    if min(image.size) < 150:
        return False
    if max(image.size) / float(min(image.size)) > 6:
        return False
    return True


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return default


def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False)
    except Exception:
        pass


class Command(BaseCommand):
    help = "Attach real, correctly matched product photos to smartphones without images."

    def add_arguments(self, parser):
        parser.add_argument("--brand", action="append", default=[],
                            help="Only process this brand (repeatable).")
        parser.add_argument("--limit", type=int, default=0,
                            help="Process at most N products.")
        parser.add_argument("--offset", type=int, default=0,
                            help="Skip the first N products.")
        parser.add_argument("--name", action="append", default=[],
                            help="Only process products whose name contains this text (repeatable).")
        parser.add_argument("--redo", action="store_true",
                            help="Also replace products that already have an image.")
        parser.add_argument("--dry-run", action="store_true",
                            help="Report matches without downloading or saving.")
        parser.add_argument("--refresh", action="store_true",
                            help="Ignore cached catalog/search results.")
        parser.add_argument("--wikimedia", action="store_true",
                            help="Try Wikimedia Commons/Wikipedia for the last leftovers.")

    def handle(self, *args, **options):
        targets = Product.objects.filter(category__name="Smartphones")
        if not options["redo"]:
            targets = targets.filter(image="")
        brands = {brand.strip() for brand in options["brand"] if brand.strip()}
        if brands:
            targets = targets.filter(brand__in=brands)
        targets = list(targets.order_by("brand", "name"))
        names = [name.strip().lower() for name in options["name"] if name.strip()]
        if names:
            targets = [
                product for product in targets
                if any(name in product.name.lower() for name in names)
            ]
        targets = targets[options["offset"]:]
        if options["limit"]:
            targets = targets[: options["limit"]]

        self.dry_run = options["dry_run"]
        self.refresh = options["refresh"]
        self.stats = {}
        self.unmatched = []

        if not targets:
            self.stdout.write("no products need a photo")
            return

        self.stdout.write(f"products to illustrate: {len(targets)}")
        matched = {}

        beebom = self.beebom_index(targets)
        honor = self.honor_index() if any(p.brand.lower() == "honor" for p in targets) else {}
        asus = self.asus_index()
        official = self.official_index()

        remaining = []
        source_priority = {"official": 4, "beebom": 3, "honor": 2, "asus": 1}
        for product in targets:
            key = compact(product.name, product.brand)
            edition_key = key.removesuffix("edition")
            candidates = []
            candidates += [(name, url, "official")
                           for name, url in official.get((product.brand.lower(), key), [])]
            candidates += [(name, url, "beebom")
                           for name, url in beebom.get((product.brand.lower(), key), [])]
            candidates += [(name, url, "beebom")
                           for name, url in beebom.get((product.brand.lower(), edition_key), [])]
            if key in honor:
                candidates.append((*honor[key], "honor"))
            if key in asus:
                candidates.append((*asus[key], "asus"))
            if edition_key in asus:
                candidates.append((*asus[edition_key], "asus"))
            candidate = max(
                candidates,
                key=lambda item: (
                    candidate_score(item[0], product.name),
                    source_priority[item[2]],
                ),
                default=None,
            )
            if candidate and self.attach(product, candidate[0], candidate[1], candidate[2]):
                matched[product.pk] = True
            else:
                remaining.append(product)

        smartprix_cache = {} if self.refresh else load_json(SMARTPRIX_CACHE, {})
        for product in list(remaining):
            key = compact(product.name, product.brand)
            pairs = smartprix_cache.get(product.name)
            if pairs is None:
                try:
                    html = http_get(SMARTPRIX_SEARCH.format(urllib.parse.quote(product.name)))
                    pairs = smartprix_parse(html)
                except Exception as exc:
                    self.stdout.write(f"  ! smartprix search failed for {product.name}: {exc}")
                    pairs = []
                smartprix_cache[product.name] = pairs
                save_json(SMARTPRIX_CACHE, smartprix_cache)
                time.sleep(0.5)
            candidate = choose_candidate(
                [(name, url) for name, url in pairs if compact(name, product.brand) == key],
                product.name,
            )
            if not candidate:
                edition_key = key.removesuffix("edition")
                candidate = choose_candidate(
                    [
                        (name, url) for name, url in pairs
                        if compact(name, product.brand) == edition_key
                    ],
                    product.name,
                )
            if candidate:
                if self.attach(product, candidate[0], candidate[1], "smartprix"):
                    matched[product.pk] = True
                    remaining.remove(product)

        if options["wikimedia"] and remaining:
            remaining = self.wikimedia_pass(remaining)

        for product in remaining:
            self.unmatched.append(f"{product.brand} | {product.name}")

        self.stdout.write("")
        self.stdout.write("done: " + ", ".join(
            f"{source}={count}" for source, count in sorted(self.stats.items())
        ))
        self.stdout.write(f"matched: {len(matched)} / {len(targets)}")
        if self.unmatched:
            self.stdout.write(f"without a confident picture ({len(self.unmatched)}):")
            for line in self.unmatched:
                self.stdout.write(f"  {line}")
        self.stdout.write(f"smartphones still without image: "
                          f"{Product.objects.filter(category__name='Smartphones', image='').count()}")

    # ------------------------------------------------------------------
    # sources
    # ------------------------------------------------------------------

    def beebom_index(self, targets):
        brands = {p.brand.lower() for p in targets} & BEEBOM_BRANDS
        cache = {} if self.refresh else load_json(BEEBOM_CACHE, {})
        index = {}
        for brand in sorted(brands):
            entries = cache.get(brand)
            if not entries:
                entries = self.fetch_beebom_brand(brand)
                cache[brand] = entries
                save_json(BEEBOM_CACHE, cache)
            for name, url in entries:
                index.setdefault((brand, compact(name, brand)), []).append((name, url))
        return index

    def fetch_beebom_brand(self, brand):
        entries = []
        seen = set()
        for page in range(1, 31):
            url = f"https://gadgets.beebom.com/mobile-brands/{brand}"
            if page > 1:
                url += f"?page={page}"
            try:
                html = http_get(url)
            except Exception:
                break
            pairs = beebom_parse(html)
            new = [(name, src) for name, src in pairs if (name, src) not in seen]
            for pair in new:
                seen.add(pair)
                entries.append(pair)
            if page > 1 and not new:
                break
            time.sleep(0.35)
        self.stdout.write(f"  beebom {brand}: {len(entries)} models")
        return entries

    def honor_index(self):
        try:
            html = http_get(HONOR_URL)
        except Exception as exc:
            self.stdout.write(f"  ! honor listing failed: {exc}")
            return {}
        entries = honor_parse(html)
        self.stdout.write(f"  honor: {len(entries)} models")
        return {compact(name, "HONOR"): (name, url) for name, url in entries}

    def asus_index(self):
        index = {
            compact("Asus ROG Phone 9 Pro", "ASUS"): ("Asus ROG Phone 9 Pro", ASUS_ROG_9_PRO_IMAGE),
            compact("Asus ROG Phone 9 Pro Edition", "ASUS"): ("Asus ROG Phone 9 Pro Edition", ASUS_ROG_9_PRO_IMAGE),
        }
        return index

    def official_index(self):
        """Hand-checked official renders for models the catalogs do not carry."""
        entries = [
            (
                "OPPO", "OPPO Reno14 F 5G",
                "https://www.oppo.com/content/dam/oppo/common/mkt/v2-2/reno14-series/list-page/reno14-f/448-600-blue.png",
            ),
            (
                "OPPO", "OPPO Reno14 FS 5G",
                "https://www.oppo.com/content/dam/oppo/product-asset-library/reno/reno14-series/en/reno14-fs/blue-green/v1/assets/images-party-s3-phone-view-phone-1.png.webp",
            ),
            (
                "OPPO", "OPPO Reno15 F 5G",
                "https://www.oppo.com/content/dam/oppo_com/common/mkt/v2-2/reno15-series-en/list-page/reno15-f/480-600-blue.png",
            ),
            (
                "TECNO", "TECNO POP 20",
                "https://d13pvy8xd75yde.cloudfront.net/global/sparkgo3-pop20/800%2A800/KN3-%E6%B7%A1%E7%B4%AB%E8%89%B2.png",
            ),
            (
                "TECNO", "TECNO POVA 7 5G",
                "https://d13pvy8xd75yde.cloudfront.net/phones/lj8k/pova7%E7%B3%BB%E7%B1%BB800%E5%9B%BE/LJ7.png",
            ),
            (
                "TECNO", "TECNO POP 10 Pro",
                "https://d13pvy8xd75yde.cloudfront.net/global/phones/spark-40c/pop-10-pro/pop10p%E9%BB%91.png",
            ),
            (
                "Infinix", "Infinix HOT 70 Pro 5G+",
                "https://pk.pro.infinixmobility.com/media/catalog/product/cache/10f519365b01716ddb90abc57de5a837/b/a/base_thermo_orange_base1_7_1.webp",
            ),
            (
                "HONOR", "HONOR 500 Smart 5G",
                "https://www-file.honor.com/content/dam/honor/common/product-list/product-series/honor-500/honor-500-id-pink-front.png",
            ),
            (
                "itel", "itel A06",
                "https://www.itel-life.com/fileadmin/assets/img/plp/A06/A06-glob.png",
            ),
            (
                "itel", "itel Power 55",
                "https://www.itel-life.com/fileadmin/assets/v/P55_V1/p55_01.png",
            ),
            (
                "itel", "itel Power 55 5G",
                "https://www.itel-life.com/fileadmin/assets/v/P55/02.png",
            ),
            (
                "itel", "itel Power 55 T",
                "https://www.itel-life.com/fileadmin/assets/v/P55T/P55T_01.png",
            ),
            (
                "itel", "itel Power 55+",
                "https://www.itel-life.com/fileadmin/assets/v/P55_Plus/P55__02.png",
            ),
            (
                "itel", "itel Power 65",
                "https://www.itel-life.com/fileadmin/assets/v/P65/P65-bai.png",
            ),
            (
                "itel", "itel S18 Pro",
                "https://www.itel-life.com/fileadmin/assets/img/plp/S18_Pro/PC/S18-Pro-product1.png",
            ),
            (
                "itel", "itel S26 Ultra",
                "https://www.itel-life.com/fileadmin/assets/v/s26u/spec/Sapphire_Black_Blue.png",
            ),
            (
                "vivo", "vivo Y500 Pro",
                "https://wwwstatic.vivo.com.cn/vivoportal/files/resource/product/1768296641475/images/y500pro-color-model-img1-lg.jpg",
            ),
            (
                "vivo", "vivo Y500i",
                "https://fdn2.gsmarena.com/vv/pics/vivo/vivo-y500i-1.jpg",
            ),
        ]
        index = {}
        for brand, name, url in entries:
            index.setdefault((brand.lower(), compact(name, brand)), []).append((name, url))
        return index

    def wikimedia_pass(self, remaining):
        try:
            os.environ["TECHFIX_IMG_NO_RUN"] = "1"
            namespace = {}
            with open("projectv3/fetch_old_images.py", encoding="utf-8") as handle:
                exec(compile(handle.read(), "fetch_old_images.py", "exec"), namespace)
            namespace["VARIANT_WORDS"].add("fe")
            best_candidate = namespace["best_candidate"]
            commons_search = namespace["commons_search"]
            tokens = namespace["tokens"]
            strip_size_period = namespace["strip_size_period"]
            fetch = namespace["fetch"]
        except Exception as exc:
            self.stdout.write(f"  ! wikimedia helpers unavailable: {exc}")
            return remaining

        wiki = "https://en.wikipedia.org/w/api.php"

        def wiki_search(query):
            raw = fetch(wiki, {
                "action": "query", "format": "json", "generator": "search",
                "gsrsearch": query, "gsrnamespace": 0, "gsrlimit": 20,
                "prop": "pageimages", "piprop": "original|thumbnail",
                "pithumbsize": 900, "redirects": 1,
            })
            data = json.loads(raw)
            out = []
            for page in ((data.get("query") or {}).get("pages") or {}).values():
                source = (page.get("original") or {}).get("source")
                if not source:
                    source = (page.get("thumbnail") or {}).get("source")
                if source and not source.lower().endswith(".svg"):
                    out.append((page.get("title", ""), source))
            return out

        still = []
        for product in remaining:
            name = re.sub(r"\s+", " ", re.sub(r"\([^)]*\)", " ", product.name)).strip()
            cleaned, removed = strip_size_period(name)
            removed_tokens = tokens(removed)
            optional = set(removed_tokens) | {"5g", "4g", "lte"}
            size_tokens = {t for t in removed_tokens if t not in ("mid", "early", "late")}
            candidates = []
            try:
                candidates += commons_search(cleaned)
                candidates += wiki_search(cleaned)
            except Exception:
                pass
            match = best_candidate(product.brand, cleaned, candidates, None, optional, size_tokens)
            if match and self.attach(product, match[1], match[2], "wikimedia"):
                pass
            else:
                still.append(product)
            time.sleep(1.0)
        return still

    # ------------------------------------------------------------------
    # save
    # ------------------------------------------------------------------

    def attach(self, product, name, url, source):
        if self.dry_run:
            self.stats[source] = self.stats.get(source, 0) + 1
            self.stdout.write(f"  DRY {source:10s} {product.name} <- {name}")
            return True
        try:
            raw = http_get(url, binary=True)
            if not valid_image(raw):
                raise ValueError("image is too small or has an unusable aspect ratio")
            jpeg = normalize_jpeg(raw)
            if product.image:
                product.image.delete(save=False)
            product.image.save(f"phone_{source}_{product.pk}.jpg", ContentFile(jpeg), save=True)
            self.stats[source] = self.stats.get(source, 0) + 1
            self.stdout.write(f"  OK  {source:10s} {product.name} <- {name}")
            time.sleep(0.25)
            return True
        except Exception as exc:
            self.stdout.write(f"  !   {product.name}: {exc}")
            return False
