"""Attach real, model-specific photos to tablet products.

Only tablets from the requested brands (Apple, ASUS, Dell, HP, Lenovo,
Samsung and RedMagic) released in 2020 or later are considered.  A candidate
image is accepted only when its listing title contains every significant model
token of the product (brand, family, model number, screen size, chip and
generation) and does not mention a conflicting variant, year, chip or
generation.  Products without a confident match keep their branded placeholder
tile, so a wrong picture is never attached.

Photos are sourced from Amazon product listings (main product image).  Results
are cached under the system temp directory, so re-runs are cheap.

Run from the project root:
    venv\\Scripts\\python.exe projectv3\\manage.py fetch_tablet_photos
    venv\\Scripts\\python.exe projectv3\\manage.py fetch_tablet_photos --dry-run
    venv\\Scripts\\python.exe projectv3\\manage.py fetch_tablet_photos --brand Apple
    venv\\Scripts\\python.exe projectv3\\manage.py fetch_tablet_photos --limit 10
    venv\\Scripts\\python.exe projectv3\\manage.py fetch_tablet_photos --redo
"""

import html
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from PIL import Image

from apps.core.models import Product


BRANDS = ('Apple', 'ASUS', 'Dell', 'HP', 'Lenovo', 'Samsung', 'RedMagic')

BROWSER_UA = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/120.0 Safari/537.36'
)
HEADERS = {
    'User-Agent': BROWSER_UA,
    'Accept': (
        'text/html,application/xhtml+xml,application/xml;q=0.9,'
        'image/avif,image/webp,*/*;q=0.8'
    ),
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
}

CACHE_DIR = tempfile.gettempdir()
SEARCH_CACHE_PATH = os.path.join(CACHE_DIR, 'techfix_tablet_amazon_search.json')
SLEEP_SECONDS = 2.5
MAX_QUERIES_PER_PRODUCT = 3
MIN_IMAGE_SIDE = 220

BRAND_NAME_TOKENS = {
    'apple', 'ipad', 'asus', 'dell', 'hp', 'lenovo', 'samsung', 'redmagic',
}

BRAND_ALIASES = {
    'apple': {'apple', 'ipad'},
    'asus': {'asus', 'rog', 'proart', 'expertbook'},
    'dell': {'dell', 'latitude'},
    'hp': {'hp', 'elitebook'},
    'lenovo': {'lenovo', 'thinkpad', 'ideapad', 'yoga', 'legion', 'duet'},
    'samsung': {'samsung', 'galaxy'},
    'redmagic': {'redmagic', 'red'},
}

# Words that never identify the model on their own.
GENERIC_TOKENS = {
    'tablet', 'tablets', 'computer', 'pc', 'gaming', 'with', 'and', 'for',
    'the', 'of', 'in', 'to', 'new', 'used', 'renewed', 'refurbished',
    'edition', 'series', 'model', 'android', 'chromeos', 'chrome', 'os',
    'windows', 'wifi', 'wi', 'fi', 'cellular', 'lte', '5g', '4g', 'uwb',
    'gps', 'global', 'international', 'version', 'warranty', 'latest',
    'gen', 'generation', 'inch', 'inches', 'display', 'screen', 'touch',
    'touchscreen', 'oled', 'lcd', 'ips', 'fhd', 'qhd', 'uhd', 'wuxga',
    'wqxga', '2k', '3k', '4k', 'gb', 'tb', 'ram', 'rom', 'storage',
    'battery', 'mah', 'camera', 'mp', 'front', 'rear', 'dual', 'quad',
    'stereo', 'speaker', 'speakers', 'jbl', 'harman', 'kardon', 'dolby',
    'atmos', 'color', 'colour', 'gray', 'grey', 'silver', 'black', 'white',
    'blue', 'gold', 'green', 'pink', 'purple', 'graphite', 'starlight',
    'space', 'midnight', 'ai', 'bionic', 'chip', 'processor', 'cpu',
    'octa', 'core', 'nano', 'textured', 'glass', 'back', 'side', 'button',
}

