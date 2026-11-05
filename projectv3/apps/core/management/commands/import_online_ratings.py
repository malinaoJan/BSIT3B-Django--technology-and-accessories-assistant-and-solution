"""Import aggregate online ratings for smartphones.

Ratings are taken from public catalog listings:

1. Beebom Gadgets brand pages (user rating and number of ratings).
2. Smartprix search results and product pages (JSON-LD ratingValue/ratingCount).

Only phones without customer reviews are filled by default, so real on-site
reviews always take priority.  Data is cached under the system temp directory
and the command can be re-run safely; use --redo to replace imported values.

Run from the project root:
    venv\\Scripts\\python.exe projectv3\\manage.py import_online_ratings
    venv\\Scripts\\python.exe projectv3\\manage.py import_online_ratings --dry-run
    venv\\Scripts\\python.exe projectv3\\manage.py import_online_ratings --brand HONOR
"""

import base64
import json
import os
import re
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.core.models import Product
from apps.core.management.commands.fetch_phone_photos import (
    candidate_score,
    compact,
)

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120 Safari/537.36"
)
CACHE_DIR = tempfile.gettempdir()
BEEBOM_CACHE = os.path.join(CACHE_DIR, "techfix_beebom_ratings.json")
SMARTPRIX_CACHE = os.path.join(CACHE_DIR, "techfix_smartprix_ratings.json")
BEEBOM_BRANDS = [
    "infinix", "tecno", "asus", "oppo", "realme",
    "vivo", "honor", "itel", "samsung",
]
SMARTPRIX_SEARCH = "https://www.smartprix.com/mobiles/search?q={}"
SMARTPRIX_BASE = "https://www.smartprix.com"

# Online catalogs often shorten or expand model names.  Only list aliases that
# refer to the same device (or its regional name), never a different variant.
RATING_ALIASES = {
    "ROG Phone 8 Pro Edition": ["Asus ROG Phone 8 Pro"],
    "HONOR 500 Smart 5G": ["Honor 500 Smart"],
    "HUAWEI Pura 80 Pro": ["Huawei Pura P80 Pro"],
    "Infinix HOT 70 Pro 5G+": ["Infinix Hot 70 Pro 5G"],
    "OPPO Reno14 F 5G": ["OPPO Reno 14F"],
    "OPPO Reno14 FS 5G": ["OPPO Reno 14F"],
    "OPPO Reno15 F 5G": ["OPPO Reno 15F"],
    "OPPO Reno16 F 5G": ["OPPO Reno 16F"],
    "TECNO CAMON Slim 5G": ["Tecno Camon Slim"],
    "vivo Y50 5G": ["Vivo Y50 (2025)"],
    "itel Power 55 T": ["itel P55T"],
    "itel Power 55+": ["itel P55 Plus"],
    "itel Power 65": ["Itel P65"],
    "itel S26 Ultra": ["itel Super 26 Ultra"],
}


def http_get(url, timeout=45, retries=4, delay=0.6):
    last_error = None
    for attempt in range(retries):
        try:
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": BROWSER_UA,
                    "Accept-Language": "en-US,en;q=0.9",
                },
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read().decode("utf-8", "ignore")
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code == 429:
                time.sleep(12 * (attempt + 1))
                continue
            if exc.code in (500, 502, 503, 504):
                time.sleep(3 * (attempt + 1))
                continue
            raise
        except Exception as exc:
            last_error = exc
            time.sleep(2 * (attempt + 1))
    raise last_error


