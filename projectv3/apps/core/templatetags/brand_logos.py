"""Template helpers for brand logos.

Brands in TechFix are plain product/accessory values (not a model), so the
logo shown for each brand is resolved from a static file in
``static/img/brands/`` via a simple name -> filename map.  Anything without a
mapped logo falls back to the lettered monogram already used in the templates.
"""

from django import template
from django.templatetags.static import static

register = template.Library()

# Brand name (lower-cased) -> file inside static/img/brands/.
# Names are matched case-insensitively; aliases cover wording differences.
BRAND_LOGOS = {
    'acer': 'acer.svg',
    'anker': 'anker.png',
    'apple': 'apple.svg',
    'asus': 'asus.svg',
    'baseus': 'baseus.png',
    'canon': 'canon.png',
    'dell': 'dell.svg',
    'epson': 'epson.svg',
    'gigabyte': 'gigabyte.png',
    'google': 'google.svg',
    'honor': 'honor.svg',
    'hp': 'hp.svg',
    'huawei': 'huawei.svg',
    'infinix': 'infinix.png',
    'itel': 'itel.png',
    'jbl': 'jbl.svg',
    'lenovo': 'lenovo.svg',
    'lg': 'lg.svg',
    'logitech': 'logitech.png',
    'microsoft': 'microsoft.png',
    'msi': 'msi.svg',
    'oneplus': 'oneplus.svg',
    'oppo': 'oppo.svg',
    'razer': 'razer.svg',
    'realme': 'realme.png',
    'redmagic': 'redmagic.png',
    'samsung': 'samsung.svg',
    'sony': 'sony.svg',
    'techfix': 'techfix.svg',
    'tecno': 'tecno.png',
    'tp-link': 'tplink.svg',
    'tplink': 'tplink.svg',
    'ugreen': 'ugreen.png',
    'vivo': 'vivo.svg',
    'xiaomi': 'xiaomi.svg',
}


def _logo_filename(brand):
    """Return the static logo filename for a brand, or '' if none is mapped."""
    return BRAND_LOGOS.get((brand or '').strip().lower(), '')


@register.filter
def brand_logo(brand):
    """Return the static URL of a brand logo, or '' when there is no logo."""
    filename = _logo_filename(brand)
    return static('img/brands/' + filename) if filename else ''