# A listing that mentions one of these is an accessory, not the tablet.
HARD_ACCESSORY_WORDS = {
    'case', 'cover', 'folio', 'sleeve', 'protector', 'protective', 'tempered',
    'replacement', 'bag', 'backpack', 'briefcase', 'motherboard', 'keycap',
    'decal', 'sticker', 'digitizer', 'assembly', 'mount', 'holder',
    'tripod', 'stand', 'lens', 'parts', 'part',
    'sparepart', 'bezel', 'skin', 'vinyl', 'wrap', 'film', 'shield',
}
# Bundle-friendly words: only an accessory when the title does not otherwise
# identify the tablet itself (name, storage, model number).
SOFT_ACCESSORY_WORDS = {
    'keyboard', 'charger', 'charging', 'adapter', 'power supply', 'dock',
    'docking', 'mouse', 'hub', 'cable', 'cord', 'stylus', 'cooling', 'lock',
    'privacy', 'dust', 'lcd', 'screen', 'display', 'battery', 'glass',
}

ACCESSORY_PATTERNS = (
    r'^(?:for|compatible)\b',
    r'\bfru[a-z0-9]{4,}\b',
    r'\b(?:case|cover|folio|sleeve|protector|keyboard|charger|adapter|'
    r'mount|holder|stand|bag|backpack|battery|glass|lcd|screen|display)'
    r'\s+(?:for|compatible\s+with)\b',
    r'\b(?:replacement|compatible)\s+(?:screen|lcd|panel|keyboard|battery|'
    r'charger|adapter|case|sleeve|cover|part|digitizer)\b',
    r'\b(?:screen|lcd|displays?)\s+(?:replacement|assembly|panel|protector)\b',
    r'\b(?:lcd|oled|amoled|displays?|screens?)\b.*\bfor\s+'
    r'(?:ipad|apple|samsung|galaxy|lenovo|asus|dell|hp|redmagic|tab)\b',
    r'\b(?:touch\s+screen\s+)?digitizer\b',
    r'\b(?:keyboard|book)\s+(?:case|cover|folio)\b',
    r'\b(?:stylus|pen|pencil)\s+(?:for|compatible)\b',
)

# Words that, when present in a listing but not in the product name, mean the
# listing is a different variant of the same family.
VARIANT_WORDS = {
    'mini', 'air', 'pro', 'plus', 'ultra', 'fe', 'lite', 'se', 'max',
    'nova', 'astra', 'active', 'rugged', 'extreme', 'detachable', 'duet',
    'yoga', 'legion', 'idea', 'elite', 'chromebook', 'flow', 'surface',
    'matepad', 'tab', 'pad', 'k10', 'k11', 'y700', 'y900',
    'm9', 'm10', 'm11', 'p10', 'p11', 'p12',
}

CHIP_TOKENS = {'a12', 'a13', 'a14', 'a15', 'a16', 'a17', 'm1', 'm2', 'm3', 'm4', 'm5'}
MODEL_CODE_RE = re.compile(r'^(?=.*[a-z])(?=.*\d)[a-z0-9]{4,}$')

CPU_PATTERNS = (
    (r'\bsnapdragon\s+8\s*(?:\+|plus)?\s*gen\s*(\d)\b', 'sd8g'),
    (r'\bsnapdragon\s+8\s+elite(?:\s+gen\s*(\d))?\b', 'sd8e'),
    (r'\bsnapdragon\s+([0-9]{3})\b', 'sd'),
    (r'\bdimensity\s+([0-9]{3,4})\b', 'dim'),
    (r'\bexynos\s+([0-9]{4})\b', 'exynos'),
    (r'\bhelio\s+([a-z][0-9]{1,3})\b', 'helio'),
    (r'\bkompanio\s+([0-9]{3,4}[a-z]?)\b', 'kompanio'),
    (r'\bmediatek\s+mt([0-9]{4})\b', 'mt'),
    (r'\bintel\s+core\s+ultra\s+([579])\s+([0-9]{3}[a-z]{0,2})\b', 'ultra'),
    (r'\bintel\s+core\s+i([3579])[- ]?([0-9]{4,5}[a-z]{0,2})\b', 'core'),
    (r'\bryzen\s+([3579])\s+([0-9]{3,4}[a-z]{0,2})\b', 'ryzen'),
    (r'\bceleron\s+([a-z0-9]{3,6})\b', 'celeron'),
    (r'\bpentium\s+([a-z0-9]{3,6})\b', 'pentium'),
)