def beebom_entries(refresh=False):
    if os.path.exists(BEEBOM_CACHE) and not refresh:
        with open(BEEBOM_CACHE, encoding="utf-8") as handle:
            return json.load(handle)

    entries = []
    seen = set()
    for brand in BEEBOM_BRANDS:
        page = 1
        max_page = 1
        while page <= max_page:
            if page == 1:
                url = f"https://gadgets.beebom.com/mobile-brands/{brand}"
            else:
                url = f"https://gadgets.beebom.com/mobile-brands/{brand}?page={page}"
            raw = http_get(url)
            if page == 1:
                pages = [int(value) for value in re.findall(r"[?&]page=(\d+)", raw)]
                max_page = max(pages) if pages else 1
            names = [
                (match.start(), base64.b64decode(match.group(1)).decode("utf-8", "ignore"))
                for match in re.finditer(r'dsv="([^"]+)"', raw)
            ]
            pattern = (
                r"&quot;userRating&quot;:\[0,([0-9.]+)\],"
                r"&quot;noOfRatings&quot;:\[0,([0-9]+)\],"
                r"&quot;mobileSlug&quot;:\[0,&quot;([^&]+)&quot;\]"
            )
            for match in re.finditer(pattern, raw):
                position = match.start()
                previous = [name for start, name in names if start < position]
                if not previous:
                    continue
                name = previous[-1]
                key = (name, match.group(3))
                if key in seen:
                    continue
                seen.add(key)
                entries.append({
                    "brand": brand,
                    "name": name,
                    "slug": match.group(3),
                    "rating": float(match.group(1)),
                    "count": int(match.group(2)),
                })
            page += 1
            time.sleep(0.4)

    with open(BEEBOM_CACHE, "w", encoding="utf-8") as handle:
        json.dump(entries, handle, ensure_ascii=False, indent=1)
    return entries


def parse_smartprix_search(raw):
    results = []
    for block in re.split(r'(?=<div[^>]*class="sm-product)', raw):
        if 'class="sm-product' not in block:
            continue
        name = re.search(r'<img[^>]*alt="([^"]*)"', block)
        href = re.search(r'href="(/mobiles/[^"]+)"', block)
        rating = re.search(r'sm-rating"\s+style="--rating:([0-9.]+)', block)
        if name and href and rating:
            results.append((name.group(1).strip(), href.group(1), float(rating.group(1))))
    return list(dict.fromkeys(results))


def smartprix_cache(refresh=False):
    if os.path.exists(SMARTPRIX_CACHE) and not refresh:
        with open(SMARTPRIX_CACHE, encoding="utf-8") as handle:
            return json.load(handle)
    return {"searches": {}, "counts": {}}


def save_smartprix_cache(cache):
    with open(SMARTPRIX_CACHE, "w", encoding="utf-8") as handle:
        json.dump(cache, handle, ensure_ascii=False, indent=1)


def smartprix_search(query, cache, refresh=False):
    if not refresh and query in cache["searches"]:
        return [tuple(item) for item in cache["searches"][query]]
    raw = http_get(SMARTPRIX_SEARCH.format(urllib.parse.quote(query)))
    results = parse_smartprix_search(raw)
    cache["searches"][query] = results
    save_smartprix_cache(cache)
    return results


def smartprix_count(path, cache, refresh=False):
    if not refresh and path in cache["counts"]:
        return cache["counts"][path]
    raw = http_get(SMARTPRIX_BASE + path)
    match = re.search(
        r'"ratingValue"\s*:\s*([0-9.]+)\s*,\s*"ratingCount"\s*:\s*([0-9]+)',
        raw,
    )
    value = None
    if match:
        value = {"rating": float(match.group(1)), "count": int(match.group(2))}
    cache["counts"][path] = value
    save_smartprix_cache(cache)
    return value


def pick_candidate(candidates, product):
    key = compact(product.name, product.brand)
    hits = [item for item in candidates if compact(item[0], product.brand) == key]
    if not hits:
        return None
    return max(hits, key=lambda item: candidate_score(item[0], product.name))


def pick_named(candidates, name, brand):
    key = compact(name, brand)
    for candidate in candidates:
        if compact(candidate[0], brand) == key:
            return candidate
    return None


