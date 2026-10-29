import re

from django.conf import settings
from django.db import models


_YOUTUBE_ID = re.compile(r'(?:v=|youtu\.be/|/embed/|/shorts/|/live/)([0-9A-Za-z_-]{6,20})')


# ---------------------------------------------------------------------------
# Generated product/accessory imagery
# ---------------------------------------------------------------------------
# Every product and accessory gets a distinct illustrated "picture" without
# needing a real photo: a coloured tile (colour derived from the brand) with a
# Font Awesome icon matching the item type, the brand logo and the item name.
# The icon is chosen from the item name first, then its category.

KIND_ICON = {
    'phone': 'fa-mobile-screen-button',
    'laptop': 'fa-laptop',
    'desktop': 'fa-desktop',
    'tablet': 'fa-tablet-screen-button',
    'handheld': 'fa-gamepad',
    'gamepad': 'fa-gamepad',
    'monitor': 'fa-display',
    'tv': 'fa-tv',
    'camera': 'fa-camera',
    'webcam': 'fa-video',
    'lens': 'fa-camera-retro',
    'projector': 'fa-film',
    'printer': 'fa-print',
    'scanner': 'fa-print',
    'ink': 'fa-droplet',
    'router': 'fa-wifi',
    'watch': 'fa-clock',
    'strap': 'fa-clock',
    'earbuds': 'fa-headphones-simple',
    'headphone': 'fa-headphones',
    'headset': 'fa-headset',
    'speaker': 'fa-volume-high',
    'microphone': 'fa-microphone',
    'powerbank': 'fa-battery-full',
    'battery': 'fa-battery-half',
    'charger': 'fa-plug-circle-bolt',
    'cable': 'fa-plug',
    'hub': 'fa-usb',
    'stand': 'fa-fan',
    'case': 'fa-shield-halved',
    'screenprotector': 'fa-shield',
    'bag': 'fa-briefcase',
    'keyboard': 'fa-keyboard',
    'mouse': 'fa-computer-mouse',
    'storage': 'fa-hard-drive',
    'pen': 'fa-pen',
    'tag': 'fa-tag',
    'light': 'fa-lightbulb',
    'scale': 'fa-scale-balanced',
    'default': 'fa-microchip',
}

CATEGORY_KIND = {
    'Smartphones': 'phone',
    'Laptops': 'laptop',
    'Tablets': 'tablet',
    'Monitors': 'monitor',
    'Desktops': 'desktop',
    'Gaming Handhelds': 'handheld',
    'Smart TVs': 'tv',
    'Cameras': 'camera',
    'Printers': 'printer',
    'Networking': 'router',
    'Wearables': 'watch',
    'Audio': 'headphone',
    'Cases & Protection': 'case',
    'Chargers & Cables': 'charger',
    'Peripherals': 'keyboard',
    'Storage': 'storage',
    'Troubleshooting': 'default',
}

# Order matters: the first keyword found in the lower-cased name wins.
_NAME_RULES = [
    (('airpods', 'earbuds', 'eartips', 'earpods', 'buds', 'bowie', 'liberty',
      'wf-', 'enco', 'cyberbuds', 'live beam', 't3 pro anc'), 'earbuds'),
    (('headset', 'quantum', 'cetra', 'delta ii', 'cloud iii', 'g733'), 'headset'),
    (('headphone', 'wh-', 'ch520', 'zone vibe', 'tune 770', 'space q45',
      'tune 5'), 'headphone'),
    (('speaker', 'partybox', 'flip 6', 'charge 5', 'srs-', 'xb100',
      'motion x', 'aequr', 'vo10', 'swing'), 'speaker'),
    (('microphone', 'boom mic'), 'microphone'),
    (('cable', 'lightning', 'usb-c to', 'type-c'), 'cable'),
    (('power bank', 'powerbank', 'powercore', 'magnetic battery', 'magcharge',
      'magnetic wireless power'), 'powerbank'),
    (('hub', 'dock', 'docking', 'card reader', 'otg'), 'hub'),
    (('stand', 'cooler', 'cooling pad', 'cooling'), 'stand'),
    (('keyboard', 'keycap'), 'keyboard'),
    (('mouse', 'mousepad', 'g304', 'g502', 'g pro x', 'harpe', 'cestus',
      'ms5320'), 'mouse'),
    (('webcam', 'brio'), 'webcam'),
    (('tempered glass', 'screen protector', 'privacy shutter'), 'screenprotector'),
    (('backpack', 'briefcase'), 'bag'),
    (('sleeve', 'case', 'cover', 'flip cover', 'flap suit', 'pouch',
      'armor'), 'case'),
    (('battery', 'np-fz', 'lp-e17'), 'battery'),
    (('strap', 'sport band', 'trail band', 'watch band'), 'strap'),
    (('stylus', 'smart pen', 'tab pen', 'pen plus', ' pen '), 'pen'),
    (('smarttag', ' tag '), 'tag'),
    (('litra', 'streaming light'), 'light'),
    (('smart scale', 'eufy'), 'scale'),
    (('ink bottle', 'ink pack', ' ink ', 'inkjet', 'refill ink', 'glossy',
      'photo paper', 'matte paper', 'toner', 'paper'), 'ink'),
    (('lens',), 'lens'),
    (('projector', '3lcd', 'eb-x'), 'projector'),
    (('scanner', 'perfection'), 'scanner'),
    (('nas', 'ssd', 'microsd', 'sd card', 'memory card', 'hard drive',
      't7 shield', 'evo plus'), 'storage'),
    (('controller', 'gamepad', 'dualsense'), 'gamepad'),
    (('camera', 'eos', 'alpha', 'powershot', 'zv-e'), 'camera'),
    (('charger', 'power adapter', 'adapter', 'gan', 'supervooc', 'flashcharge',
      'airvooc', 'charge kit', 'nano', 'brick'), 'charger'),
    (('65w', '45w', '33w', '25w', '80w', '50w', '90w', '120w', '100w', '140w',
      '18w'), 'charger'),
]