_cache = None


class Command(BaseCommand):
    help = 'Attach verified product photos to 2020-2026 tablet products.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--brand', action='append', default=[],
            help='Only process this brand (can be repeated).',
        )
        parser.add_argument(
            '--name', action='append', default=[],
            help='Only process products whose name contains this text (can be repeated).',
        )
        parser.add_argument(
            '--limit', type=int, default=0,
            help='Process at most N products.',
        )
        parser.add_argument(
            '--offset', type=int, default=0,
            help='Skip the first N products.',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Report matches without downloading or saving.',
        )
        parser.add_argument(
            '--redo', action='store_true',
            help='Also replace existing real photos.',
        )
        parser.add_argument(
            '--refresh', action='store_true',
            help='Ignore cached search results.',
        )

    def handle(self, *args, **options):
        brands = options['brand'] or list(BRANDS)
        brands = [b for b in brands if b in BRANDS]
        dry_run = options['dry_run']
        redo = options['redo']

        if options['refresh']:
            global _cache
            _cache = {}

        qs = Product.objects.filter(
            category__name='Tablets', brand__in=brands
        ).order_by('brand', 'name')

        names = [name.strip().lower() for name in options['name'] if name.strip()]

        targets = []
        for product in qs:
            year = product_year(product.name)
            if year is not None and year < 2020:
                continue
            if names and not any(name in product.name.lower() for name in names):
                continue
            if product.image and '_tile_' not in product.image.name and not redo:
                continue
            targets.append(product)

        targets = targets[options['offset']:]
        if options['limit']:
            targets = targets[:options['limit']]

        self.stdout.write(
            'brands: %s | targets: %d' % (', '.join(brands), len(targets))
        )

        stats = {'photo': 0, 'kept': 0, 'failed': 0}
        for index, product in enumerate(targets, 1):
            label = '[%d/%d] %s' % (index, len(targets), product.name)
            try:
                match = find_match(product)
            except Exception as exc:
                stats['failed'] += 1
                self.stdout.write('%s FAIL search: %s' % (label, _safe(exc)))
                continue

            if not match:
                stats['kept'] += 1
                self.stdout.write('%s KEEP (no confident match)' % label)
                continue

            title, image_url = match
            if dry_run:
                stats['photo'] += 1
                self.stdout.write('%s MATCH <- %s' % (label, _safe(title[:120])))
                continue

            try:
                data = download_image(image_url)
                save_image(product, data)
                stats['photo'] += 1
                self.stdout.write('%s PHOTO <- %s' % (label, _safe(title[:120])))
            except Exception as exc:
                stats['failed'] += 1
                self.stdout.write('%s FAIL save: %s' % (label, _safe(exc)))

        self.stdout.write('done: %s' % stats)


# ---------------------------------------------------------------------------
# matching helpers
# ---------------------------------------------------------------------------

def _safe(value):
    return str(value).encode('ascii', 'replace').decode('ascii')


def product_year(name):
    years = re.findall(r'\b(20(?:1\d|2\d))\b', name or '')
    return int(years[-1]) if years else None