def smartprix_result(product, query, cache, refresh, delay, match_name=None, log=None):
    try:
        candidates = smartprix_search(query, cache, refresh=refresh)
    except Exception as exc:
        if log:
            log(f"  ! search failed for {query}: {exc}")
        return None

    if match_name:
        best = pick_named(candidates, match_name, product.brand)
    else:
        best = pick_candidate(candidates, product)
    if not best:
        return None

    name, path, rating = best
    count = None
    try:
        detail = smartprix_count(path, cache, refresh=refresh)
    except Exception as exc:
        detail = None
        if log:
            log(f"  ! count failed for {query}: {exc}")
    if detail:
        rating = detail["rating"]
        count = detail["count"]
    time.sleep(delay)
    return (name, rating, count, "Smartprix", SMARTPRIX_BASE + path)


class Command(BaseCommand):
    help = "Import aggregate ratings from Beebom and Smartprix for smartphones."

    def add_arguments(self, parser):
        parser.add_argument("--brand", action="append", default=[])
        parser.add_argument("--name", action="append", default=[])
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--redo", action="store_true", help="Replace existing imported ratings.")
        parser.add_argument("--all", action="store_true", help="Include phones that already have reviews.")
        parser.add_argument("--refresh", action="store_true", help="Ignore cached source data.")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--delay", type=float, default=1.5, help="Delay between Smartprix requests.")

    def handle(self, *args, **options):
        delay = max(0.5, options["delay"])
        products = Product.objects.filter(category__name="Smartphones").order_by("pk")
        if not options["all"]:
            products = products.filter(reviews__isnull=True)
        if options["brand"]:
            products = products.filter(brand__in=options["brand"])
        if options["name"]:
            from django.db.models import Q
            query = Q()
            for value in options["name"]:
                query |= Q(name__icontains=value)
            products = products.filter(query)
        if not options["redo"]:
            products = products.filter(online_rating__isnull=True)
        products = list(products)
        if options["limit"]:
            products = products[: options["limit"]]

        if not products:
            self.stdout.write("No smartphones need online ratings.")
            return

        self.stdout.write(f"smartphones to rate: {len(products)}")
        beebom = beebom_entries(refresh=options["refresh"])
        beebom_index = {}
        for entry in beebom:
            if entry["rating"] <= 0:
                continue
            key = compact(entry["name"], entry["brand"])
            beebom_index.setdefault(key, []).append(entry)

        cache = smartprix_cache(refresh=options["refresh"])
        filled = 0
        skipped = []
        for product in products:
            result = None
            beebom_hits = beebom_index.get(compact(product.name, product.brand), [])
            if beebom_hits:
                best = max(
                    beebom_hits,
                    key=lambda item: candidate_score(item["name"], product.name),
                )
                result = (best["name"], best["rating"], best["count"], "Beebom", "")

            if result is None:
                result = smartprix_result(
                    product, product.name, cache, options["refresh"], delay,
                    log=self.stdout.write,
                )

            for alias in RATING_ALIASES.get(product.name, []):
                if result is not None:
                    break
                result = smartprix_result(
                    product, alias, cache, options["refresh"], delay,
                    match_name=alias, log=self.stdout.write,
                )

            if result is None:
                skipped.append(product.name)
                continue

            name, rating, count, source, _url = result
            try:
                value = Decimal(str(rating)).quantize(Decimal("0.01"))
            except (InvalidOperation, ValueError):
                skipped.append(product.name)
                continue
            if value <= 0:
                skipped.append(product.name)
                continue

            if not options["dry_run"]:
                with transaction.atomic():
                    product.online_rating = value
                    product.online_rating_count = count
                    product.online_rating_source = source
                    product.save(update_fields=[
                        "online_rating",
                        "online_rating_count",
                        "online_rating_source",
                    ])
            filled += 1
            suffix = f" ({count:,} ratings)" if count else ""
            self.stdout.write(
                f"  OK  {source:<9} {product.name} <- {name}: {value}/5{suffix}"
            )

        self.stdout.write(f"\nimported: {filled}")
        self.stdout.write(f"skipped: {len(skipped)}")
        if skipped:
            self.stdout.write("  " + "; ".join(skipped[:20]))
        remaining = Product.objects.filter(
            category__name="Smartphones",
            reviews__isnull=True,
            online_rating__isnull=True,
        ).count()
        self.stdout.write(f"smartphones without any rating: {remaining}")
