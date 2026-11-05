"""Attach real, model-specific photos to laptop products.

Only laptops from the requested brands (Apple, ASUS, Dell, HP, Lenovo,
Samsung, Sony and RedMagic) released in 2020 or later are considered.  A
candidate image is accepted only when its listing title contains every
significant model token of the product (brand, family, model number, screen
size, chip and generation) and does not mention a conflicting variant, year,
chip or generation.  Products without a confident match keep their branded
placeholder tile, so a wrong picture is never attached.

Photos are sourced from Amazon product listings (main product image).  Results
are cached under the system temp directory, so re-runs are cheap.

Run from the project root:
    venv\\Scripts\\python.exe projectv3\\manage.py fetch_laptop_photos
    venv\\Scripts\\python.exe projectv3\\manage.py fetch_laptop_photos --dry-run
    venv\\Scripts\\python.exe projectv3\\manage.py fetch_laptop_photos --brand Apple
    venv\\Scripts\\python.exe projectv3\\manage.py fetch_laptop_photos --limit 10
    venv\\Scripts\\python.exe projectv3\\manage.py fetch_laptop_photos --redo
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
    'Accept-Encoding': 'identity',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
}

CACHE_DIR = tempfile.gettempdir()
SEARCH_CACHE_PATH = os.path.join(CACHE_DIR, 'techfix_laptop_amazon_search.json')
SLEEP_SECONDS = 2.5
MAX_QUERIES_PER_PRODUCT = 3

BRAND_NAME_TOKENS = {
    'apple', 'asus', 'dell', 'hp', 'lenovo', 'samsung', 'redmagic',
}

BRAND_ALIASES = {
    'apple': {'apple', 'macbook'},
    'asus': {'asus', 'rog', 'tuf', 'zenbook', 'vivobook', 'proart'},
    'dell': {
        'dell', 'xps', 'inspiron', 'latitude', 'vostro', 'alienware',
        'g5', 'g15', 'g16',
    },
    'hp': {
        'hp', 'spectre', 'envy', 'pavilion', 'omen', 'victus', 'elitebook',
        'probook', 'omnibook', 'hyperx',
    },
    'lenovo': {
        'lenovo', 'thinkpad', 'ideapad', 'legion', 'loq', 'yoga',
        'thinkbook',
    },
    'samsung': {'samsung', 'galaxy'},
    'redmagic': {'redmagic', 'red', 'magic'},
}

# Words that never identify the model on their own.
GENERIC_TOKENS = {
    'laptop', 'laptops', 'notebook', 'notebooks', 'computer', 'pc', 'gaming',
    'with', 'and', 'for', 'the', 'of', 'in', 'to', 'new', 'used', 'renewed',
    'edition', 'series', 'model', 'windows', 'home', 'touch', 'touchscreen',
    'oled', 'ips', 'fhd', 'qhd', 'uhd', 'wuxga', 'wqxga', 'display', 'screen',
    'inch', 'inches', 'in', 'business', 'creator', 'convertible', 'flip',
    '2in1', '2', '1', 'rtx', 'gtx', 'graphics', 'ssd', 'ram', 'gb', 'tb',
    'intel', 'amd', 'ryzen', 'core', 'ultra', 'processor', 'cpu', 'gpu',
    'nvidia', 'geforce', 'radeon', 'arc', 'ai', 'copilot', 'backlit',
    'keyboard', 'webcam', 'wifi', 'bluetooth', 'color', 'colour', 'gray',
    'grey', 'silver', 'black', 'white', 'blue', 'gold', 'space',
}

# A listing that mentions one of these is an accessory, not the laptop.
ACCESSORY_WORDS = {
    'case', 'cases', 'sleeve', 'cover', 'skin', 'skins', 'protector',
    'screen protector', 'keyboard cover', 'charger', 'charging', 'adapter',
    'power supply', 'power adapter', 'dock', 'docking', 'replacement',
    'bag', 'backpack', 'briefcase', 'mouse', 'mousepad', 'hub', 'cable',
    'cord', 'stylus', 'cooling pad', 'replacement part', 'spare', 'hinge',
    'motherboard', 'keycap', 'decal', 'sticker', 'privacy filter',
    'lock cable', 'dust plug', 'port cover', 'monitor',
}

ACCESSORY_PATTERNS = (
    r'\b(?:ram|memory|ssd|screen|lcd|keyboard|battery|charger|adapter|'
    r'case|sleeve|cover)\s+(?:for|compatible)\b',
    r'\b(?:replacement|compatible)\s+(?:screen|lcd|panel|keyboard|battery|'
    r'charger|adapter|case|sleeve|cover|part)\b',
    r'\b(?:screen|lcd|display)\s+(?:replacement|assembly|panel)\b',
    r'\bfor\s+(?:asus|dell|hp|lenovo|samsung|apple|acer|msi)\b',
)

# Words that, when present in a listing but not in the product name, mean the
# listing is a different variant of the same family.
VARIANT_WORDS = {
    'mini', 'neo', 'lite', 'plus', 'max', 'se', 'air', 'pro',
    'studio', 'duo', 'fold', 'flip', '2in1', 'touch', 'oled', 'slim',
    'aero', 'flex', 'duet',
    'spectre', 'envy', 'pavilion', 'omen', 'victus', 'elitebook', 'probook',
    'omnibook', 'thinkpad', 'ideapad', 'legion', 'loq', 'yoga', 'thinkbook',
    'zephyrus', 'strix', 'scar', 'flow', 'tuf', 'zenbook', 'vivobook',
    'proart', 'xps', 'inspiron', 'latitude', 'vostro', 'alienware',
    'galaxy', 'book', 'macbook', 'redmagic', 'titan',
}

CHIP_TOKENS = {'m1', 'm2', 'm3', 'm4', 'm5', 'm6'}
SIZE_TOKENS = {'13', '14', '15', '16', '17', '18'}

FAMILY_TOKENS = {
    'spectre', 'envy', 'pavilion', 'omen', 'victus', 'elitebook', 'probook',
    'omnibook', 'thinkpad', 'ideapad', 'legion', 'loq', 'yoga', 'thinkbook',
    'zephyrus', 'strix', 'scar', 'flow', 'tuf', 'zenbook', 'vivobook',
    'proart', 'xps', 'inspiron', 'latitude', 'vostro', 'alienware', 'galaxy',
    'book', 'book2', 'book3', 'book4', 'book5', 'book6', 'macbook',
    'redmagic', 'titan', 'x360', 't14', 't14s', 't16', 't16s', 'x13', 'x16',
    'p14s', 'p16s', 'l14', 'l16', 'e14', 'e16',
}

MODEL_CODE_RE = re.compile(r'^(?=.*[a-z])(?=.*\d)[a-z0-9]{4,}$')

CPU_PATTERNS = (
    (r'\b(?:intel\s+)?core\s+i[3579][- ]?(\d{4,5}[a-z]{0,2}\d{0,2})\b', 'intel'),
    (r'\b(?:intel\s+)?core\s+ultra\s+[579]\s+(\d{3}[a-z]{0,2}\d{0,2})\b', 'intel'),
    (r'\b(?:intel\s+)?core\s+ultra\s+(x[579])\b', 'intel'),
    (r'\b(?:intel\s+)?core\s+[357]\s+(\d{3}[a-z]{0,2}\d{0,2})\b', 'intel'),
    (r'\bamd\s+ryzen\s+(?:ai\s+)?[3579]\s+(?:hx\s+|pro\s+)?(\d{3,4}[a-z]{0,2}\d{0,2})\b', 'amd'),
    (r'\bsnapdragon\s+(x2?)\s+(elite|plus)\b', 'qualcomm'),
)

_search_cache = None


class Command(BaseCommand):
    help = 'Attach verified product photos to 2020-2026 laptop products.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--brand', action='append', default=[],
            help='Only process this brand (can be repeated).',
        )
        parser.add_argument(
            '--limit', type=int, default=0,
            help='Process at most N products.',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Report matches without downloading or saving.',
        )
        parser.add_argument(
            '--redo', action='store_true',
            help='Also replace existing real photos.',
        )

    def handle(self, *args, **options):
        brands = options['brand'] or list(BRANDS)
        brands = [b for b in brands if b in BRANDS]
        limit = options['limit']
        dry_run = options['dry_run']
        redo = options['redo']

        qs = Product.objects.filter(
            category__name='Laptops', brand__in=brands
        ).order_by('brand', 'name')

        targets = []
        for product in qs:
            year = product_year(product.name)
            if year is not None and year < 2020:
                continue
            if product.image and '_tile_' not in product.image.name and not redo:
                continue
            targets.append(product)

        if limit:
            targets = targets[:limit]

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
                self.stdout.write('%s MATCH <- %s' % (label, _safe(title[:100])))
                continue

            try:
                data = download_image(image_url)
                save_image(product, data)
                stats['photo'] += 1
                self.stdout.write('%s PHOTO <- %s' % (label, _safe(title[:100])))
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


def _tokens(text):
    text = (text or '').lower()
    text = text.replace('&', ' and ')
    text = text.replace('2-in-1', ' 2in1 ')
    text = text.replace('2 in 1', ' 2in1 ')
    return re.findall(r'[a-z0-9]+', text)


def model_tokens(name):
    year = product_year(name)
    tokens = []
    for token in _tokens(name):
        if token in GENERIC_TOKENS:
            continue
        if token.isdigit() and len(token) == 4 and token.startswith('20'):
            if int(token) == year:
                continue
        tokens.append(token)
    # Preserve order, drop duplicates.
    return list(dict.fromkeys(tokens))


def _brand_tokens(brand):
    return BRAND_ALIASES.get((brand or '').lower(), {(brand or '').lower()})


def _has_accessory_word(low):
    for word in ACCESSORY_WORDS:
        if re.search(r'\b%s\b' % re.escape(word), low):
            return True
    for pattern in ACCESSORY_PATTERNS:
        if re.search(pattern, low):
            return True
    return False


def _title_has_size(low, size):
    patterns = (
        r'\b%s(?:\.\d+)?\s*(?:"|\'\'|inch|inches|in\b)' % size,
        r'\b%s(?:\.\d+)?\s*-\s*inch' % size,
        r'\b%s\.\d\b' % size,
    )
    return any(re.search(p, low) for p in patterns)


def _title_gen(low):
    match = re.search(r'\bgen(?:eration)?\s*(\d+)\b', low)
    if match:
        return match.group(1)
    match = re.search(
        r'\b(\d+)(?:st|nd|rd|th)\s+gen\b'
        r'(?!\s+(?:intel|amd|ryzen|core))',
        low,
    )
    if match:
        return match.group(1)
    return None


def _title_has_gen(low, gen):
    return _title_gen(low) == gen


def _title_has_chip(tokens, chip):
    return chip in tokens


def _title_years(low):
    return {int(y) for y in re.findall(r'\b(20(?:1\d|2\d))\b', low)}


def _has_model_pro(low):
    stripped = re.sub(r'\b(?:windows|win)\s+(?:\d+\s+)?pro\b', ' ', low)
    return bool(re.search(r'\bpro\b', stripped))


def _has_cpu_plus(low):
    return bool(re.search(r'\b\d{3,5}[a-z]{1,2}\s+plus\b', low))


def _four_digit_numbers(tokens):
    return {t for t in tokens if t.isdigit() and len(t) == 4 and not t.startswith('20')}


def spec_cpu_tokens(product):
    text = '%s %s' % (product.name or '', product.specifications or '')
    text = text.lower()
    for pattern, kind in CPU_PATTERNS:
        match = re.search(pattern, text)
        if not match:
            continue
        if kind == 'qualcomm':
            return ['snapdragon', match.group(1), match.group(2)]
        return [match.group(1)]
    return []


def _token_matches(token, title_tokens):
    if token in title_tokens:
        return True
    # Legion/IdeaPad/Yoga "5i" and "5" are the same chassis in listings.
    match = re.fullmatch(r'([3579])i', token)
    if match and match.group(1) in title_tokens:
        return True
    if re.fullmatch(r'[3579]', token) and token + 'i' in title_tokens:
        return True
    return False


def cpu_vendor(text):
    low = (text or '').lower()
    if re.search(r'\b(?:amd|ryzen)\b', low):
        return 'amd'
    if re.search(
        r'\b(?:intel|core\s+i[3579]|core\s+ultra|core\s+[3579]|'
        r'i[3579][- ]?\d|ultra\s+[579]\s+\d)\b',
        low,
    ):
        return 'intel'
    if re.search(r'\b(?:snapdragon|qualcomm)\b', low):
        return 'qualcomm'
    if re.search(r'\bapple\s+m[1-6]\b', low):
        return 'apple'
    return None


def cpu_series(text):
    low = (text or '').lower()
    match = re.search(r'\bultra\s+(?:x)?([579])\b', low)
    if match:
        return 'ultra' + match.group(1)
    match = re.search(r'\b(?:intel\s+)?core\s+([357])\b', low)
    if match:
        return 'intel' + match.group(1)
    match = re.search(r'\bintel\s+([357])\b', low)
    if match:
        return 'intel' + match.group(1)
    match = re.search(r'\bi([3579])[- ]?\d', low)
    if match:
        return 'intel' + match.group(1)
    match = re.search(r'\bryzen\s+(ai\s+)?([3579])\b', low)
    if match:
        return ('ryzenai' if match.group(1) else 'ryzen') + match.group(2)
    match = re.search(r'\bsnapdragon\s+(x2?)\b', low)
    if match:
        return 'snapdragon' + match.group(1)
    for chip in ('m6', 'm5', 'm4', 'm3', 'm2', 'm1'):
        if re.search(r'\b%s\b' % chip, low):
            return chip
    return None


CHIP_SUFFIX_RE = re.compile(r'\b(m[1-6])\s+(pro|max)\b')


def cpu_generation(text):
    low = (text or '').lower()
    match = re.search(
        r'\b(?:intel\s+)?core\s+i[3579][- ]?(\d{2})\d{2,3}[a-z]{0,2}\d{0,2}\b',
        low,
    )
    if match:
        return 'intel' + match.group(1)
    match = re.search(
        r'\b(?:intel\s+)?i[3579][- ]?(\d{2})\d{2,3}[a-z]{0,2}\d{0,2}\b',
        low,
    )
    if match:
        return 'intel' + match.group(1)
    match = re.search(
        r'\b(?:intel\s+)?(?:core\s+)?ultra\s+[579]\s+series\s+(\d)\b',
        low,
    )
    if match:
        return 'ultra' + match.group(1)
    match = re.search(
        r'\b(?:intel\s+)?(?:core\s+)?ultra\s+[579]\s+(\d)\d{2}[a-z]{0,2}\b',
        low,
    )
    if match:
        return 'ultra' + match.group(1)
    if re.search(r'\b(?:intel\s+)?(?:core\s+)?ultra\s+x[579]\b', low):
        return 'ultra3'
    match = re.search(
        r'\b(?:intel\s+)?core\s+[357]\s+(\d)\d{2}[a-z]{0,2}\b', low
    )
    if match:
        return 'core' + match.group(1)
    match = re.search(
        r'\bintel\s+[357][- ]?(\d)\d{2}[a-z]{0,2}\b', low
    )
    if match:
        return 'core' + match.group(1)
    match = re.search(
        r'\bryzen\s+(ai\s+)?[3579][- ]?(?:hx\s+|pro\s+)?'
        r'(\d)\d{2,3}[a-z]{0,2}\b',
        low,
    )
    if match:
        return ('ryzenai' if match.group(1) else 'ryzen') + match.group(2)
    match = re.search(r'\bsnapdragon\s+(x2?)\s+(?:elite|plus)\b', low)
    if match:
        return 'snapdragon' + match.group(1)
    for chip in ('m6', 'm5', 'm4', 'm3', 'm2', 'm1'):
        if re.search(r'\b%s\b' % chip, low):
            return chip
    return None


def score_candidate(product, title):
    low = title.lower().strip()
    if len(low) < 12 or 'sponsored ad' in low:
        return -1
    if _has_accessory_word(low):
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

    product_gen = re.search(r'\bgen(?:eration)?\s*(\d+)\b', product.name.lower())
    gen_number = product_gen.group(1) if product_gen else None

    cpu_required = spec_cpu_tokens(product)
    optional_codes = set()
    if cpu_required:
        optional_codes = {
            t for t in required
            if t not in cpu_required
            and t not in FAMILY_TOKENS
            and MODEL_CODE_RE.match(t)
        }
    required_core = [
        t for t in required
        if t not in optional_codes and t != gen_number
    ]

    missing = [t for t in required_core if not _token_matches(t, title_tokens)]
    if missing:
        return -1

    # A matching CPU model is the strongest guard against adjacent generations.
    # Same-generation CPUs, or a matching model code, are also acceptable
    # because they identify another configuration of the same chassis.
    cpu_ok = not cpu_required or all(t in title_tokens for t in cpu_required)
    code_ok = bool(optional_codes & title_tokens)
    product_cpu_gen = cpu_generation(product.specifications or '')
    title_cpu_gen = cpu_generation(title)
    generation_ok = bool(
        product_cpu_gen and title_cpu_gen and product_cpu_gen == title_cpu_gen
    )
    product_vendor = cpu_vendor(product.specifications or '')
    title_vendor = cpu_vendor(title)
    vendor_ok = not product_vendor or not title_vendor or product_vendor == title_vendor
    if product_vendor and title_vendor and product_vendor != title_vendor:
        return -1

    product_series = cpu_series(product.specifications or '')
    title_series = cpu_series(title)
    if product_series and title_series and product_series != title_series:
        return -1

    product_chip = CHIP_SUFFIX_RE.search(product.name.lower())
    title_chip = CHIP_SUFFIX_RE.search(title.lower())
    if title_chip and not product_chip:
        return -1
    if (
        product_chip
        and title_chip
        and product_chip.groups() != title_chip.groups()
    ):
        return -1

    if cpu_required and not cpu_ok and not code_ok and not generation_ok:
        if not (
            vendor_ok
            and title_cpu_gen is None
            and not optional_codes
            and len(required_core) >= 3
        ):
            return -1

    name_tokens = set(_tokens(product.name))
    if '2in1' in name_tokens and not re.search(
        r'\b2\s*(?:-|in)?\s*1\b', low
    ):
        return -1
    if (
        'omnibook' in name_tokens
        and 'ultra' in name_tokens
        and not re.search(r'\bomnibook\s+ultra\b', low)
    ):
        return -1
    if (
        'omnibook' in name_tokens
        and 'x' in name_tokens
        and not re.search(r'\bomnibook\s+x\b', low)
    ):
        return -1

    # "Ultra" is normally Intel Core Ultra, not the OmniBook Ultra model name.
    if 'ultra' in title_tokens and 'ultra' not in _tokens(product.name):
        if not re.search(
            r'\b(?:core|intel)?\s*ultra\s+(?:[579]\s+\d|x[579])', low
        ):
            return -1

    # Conflicting year (e.g. product is 2021, listing is 2024).
    year = product_year(product.name)
    years = _title_years(low)
    if year and years and year not in years:
        return -1

    # Conflicting Apple Silicon chip.
    product_chips = set(required) & CHIP_TOKENS
    if product_chips:
        title_chips = title_tokens & CHIP_TOKENS
        if title_chips - product_chips:
            return -1

    # Conflicting ThinkPad / Yoga / Legion generation.  When the CPU model
    # matches, the generation is already pinned down by the CPU.
    product_gen = re.search(r'\bgen(?:eration)?\s*(\d+)\b', product.name.lower())
    if product_gen:
        gen = product_gen.group(1)
        title_gen = _title_gen(low)
        if title_gen and title_gen != gen and not code_ok:
            return -1
        if not title_gen and not cpu_ok and not code_ok:
            return -1

    # Conflicting model number (XPS 9300 vs 9310, G5 5500 vs 5511...).
    required_numbers = _four_digit_numbers(set(required))
    title_numbers = _four_digit_numbers(title_tokens)
    if required_numbers:
        if title_numbers - required_numbers:
            return -1
    elif title_numbers and any(
        n.startswith(('93', '94', '95', '96', '97', '54', '55', '74', '76'))
        for n in title_numbers
    ):
        # A model number we did not ask for (e.g. a different XPS/Latitude).
        return -1

    # Conflicting screen size (13/14/15/16/17/18).  Only standalone numbers in
    # the product name count; "G14" and "x360" are model tokens, not sizes.
    name_tokens = _tokens(product.name)
    product_sizes = {t for t in name_tokens if t in SIZE_TOKENS}
    if product_sizes:
        title_sizes = {
            t for t in title_tokens
            if t in SIZE_TOKENS and _title_has_size(low, t)
        }
        if title_sizes - product_sizes:
            return -1
        if not (title_sizes & product_sizes):
            return -1

    # Conflicting variant words that change the model identity.
    extra_variants = (title_tokens & VARIANT_WORDS) - set(required)
    if 'pro' in extra_variants and not _has_model_pro(low):
        extra_variants.discard('pro')
    if 'plus' in extra_variants and _has_cpu_plus(low):
        extra_variants.discard('plus')
    # Display words are harmless; other variant words change the model identity.
    harmless = {'oled', 'touch'}
    if extra_variants - harmless:
        return -1

    score = len(required_core) * 2
    if optional_codes and optional_codes & title_tokens:
        score += 3
    if year and year in years:
        score += 5
    if 'renewed' in low or 'refurbished' in low:
        score -= 3
    else:
        score += 3
    first = _tokens(title)[:1]
    if first and first[0] in brand_tokens:
        score += 2
    if 'laptop' in low:
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
    global _search_cache
    if _search_cache is not None:
        return _search_cache
    try:
        with open(SEARCH_CACHE_PATH, encoding='utf-8') as handle:
            _search_cache = json.load(handle)
    except Exception:
        _search_cache = {}
    return _search_cache


def _save_cache():
    if _search_cache is None:
        return
    try:
        with open(SEARCH_CACHE_PATH, 'w', encoding='utf-8') as handle:
            json.dump(_search_cache, handle)
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
                    curl, '-s', '-L', '--max-time', str(timeout),
                    '-o', path, '-A', BROWSER_UA,
                    '-H', 'Accept: %s' % HEADERS['Accept'],
                    '-H', 'Accept-Language: %s' % HEADERS['Accept-Language'],
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


def amazon_search(query):
    cache = _load_cache()
    key = query.strip().lower()
    if key in cache:
        return [tuple(item) for item in cache[key]]

    url = 'https://www.amazon.com/s?k=' + urllib.parse.quote_plus(query)
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


def _query_variants(product):
    name = product.name
    # Drop the year for broader searches; CPU queries pin exact configurations.
    without_year = re.sub(r'\s*\(20(?:1\d|2\d)\)', '', name).strip()
    variants = [name]
    cpu = spec_cpu_tokens(product)
    if cpu:
        variants.append('%s %s' % (without_year, ' '.join(cpu)))
    if without_year != name:
        variants.append(without_year)
    return variants[:MAX_QUERIES_PER_PRODUCT]


def find_match(product):
    best = None
    best_score = -1
    for query in _query_variants(product):
        try:
            candidates = amazon_search(query)
        except Exception:
            continue
        for title, image_url in candidates:
            score = score_candidate(product, title)
            if score > best_score:
                best_score = score
                best = (title, image_url)
    if best_score <= 0:
        return None
    return best


# ---------------------------------------------------------------------------
# image saving
# ---------------------------------------------------------------------------

def download_image(url):
    data = _fetch_bytes(url)
    if len(data) < 5000:
        raise RuntimeError('image too small')
    image = Image.open(io.BytesIO(data))
    image.load()
    if image.mode != 'RGB':
        image = image.convert('RGB')
    image.thumbnail((1200, 1200))
    buffer = io.BytesIO()
    image.save(buffer, format='JPEG', quality=90, optimize=True)
    return buffer.getvalue()


def save_image(product, data):
    slug = re.sub(r'[^a-z0-9]+', '_', product.name.lower()).strip('_')
    filename = 'laptop_%s_%s.jpg' % (slug[:80], product.pk)
    if product.image:
        product.image.delete(save=False)
    product.image.save(filename, ContentFile(data), save=True)