def _normalize(text):
    text = (text or '').lower()
    text = text.replace('&', ' and ')
    text = re.sub(
        r'\bwi-?fi\s*(?:\+|plus)\s*(?:cellular|cell)\b',
        ' wifi cellular ',
        text,
    )
    text = re.sub(
        r'\b(?:cellular|cell)\s*(?:\+|plus)\s*wi-?fi\b',
        ' wifi cellular ',
        text,
    )
    # Only model names (S11+, FE+, A9+) use "+" as "plus"; 2K+, 128GB+ etc do not.
    text = re.sub(
        r'\b(s\d{1,2}|a\d{1,2}|fe|se)\+',
        lambda match: match.group(1) + ' plus ',
        text,
    )
    text = text.replace('+', ' ')
    text = text.replace('2-in-1', ' 2in1 ')
    text = text.replace('2 in 1', ' 2in1 ')
    text = text.replace('wi-fi', ' wifi ')
    text = re.sub(r'\bactive\s*([3-5])\b', r'active \1', text)
    text = re.sub(r'\bactive([3-5])\b', r'active \1', text)
    text = re.sub(
        r'\b(?:with\s+)?s\s*pen\b', ' ', text
    )
    text = re.sub(r'\bapple\s+pencil(?:\s+pro)?\b', ' ', text)
    text = re.sub(
        r'\bultra[\s-]*wide(?:\s+(?:camera|lens|angle|front|rear))?\b',
        ' ',
        text,
    )
    return text


def _tokens(text):
    text = _normalize(text)
    return re.findall(r'[a-z0-9]+(?:\.[0-9]+)?', text)


def _product_gen(name):
    low = (name or '').lower()
    match = re.search(r'\b(\d+)(?:st|nd|rd|th)\s+gen(?:eration)?\b', low)
    if match:
        return match.group(1)
    match = re.search(r'\bgen(?:eration)?\s*(\d+)\b', low)
    if match:
        return match.group(1)
    return None


def _title_gen(low):
    return _product_gen(low)


def model_tokens(name):
    year = product_year(name)
    connectivity = {'5g', '4g', 'lte', 'wifi', 'cellular'}
    tokens = []
    for token in _tokens(name):
        if token in GENERIC_TOKENS and token not in connectivity:
            continue
        if token.isdigit() and len(token) == 4 and token.startswith('20'):
            if int(token) == year:
                continue
        tokens.append(token)
    return list(dict.fromkeys(tokens))


def _brand_tokens(brand):
    return BRAND_ALIASES.get((brand or '').lower(), {(brand or '').lower()})


def _title_identifies_device(low):
    return bool(
        re.search(r'\b(?:tablet|ipad)\b', low)
        or re.search(r'\b\d+\s*(?:gb|tb)\b', low)
        or re.search(r'\bsm[-\s]?[a-z]?\d{3,4}\b', low)
        or re.search(
            r'\b(?:tab|ipad)\b.*\b\d{1,2}(?:\.\d)?\s*(?:"|\'\'|inch|in\b)',
            low,
        )
    )


def _has_accessory_word(low):
    low = low or ''
    if re.search(r'^(?:stylus|pen|pencil|case|cover|folio|sleeve|keyboard)\b', low):
        return True
    # A bare "S Pen" listing is an accessory; bundled pens are fine when the
    # title still identifies the tablet itself (name, storage or screen size).
    if re.search(r'\bs[\s-]*pen\b', low) and not _title_identifies_device(low):
        return True
    for word in HARD_ACCESSORY_WORDS:
        if re.search(r'\b%s\b' % re.escape(word), low):
            return True
    identifies_device = _title_identifies_device(low)
    for word in SOFT_ACCESSORY_WORDS:
        if re.search(r'\b%s\b' % re.escape(word), low):
            if not identifies_device:
                return True
    for pattern in ACCESSORY_PATTERNS:
        if re.search(pattern, low):
            return True
    return False


