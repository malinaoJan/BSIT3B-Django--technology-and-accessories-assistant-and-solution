"""Import aggregate online ratings for catalog products.

Ratings are taken from public catalog listings:

1. Beebom Gadgets brand pages (user rating and number of ratings) for phones.
2. Smartprix search results and product pages (JSON-LD ratingValue/ratingCount)
   for phones, laptops, and tablets.

Only products without customer reviews are filled by default, so real on-site
reviews always take priority.  Data is cached under the system temp directory
and the command can be re-run safely; use --redo to replace imported values.

Run from the project root:
    venv\\Scripts\\python.exe projectv3\\manage.py import_online_ratings
    venv\\Scripts\\python.exe projectv3\\manage.py import_online_ratings --dry-run
    venv\\Scripts\\python.exe projectv3\\manage.py import_online_ratings --category Laptops
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
SMARTPRIX_SEARCH = "https://www.smartprix.com/{section}/search?q={query}"
SMARTPRIX_BASE = "https://www.smartprix.com"
SMARTPRIX_SECTIONS = {
    "Smartphones": "mobiles",
    "Laptops": "laptops",
    "Tablets": "tablets",
}

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

BRAND_ALIASES = sorted([
    "red magic", "redmagic", "nubia", "samsung", "apple", "lenovo", "hp",
    "dell", "asus", "acer", "msi", "gigabyte", "google", "microsoft",
    "razer", "huawei", "xiaomi", "lg", "honor", "infinix", "tecno",
    "realme", "oppo", "vivo", "itel", "oneplus", "nothing", "sony", "tcl",
    "nokia", "motorola", "amazon", "anker", "baseus", "ugreen", "logitech",
    "tp-link", "epson", "redmi", "poco",
], key=len, reverse=True)

GENERIC_NAME_WORDS = sorted([
    "laptop", "laptops", "tablet", "tablets", "notebook", "notebooks",
    "gaming", "wi-fi", "wifi", "wi", "fi", "windows", "win", "win10",
    "win11", "home", "pc", "inch", "inches", "gen", "generation",
    "edition", "4g", "5g", "lte", "hyperx",
], key=len, reverse=True)


SIZE_TOKENS = {"10", "11", "12", "13", "14", "15", "16", "17", "18"}
OPTIONAL_MATCH_TOKENS = {"tab", "ai"}
VARIANT_TOKENS = {
    "ultra", "plus", "pro", "max", "lite", "fe", "se", "air", "mini",
    "oled", "snapdragon", "rtx", "gtx",
}
QUERY_SPEC_WORDS = sorted([
    "snapdragon", "hyperx", "windows", "gaming", "win11", "win10",
    "wi-fi", "oled", "rtx", "gtx", "home", "wifi", "lte", "5g",
    "4g", "ai",
], key=len, reverse=True)
CPU_GEN_YEARS = {
    3: 2013, 4: 2014, 5: 2015, 6: 2016, 7: 2017,
    8: 2018, 9: 2019, 10: 2020, 11: 2021, 12: 2022,
    13: 2023, 14: 2024,
}


def product_search_variants(name):
    variants = [name]
    bare = re.sub(r"\s*\([^)]*\)", " ", name or "")
    bare = re.sub(r"\s+", " ", bare).strip()
    if bare and bare not in variants:
        variants.append(bare)

    simplified = bare
    for word in QUERY_SPEC_WORDS:
        simplified = re.sub(
            r"(?<![a-z0-9])" + re.escape(word) + r"(?![a-z0-9])",
            " ",
            simplified,
            flags=re.IGNORECASE,
        )
    simplified = re.sub(r"\s+", " ", simplified).strip()
    if simplified and simplified not in variants:
        variants.append(simplified)
    return variants


def _gpu_models(name):
    return set(
        re.findall(r"\b(?:rtx|gtx)\s*(\d{3,4})\b", name or "", flags=re.IGNORECASE)
    )


def _candidate_conflicts(candidate_name, product_name):
    product = _model_tokens(product_name)
    candidate = _model_tokens(candidate_name, truncate=True)

    product_years = {t for t in product if re.fullmatch(r"20\d\d", t)}
    candidate_years = {t for t in candidate if re.fullmatch(r"20\d\d", t)}
    if product_years and candidate_years and not (product_years & candidate_years):
        return True

    product_sizes = product & SIZE_TOKENS
    candidate_sizes = candidate & SIZE_TOKENS
    if product_sizes and candidate_sizes and not (product_sizes & candidate_sizes):
        return True

    product_gens = {t for t in product if re.fullmatch(r"g\d+", t)}
    candidate_gens = {t for t in candidate if re.fullmatch(r"g\d+", t)}
    if product_gens:
        if not candidate_gens:
            return True
        if not (product_gens & candidate_gens):
            return True

    product_series = {
        t for t in product
        if t.isdigit() and len(t) <= 2 and t not in SIZE_TOKENS
    }
    candidate_series = {
        t for t in candidate
        if t.isdigit() and len(t) <= 2 and t not in SIZE_TOKENS
    }
    if product_series and candidate_series and not (
        product_series & candidate_series
    ):
        return True

    product_suffixes = set(
        re.findall(r"\b(\d{2}[a-z])\b", (product_name or "").lower())
    )
    if product_suffixes:
        candidate_text = (candidate_name or "").lower()
        if not all(
            re.search(r"\b" + re.escape(suffix) + r"\b", candidate_text)
            for suffix in product_suffixes
        ):
            return True

    cpu_gen = re.search(
        r"\b(\d{1,2})(?:st|nd|rd|th)\s+gen\b",
        candidate_name or "",
        flags=re.IGNORECASE,
    )
    if product_years and cpu_gen:
        generation = int(cpu_gen.group(1))
        product_year = max(int(t) for t in product_years)
        cpu_year = CPU_GEN_YEARS.get(generation)
        if cpu_year and abs(product_year - cpu_year) > 1:
            return True
        if product_year <= 2021 and generation >= 12:
            return True
        if product_year >= 2022 and generation <= 11:
            return True

    return False


def _pick_reordered(candidates, product_name):
    product = _model_tokens(product_name)
    product_years = {t for t in product if re.fullmatch(r"20\d\d", t)}
    required = product - OPTIONAL_MATCH_TOKENS - product_years
    if not required:
        return None

    hits = []
    for item in candidates:
        candidate = _model_tokens(item[0])
        if required <= candidate:
            hits.append(item)
    if not hits:
        return None
    return max(hits, key=lambda item: candidate_rank(item[0], product_name))


def _clean_model_text(name, truncate=False, drop_years=False):
    text = (name or "").lower().replace("+", " plus ")
    if drop_years:
        text = re.sub(r"\b(19|20)\d{2}\b", " ", text)
    if truncate:
        text = re.sub(
            r"\b(laptop|laptops|tablet|tablets|notebook|notebooks)\b.*$",
            " ",
            text,
        )
    text = re.sub(r"\((?![^)]*20\d\d)[^)]*\)", " ", text)
    text = re.sub(r"\bgen(?:eration)?\s*(\d+)\b", r"g\1", text)
    for alias in BRAND_ALIASES:
        text = re.sub(
            r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])",
            " ",
            text,
        )
    for word in GENERIC_NAME_WORDS:
        text = re.sub(
            r"(?<![a-z0-9])" + re.escape(word) + r"(?![a-z0-9])",
            " ",
            text,
        )
    text = re.sub(r"\b(\d+)(st|nd|rd|th)\b", r"\1", text)
    return re.sub(r"\b(\d+)i\b", r"\1", text)


def model_key(name):
    """Compact model-only key used for fuzzy laptop/tablet matching."""
    return re.sub(r"[^a-z0-9]+", "", _clean_model_text(name, drop_years=True))


def _model_tokens(name, truncate=False):
    text = _clean_model_text(name, truncate=truncate)
    tokens = set()
    for token in re.findall(r"[a-z0-9]+", text):
        if re.fullmatch(r"g\d+", token):
            tokens.add(token)
            continue
        trailing_number = re.fullmatch(r"([a-z]+)(\d{1,2})", token)
        if trailing_number and len(token) > 5:
            tokens.update(trailing_number.groups())
        elif (
            len(token) <= 5
            and re.search(r"[a-z]", token)
            and re.search(r"\d", token)
        ):
            tokens.update(re.findall(r"[a-z]+|\d+", token))
        else:
            tokens.add(token)
    return {token for token in tokens if len(token) > 1 or token.isdigit()}


def candidate_rank(candidate_name, product_name):
    """Prefer the candidate that best matches year, size, and model numbers."""
    product = _model_tokens(product_name)
    candidate = _model_tokens(candidate_name, truncate=True)
    product_key = model_key(product_name)
    candidate_key = model_key(candidate_name)
    common = 0
    for left, right in zip(product_key, candidate_key):
        if left != right:
            break
        common += 1
    score = 4.0 * common / len(product_key) if product_key else 0.0

    product_years = {t for t in product if re.fullmatch(r"20\d\d", t)}
    candidate_years = {t for t in candidate if re.fullmatch(r"20\d\d", t)}
    if product_years:
        if product_years & candidate_years:
            score += 4.0
        elif candidate_years:
            score -= 5.0

    product_sizes = product & SIZE_TOKENS
    candidate_sizes = candidate & SIZE_TOKENS
    if product_sizes:
        if product_sizes & candidate_sizes:
            score += 2.5
        elif candidate_sizes:
            score -= 2.5
        else:
            large_series = {
                t for t in candidate
                if t.isdigit() and len(t) == 2 and int(t) >= 19
            }
            if large_series:
                score -= 4.0

    product_gens = {t for t in product if re.fullmatch(r"g\d+", t)}
    candidate_gens = {t for t in candidate if re.fullmatch(r"g\d+", t)}
    if product_gens:
        if product_gens & candidate_gens:
            score += 2.0
        elif candidate_gens:
            distance = abs(
                int(sorted(product_gens)[0][1:])
                - int(sorted(candidate_gens)[0][1:])
            )
            score -= 2.0 + min(distance, 6) * 0.5

    product_series = {
        t for t in product
        if t.isdigit() and len(t) <= 2 and t not in SIZE_TOKENS
    }
    candidate_series = {
        t for t in candidate
        if t.isdigit() and len(t) <= 2 and t not in SIZE_TOKENS
    }
    if product_series:
        if product_series & candidate_series:
            score += 2.0
        elif candidate_series:
            score -= 3.0

    product_numbers = {
        t for t in product
        if t.isdigit() and len(t) >= 3 and t not in product_years
    }
    candidate_numbers = {
        t for t in candidate
        if t.isdigit() and len(t) >= 3 and t not in candidate_years
    }
    full_candidate_numbers = {
        t for t in re.findall(r"\d+", candidate_name)
        if len(t) >= 3 and not re.fullmatch(r"20\d\d", t)
    }
    if product_numbers and product_numbers & full_candidate_numbers:
        score += 3.0

    candidate_text = candidate_name.lower()
    cpu_gen = re.search(
        r"\b(\d{1,2})(?:st|nd|rd|th)\s+gen\b", candidate_text
    )
    if cpu_gen:
        score += min(int(cpu_gen.group(1)), 14) * 0.15
    elif "core ultra" in candidate_text:
        score += 1.0

    modern_product = (
        (product_years and max(int(t) for t in product_years) >= 2024)
        or (product_gens and max(int(t[1:]) for t in product_gens) >= 7)
    )
    if modern_product:
        if "core ultra" in candidate_text or re.search(
            r"\bcore [579]\b", candidate_text
        ):
            score += 1.5
        elif re.search(r"\b(8th|9th|10th|11th) gen\b", candidate_text):
            score -= 2.0

    product_variants = product & VARIANT_TOKENS
    candidate_variants = candidate & VARIANT_TOKENS
    score += 1.5 * len(product_variants & candidate_variants)
    score -= 2.0 * len(product_variants - candidate_variants)
    score -= 1.0 * len(candidate_variants - product_variants)

    shared = (
        (product & candidate)
        - product_years - candidate_years
        - product_sizes - candidate_sizes
        - product_gens - candidate_gens
        - product_series - candidate_series
        - product_numbers - candidate_numbers
    )
    return score + len(shared), -len(candidate_key)


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


def parse_smartprix_search(raw, section="mobiles"):
    results = []
    for block in re.split(r'(?=<div[^>]*class="sm-product)', raw):
        if 'class="sm-product' not in block:
            continue
        name = re.search(r'<img[^>]*alt="([^"]*)"', block)
        href = re.search(r'href="(/' + re.escape(section) + r'/[^"]+)"', block)
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


def smartprix_search(query, cache, refresh=False, section="mobiles"):
    key = query if section == "mobiles" else f"{section}:{query}"
    if not refresh and key in cache["searches"]:
        return [tuple(item) for item in cache["searches"][key]]
    raw = http_get(
        SMARTPRIX_SEARCH.format(section=section, query=urllib.parse.quote(query))
    )
    results = parse_smartprix_search(raw, section)
    if results:
        cache["searches"][key] = results
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


def pick_candidate(candidates, product, allow_prefix=False):
    if not allow_prefix:
        key = compact(product.name, product.brand)
        hits = [
            item for item in candidates
            if compact(item[0], product.brand) == key
        ]
        if not hits:
            return None
        return max(hits, key=lambda item: candidate_score(item[0], product.name))

    gpu_models = _gpu_models(product.name)
    if gpu_models:
        candidates = [
            item for item in candidates
            if gpu_models <= set(re.findall(r"\d{3,4}", item[0]))
        ]
    candidates = [
        item for item in candidates
        if not _candidate_conflicts(item[0], product.name)
    ]
    if not candidates:
        return None

    key = model_key(product.name)
    if not key:
        return None
    attempts = []
    current = key
    while len(current) >= 4:
        attempts.append(current)
        if current[-1].isdigit():
            current = current[:-1]
        else:
            current = re.sub(r"[a-z]+$", "", current)
    if key.endswith("ai"):
        relaxed = key[:-2]
        if len(relaxed) >= 4 and relaxed not in attempts:
            attempts.append(relaxed)
    for attempt in attempts:
        hits = [
            item for item in candidates
            if model_key(item[0]).startswith(attempt)
        ]
        if hits:
            return max(
                hits, key=lambda item: candidate_rank(item[0], product.name)
            )
    return _pick_reordered(candidates, product.name)


def pick_named(candidates, name, brand):
    key = compact(name, brand)
    for candidate in candidates:
        if compact(candidate[0], brand) == key:
            return candidate
    return None


def smartprix_result(
    product, query, cache, refresh, delay, match_name=None, log=None,
    section="mobiles", allow_prefix=False,
):
    try:
        candidates = smartprix_search(
            query, cache, refresh=refresh, section=section
        )
    except Exception as exc:
        if log:
            log(f"  ! search failed for {query}: {exc}")
        time.sleep(delay)
        return None

    if match_name:
        best = pick_named(candidates, match_name, product.brand)
    else:
        best = pick_candidate(candidates, product, allow_prefix=allow_prefix)
    if not best:
        time.sleep(delay)
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
    help = (
        "Import aggregate ratings from Beebom and Smartprix for phones, "
        "laptops, and tablets."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--category", action="append", default=[],
            choices=list(SMARTPRIX_SECTIONS),
            help="Category to fill (repeatable). Defaults to all supported categories.",
        )
        parser.add_argument("--brand", action="append", default=[])
        parser.add_argument("--name", action="append", default=[])
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--redo", action="store_true", help="Replace existing imported ratings.")
        parser.add_argument("--all", action="store_true", help="Include products that already have reviews.")
        parser.add_argument("--refresh", action="store_true", help="Ignore cached source data.")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--delay", type=float, default=1.5, help="Delay between Smartprix requests.")

    def handle(self, *args, **options):
        stream = getattr(self.stdout, "_out", None)
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(errors="replace")
            except (AttributeError, ValueError):
                pass
        delay = max(0.5, options["delay"])
        categories = options["category"] or list(SMARTPRIX_SECTIONS)
        products = Product.objects.filter(
            category__name__in=categories
        ).order_by("pk")
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
            self.stdout.write("No products need online ratings.")
            return

        self.stdout.write(f"products to rate: {len(products)}")
        beebom_index = {}
        if any(
            product.category and product.category.name == "Smartphones"
            for product in products
        ):
            beebom = beebom_entries(refresh=options["refresh"])
            for entry in beebom:
                if entry["rating"] <= 0:
                    continue
                key = compact(entry["name"], entry["brand"])
                beebom_index.setdefault(key, []).append(entry)

        cache = smartprix_cache(refresh=options["refresh"])
        filled = 0
        skipped = []
        for product in products:
            section = SMARTPRIX_SECTIONS.get(
                product.category.name if product.category else "", "mobiles"
            )
            result = None
            if section == "mobiles":
                beebom_hits = beebom_index.get(
                    compact(product.name, product.brand), []
                )
                if beebom_hits:
                    best = max(
                        beebom_hits,
                        key=lambda item: candidate_score(
                            item["name"], product.name
                        ),
                    )
                    result = (
                        best["name"], best["rating"], best["count"], "Beebom", ""
                    )

            if result is None:
                queries = []
                for variant in product_search_variants(product.name):
                    if (
                        product.brand
                        and product.brand.lower() not in variant.lower()
                    ):
                        queries.append(f"{product.brand} {variant}")
                    queries.append(variant)
                queries = list(dict.fromkeys(queries))
                sections = [section]
                if section == "laptops":
                    sections.append("tablets")
                elif section == "tablets":
                    sections.append("laptops")
                for active_section in sections:
                    for query in queries:
                        result = smartprix_result(
                            product, query, cache, options["refresh"], delay,
                            log=self.stdout.write, section=active_section,
                            allow_prefix=active_section != "mobiles",
                        )
                        if result is not None:
                            break
                    if result is not None:
                        break

            for alias in RATING_ALIASES.get(product.name, []):
                if result is not None:
                    break
                result = smartprix_result(
                    product, alias, cache, options["refresh"], delay,
                    match_name=alias, log=self.stdout.write, section=section,
                    allow_prefix=section != "mobiles",
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
            category__name__in=categories,
            reviews__isnull=True,
            online_rating__isnull=True,
        ).count()
        self.stdout.write(f"products without any rating: {remaining}")