def _item_kind(name, category_name):
    low = (name or '').lower()
    for keywords, kind in _NAME_RULES:
        for keyword in keywords:
            if keyword in low:
                return kind
    return CATEGORY_KIND.get((category_name or '').strip(), 'default')


def _brand_tint(brand):
    """Stable palette class (pt-0..pt-7) so each brand gets its own colour."""
    code = 0
    for char in (brand or '').lower():
        code = (code * 31 + ord(char)) % 100003
    return 'pt-%d' % (code % 8)


class Category(models.Model):
    """Grouping for products, accessories and solutions (ex. Laptops, Audio, Chargers)."""

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'techfix_category'
        verbose_name_plural = 'categories'
        ordering = ['name']

    def __str__(self):
        return self.name


class Product(models.Model):
    """Main technology devices (laptop, phone, printer, router)."""

    name = models.CharField(max_length=255)
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='products'
    )
    brand = models.CharField(max_length=100, blank=True)
    description = models.TextField()
    specifications = models.TextField(blank=True, help_text='RAM, CPU, Storage, etc.')
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    stock_quantity = models.PositiveIntegerField(default=0)
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'techfix_product'
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    @property
    def kind(self):
        return _item_kind(self.name, self.category.name if self.category else '')

    @property
    def display_icon(self):
        return 'fas ' + KIND_ICON.get(self.kind, KIND_ICON['default'])

    @property
    def display_tint(self):
        return _brand_tint(self.brand)

    @property
    def spec_list(self):
        """Split the free-text specs into a clean list for detail pages."""
        raw = (self.specifications or '').replace('\r', '')
        parts = []
        for chunk in raw.replace('\n', ',').split(','):
            chunk = chunk.strip()
            if chunk:
                parts.append(chunk)
        return parts


class Accessory(models.Model):
    """Add-ons: cases, chargers, keyboards, earbuds, cables."""

    name = models.CharField(max_length=255)
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='accessories'
    )
    brand = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    compatibility_notes = models.TextField(
        blank=True, help_text='Ex. Compatible with USB-C laptops'
    )
    stock_quantity = models.PositiveIntegerField(default=0)
    image = models.ImageField(upload_to='accessories/', blank=True, null=True)
    compatible_products = models.ManyToManyField(
        Product, blank=True, related_name='compatible_accessories'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'techfix_accessory'
        verbose_name_plural = 'accessories'
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    @property
    def kind(self):
        return _item_kind(self.name, self.category.name if self.category else '')

    @property
    def display_icon(self):
        return 'fas ' + KIND_ICON.get(self.kind, KIND_ICON['default'])

    @property
    def display_tint(self):
        return _brand_tint(self.brand)


class Solution(models.Model):
    """Step-by-step fix for a common technology problem."""

    DIFFICULTY_CHOICES = [
        ('Easy', 'Easy'),
        ('Medium', 'Medium'),
        ('Hard', 'Hard'),
    ]

    title = models.CharField(max_length=255)
    problem_description = models.TextField(help_text='Symptoms / common issue')
    steps = models.TextField(help_text='Step 1, Step 2, ...')
    difficulty_level = models.CharField(
        max_length=10, choices=DIFFICULTY_CHOICES, default='Easy'
    )
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='solutions'
    )
    related_product = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True, blank=True, related_name='solutions'
    )
    video_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'techfix_solution'
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    @property
    def video_thumb(self):
        """YouTube thumbnail for video_url (blank when it is not a YouTube link)."""
        match = _YOUTUBE_ID.search(self.video_url or '')
        if not match:
            return ''
        return 'https://i.ytimg.com/vi/%s/hqdefault.jpg' % match.group(1)


class RecentActivity(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='recent_activities',
    )
    kind = models.CharField(max_length=40)
    title = models.CharField(max_length=120)
    url = models.CharField(max_length=2048)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'techfix_recent_activity'
        ordering = ['-created_at', '-pk']

    def __str__(self):
        return self.title