def _title_has_size(low, size):
    if '.' in size:
        return bool(re.search(r'(?<![\d.])%s(?![\d])' % re.escape(size), low))
    patterns = (
        r'(?<![\w.])%s(?:\.\d+)?\s*(?:"|\'\'|inch|inches|in\b)' % size,
        r'(?<![\w.])%s\s*-\s*inch' % size,
        r'(?<![\w.])%s(?![\w.])' % size,
    )
    return any(re.search(p, low) for p in patterns)


def product_sizes(name):
    low = (name or '').lower()
    sizes = set()
    for match in re.finditer(r'\b(\d{1,2}\.\d{1,2})\b', low):
        sizes.add(match.group(1))
    for match in re.finditer(r'(?<![\w.])(\d{1,2})(?![\w.])', low):
        value = int(match.group(1))
        if 8 <= value <= 15:
            sizes.add(match.group(1))
    return sizes


def _title_sizes(low):
    sizes = set()
    for match in re.finditer(
        r'(\d{1,2}\.\d{1,2})\s*(?:"|\'\'|inch|inches|in\b)', low
    ):
        sizes.add(match.group(1))
    for match in re.finditer(r'(?<![\w.])(\d{1,2})(?![\w.])', low):
        value = int(match.group(1))
        if 8 <= value <= 15:
            sizes.add(match.group(1))
    return sizes


def _title_years(low):
    return {int(y) for y in re.findall(r'\b(20(?:1\d|2\d))\b', low)}


def _has_model_pro(low):
    stripped = re.sub(r'\b(?:windows|win)\s+(?:\d+\s+)?pro\b', ' ', low)
    return bool(re.search(r'\bpro\b', stripped))


def _has_cpu_plus(low):
    return bool(re.search(r'\b\d{3,5}[a-z]{1,2}\s+plus\b', low))


def _four_digit_numbers(tokens):
    return {t for t in tokens if t.isdigit() and len(t) == 4 and not t.startswith('20')}


def apple_chips(text):
    low = _normalize(text)
    chips = set()
    for match in re.finditer(r'\ba(\d{1,2})(x|z)?\b', low):
        value = int(match.group(1))
        if 10 <= value <= 20:
            suffix = match.group(2) or ''
            chips.add('a%d%s' % (value, suffix))
    for match in re.finditer(r'\bm([1-6])\b', low):
        chips.add('m' + match.group(1))
    return chips


def cpu_signatures(text):
    low = _normalize(text)
    chips = set()
    for pattern, prefix in CPU_PATTERNS:
        for match in re.finditer(pattern, low):
            chips.add(prefix + '-' + '-'.join(match.groups()))
    if not chips:
        chips |= apple_chips(low)
    return chips


def spec_cpu_tokens(product):
    return sorted(cpu_signatures('%s %s' % (product.name, product.specifications or '')))


def product_ram(product):
    text = '%s %s' % (product.name, product.specifications or '')
    match = re.search(r'\b(\d+)\s*GB\s*(?:of\s*)?RAM\b', text, re.I)
    if match:
        return int(match.group(1))
    match = re.search(r'\b(\d+)\s*GB\s*/\s*\d+\s*GB\b', text, re.I)
    if match:
        return int(match.group(1))
    match = re.search(r'\bRAM[:\s]*(\d+)\s*GB\b', text, re.I)
    if match:
        return int(match.group(1))
    return None


def _title_ram(low):
    match = re.search(r'\b(\d+)\s*GB\s*RAM\b', low, re.I)
    if match:
        return int(match.group(1))
    match = re.search(r'\bRAM[:\s]*(\d+)\s*GB\b', low, re.I)
    if match:
        return int(match.group(1))
    return None


def _token_matches(token, title_tokens):
    if token in title_tokens:
        return True
    ordinal = re.fullmatch(r'(\d+)(?:st|nd|rd|th)', token)
    if ordinal and ordinal.group(1) in title_tokens:
        return True
    match = re.fullmatch(r'([3579])i', token)
    if match and match.group(1) in title_tokens:
        return True
    if re.fullmatch(r'[3579]', token) and token + 'i' in title_tokens:
        return True
    return False


def score_candidate(product, title):
    low = _normalize(title).strip()
    if len(low) < 12 or 'sponsored ad' in low:
        return -1
    if _has_accessory_word(title.lower()):
        return -1

    title_tokens = set(_tokens(title))
    required = [
        t for t in model_tokens(product.name) if t not in BRAND_NAME_TOKENS
    ]
    if not required:
        return -1

    brand_tokens = _brand_tokens(product.brand)
    if not (title_tokens & brand_tokens):
        return -1

    # Conflicting Apple Silicon / Ax chip.
    product_chips = apple_chips('%s %s' % (product.name, product.specifications or ''))
    title_chips = apple_chips(title)
    if product_chips and title_chips and not (product_chips & title_chips):
        return -1

    # Conflicting non-Apple CPU (Snapdragon/Exynos/Intel...).
    product_cpu = cpu_signatures(product.specifications or '')
    title_cpu = cpu_signatures(title)
    if product_cpu and title_cpu and not (product_cpu & title_cpu):
        return -1

    # Conflicting RAM (often separates generations sold under one name).
    ram = product_ram(product)
    title_ram = _title_ram(low)
    if ram and title_ram and ram != title_ram:
        return -1

    # Conflicting generation (8th Gen vs 9th Gen, Gen 4 vs Gen 5).
    product_gen = _product_gen(product.name)
    title_generation = _title_gen(low)
    if product_gen and title_generation and product_gen != title_generation:
        return -1

    # Conflicting year (e.g. product is 2020, listing is 2024).
    year = product_year(product.name)
    years = _title_years(low)
    if year and years and year not in years:
        return -1

    # A generation in the listing that the product name does not mention means
    # a different model (M10 FHD Plus vs M10 Plus 3rd Gen), unless the year
    # pins the listing to this exact product.  Apple names use chips instead.
    if (
        not product_gen
        and title_generation
        and (product.brand or '').lower() != 'apple'
        and not (year and year in years)
    ):
        return -1

    # Conflicting screen size: 10.2 vs 10.9, 11 vs 13.  Apple sizes always have
    # to match; other brands also put the size in the model name (A9 vs A9+),
    # but sellers often leave it out of the listing title.
    size_strict = (product.brand or '').lower() == 'apple'
    sizes = product_sizes(product.name)
    size_ok = False
    if sizes:
        title_sizes = _title_sizes(low)
        if title_sizes and not (title_sizes & sizes):
            return -1
        size_ok = bool(sizes & title_tokens) or any(
            _title_has_size(low, size) for size in sizes
        )
        if not size_ok and size_strict:
            return -1

    # A matching generation, chip, or year+size identifies the exact model even
    # when the seller leaves the chip or generation out of the listing title.
    identity_ok = bool(
        (product_gen and title_generation == product_gen)
        or (product_chips & title_chips)
        or (year and year in years and size_ok)
    )
    optional = {t for t in required if t in CHIP_TOKENS}
    if product_gen:
        optional.add(product_gen)
        for suffix in ('st', 'nd', 'rd', 'th'):
            optional.add(product_gen + suffix)
    lenient_optional = set() if size_strict else set(sizes)

    missing = [
        t for t in required
        if not _token_matches(t, title_tokens)
        and not (t in optional and identity_ok)
        and t not in lenient_optional
    ]
    if missing:
        return -1

    # Conflicting model number (Latitude 7320 vs 7350...).
    required_numbers = _four_digit_numbers(set(required))
    title_numbers = _four_digit_numbers(title_tokens)
    if required_numbers:
        if title_numbers - required_numbers:
            return -1

    # Conflicting variant words that change the model identity.
    extra_variants = (title_tokens & VARIANT_WORDS) - set(required)
    if 'pro' in extra_variants and not _has_model_pro(low):
        extra_variants.discard('pro')
    if 'plus' in extra_variants and _has_cpu_plus(low):
        extra_variants.discard('plus')
    if extra_variants:
        return -1

    score = len(required) * 2
    if year and year in years:
        score += 5
    if product_gen and title_generation == product_gen:
        score += 4
    if product_chips & title_chips:
        score += 4
    if product_cpu & title_cpu:
        score += 4
    if sizes & title_tokens:
        score += 4
    if 'renewed' in low or 'refurbished' in low:
        score -= 3
    else:
        score += 3
    first = _tokens(title)[:1]
    if first and first[0] in brand_tokens:
        score += 2
    if 'tablet' in low:
        score += 1
    return score


def parse_search_results(page):
    results = []
    blocks = page.split('data-component-type="s-search-result"')[1:]
    for block in blocks:
        alt = re.search(r'alt="([^"]+)"', block)
        src = re.search(
            r'src="(https://m\.media-amazon\.com/images/I/[^"]+)"', block
        )
        if not alt or not src:
            continue
        title = html.unescape(alt.group(1)).strip()
        if len(title) < 12:
            continue
        image_url = re.sub(
            r'\._[A-Za-z0-9_,]+_\.(jpg|jpeg|png)$', r'.\1', src.group(1)
        )
        results.append((title, image_url))
    return results


def _load_cache():
    global _cache
    if _cache is not None:
        return _cache
    try:
        with open(SEARCH_CACHE_PATH, encoding='utf-8') as handle:
            _cache = json.load(handle)
    except Exception:
        _cache = {}
    return _cache


def _save_cache():
    if _cache is None:
        return
    try:
        with open(SEARCH_CACHE_PATH, 'w', encoding='utf-8') as handle:
            json.dump(_cache, handle)
    except Exception:
        pass


def _fetch_bytes(url, timeout=45):
    curl = shutil.which('curl')
    if curl:
        fd, path = tempfile.mkstemp()
        os.close(fd)
        try:
            result = subprocess.run(
                [
                    curl, '-s', '-L', '--compressed', '--max-time', str(timeout),
                    '-o', path, '-A', BROWSER_UA,
                    '-H', 'Accept: %s' % HEADERS['Accept'],
                    '-H', 'Accept-Language: %s' % HEADERS['Accept-Language'],
                    '-H', 'Accept-Encoding: %s' % HEADERS['Accept-Encoding'],
                    url,
                ],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout + 10,
            )
            if result.returncode != 0:
                raise RuntimeError(
                    'curl failed (%s): %s'
                    % (result.returncode, result.stderr.decode('utf-8', 'replace')[:200])
                )
            with open(path, 'rb') as handle:
                return handle.read()
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def amazon_search(query, tablets_only=True):
    cache = _load_cache()
    key = ('tablets:' if tablets_only else 'all:') + query.strip().lower()
    if key in cache:
        return [tuple(item) for item in cache[key]]

    params = {'k': query}
    if tablets_only:
        params['i'] = 'computers'
        params['rh'] = 'n:1232597011'
    url = 'https://www.amazon.com/s?' + urllib.parse.urlencode(params)
    last_error = None
    for attempt in range(3):
        try:
            page = _fetch_bytes(url).decode('utf-8', 'replace')
            results = parse_search_results(page)
            if results:
                cache[key] = results
                _save_cache()
                time.sleep(SLEEP_SECONDS)
                return results
            last_error = 'no product cards'
        except Exception as exc:
            last_error = str(exc)
        time.sleep(SLEEP_SECONDS * (attempt + 1))
    raise RuntimeError('search failed for %r: %s' % (query, last_error))


BUNDLE_TITLE_TERMS = (
    'bundle', 'sd card', 'storage+', 'storage +', 'with keyboard',
    'keyboard cover', 'book cover', 'starter kit', 'accessory', 'accessories',
)


def _capacity_gb(value, unit):
    return int(round(float(value) * (1024 if unit.lower() == 'tb' else 1)))


def product_storage(product):
    text = product.specifications or ''
    match = re.search(r'\b\d+\s*GB\s*/\s*(\d+)\s*GB\b', text, re.I)
    if match:
        return int(match.group(1))
    match = re.search(
        r'\b(\d+)\s*(GB|TB)\s*(?:storage|rom|emmc|ufs)\b', text, re.I
    )
    if match:
        return _capacity_gb(match.group(1), match.group(2))
    match = re.search(r'\bstorage[:\s]*(\d+)\s*(GB|TB)\b', text, re.I)
    if match:
        return _capacity_gb(match.group(1), match.group(2))
    match = re.search(r'\b(\d+)\s*(GB|TB)\b(?!\s*RAM)', text, re.I)
    if match:
        return _capacity_gb(match.group(1), match.group(2))
    return None


def _title_storage(low):
    match = re.search(
        r'\b(\d+)\s*(GB|TB)\s*(?:storage|rom|emmc|ufs)\b', low, re.I
    )
    if match:
        return _capacity_gb(match.group(1), match.group(2))
    match = re.search(r'\bstorage[:\s]*(\d+)\s*(GB|TB)\b', low, re.I)
    if match:
        return _capacity_gb(match.group(1), match.group(2))
    return None


def _clean_match(product, title):
    low = title.lower()
    if any(term in low for term in BUNDLE_TITLE_TERMS):
        return False
    title_storage = _title_storage(low)
    storage = product_storage(product)
    if title_storage and storage and title_storage != storage:
        return False
    return True


def _query_variants(product):
    name = re.sub(r'\s+', ' ', product.name).strip()
    without_year = re.sub(r'\s*\(20(?:1\d|2\d)\)', '', name).strip()
    variants = [name]
    if '+' in name:
        variants.append(re.sub(r'\+', ' Plus ', without_year))
    if without_year != name:
        variants.append(without_year)
    else:
        variants.append(name + ' tablet')
    return variants[:MAX_QUERIES_PER_PRODUCT]


def find_match(product):
    for tablets_only in (True, False):
        best = None
        best_score = -1
        clean = None
        clean_score = -1
        for query in _query_variants(product):
            try:
                candidates = amazon_search(query, tablets_only=tablets_only)
            except Exception:
                continue
            for title, image_url in candidates:
                score = score_candidate(product, title)
                if score > best_score:
                    best_score = score
                    best = (title, image_url)
                if score > clean_score and _clean_match(product, title):
                    clean_score = score
                    clean = (title, image_url)
        if clean_score > 0:
            return clean
        if best_score > 0:
            return best
    return None


# ---------------------------------------------------------------------------
# image saving
# ---------------------------------------------------------------------------

def download_image(url):
    data = _fetch_bytes(url)
    if len(data) < 5000:
        raise RuntimeError('image too small')
    image = Image.open(io.BytesIO(data))
    image.load()
    if min(image.size) < MIN_IMAGE_SIDE:
        raise RuntimeError('image resolution too low')
    if max(image.size) / float(min(image.size)) > 4:
        raise RuntimeError('unusable aspect ratio')
    if image.mode in ('RGBA', 'LA', 'P'):
        image = image.convert('RGBA')
        background = Image.new('RGB', image.size, (255, 255, 255))
        background.paste(image, mask=image.split()[-1])
        image = background
    elif image.mode != 'RGB':
        image = image.convert('RGB')
    image.thumbnail((1200, 1200))
    buffer = io.BytesIO()
    image.save(buffer, format='JPEG', quality=90, optimize=True)
    return buffer.getvalue()


def save_image(product, data):
    slug = re.sub(r'[^a-z0-9]+', '_', product.name.lower()).strip('_')
    filename = 'tablet_%s_%s.jpg' % (slug[:80], product.pk)
    if product.image:
        product.image.delete(save=False)
    product.image.save(filename, ContentFile(data), save=True)
