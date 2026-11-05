import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Avg, Q
from django.utils.functional import cached_property


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


def _has_real_catalog_photo(image):
    return bool(image and '_tile_' not in image.name)


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
    price = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True, default=None
    )
    source_url = models.URLField(blank=True)
    stock_quantity = models.PositiveIntegerField(
        blank=True, null=True, default=None
    )
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    online_rating = models.DecimalField(
        max_digits=3, decimal_places=2, blank=True, null=True,
        help_text='Aggregate rating imported from an online catalog.',
    )
    online_rating_count = models.PositiveIntegerField(blank=True, null=True)
    online_rating_source = models.CharField(max_length=100, blank=True)
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
    def has_real_photo(self):
        return _has_real_catalog_photo(self.image)

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

    @cached_property
    def review_total(self):
        count = getattr(self, '_review_count', None)
        return count if count is not None else self.reviews.count()

    @cached_property
    def average_rating(self):
        value = getattr(self, '_review_avg', None)
        return value if value is not None else self.reviews.aggregate(value=Avg('rating'))['value']

    @property
    def display_rating(self):
        if self.review_total:
            return self.average_rating
        return self.online_rating

    @property
    def display_rating_count(self):
        if self.review_total:
            return self.review_total
        return self.online_rating_count or 0

    @property
    def rating_is_online(self):
        return not self.review_total and self.online_rating is not None


class Accessory(models.Model):
    """Add-ons: cases, chargers, keyboards, earbuds, cables."""

    name = models.CharField(max_length=255)
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='accessories'
    )
    brand = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True, default=None
    )
    source_url = models.URLField(blank=True)
    compatibility_notes = models.TextField(
        blank=True, help_text='Ex. Compatible with USB-C laptops'
    )
    stock_quantity = models.PositiveIntegerField(
        blank=True, null=True, default=None
    )
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

    @property
    def has_real_photo(self):
        return _has_real_catalog_photo(self.image)

    @cached_property
    def review_total(self):
        count = getattr(self, '_review_count', None)
        return count if count is not None else self.reviews.count()

    @cached_property
    def average_rating(self):
        value = getattr(self, '_review_avg', None)
        return value if value is not None else self.reviews.aggregate(value=Avg('rating'))['value']

    @property
    def display_rating(self):
        return self.average_rating

    @property
    def display_rating_count(self):
        return self.review_total

    @property
    def rating_is_online(self):
        return False


class Review(models.Model):
    """Customer rating and feedback for a product or accessory."""

    RATING_CHOICES = [
        (1, '1 star'),
        (2, '2 stars'),
        (3, '3 stars'),
        (4, '4 stars'),
        (5, '5 stars'),
    ]

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='reviews',
    )
    accessory = models.ForeignKey(
        Accessory,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='reviews',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reviews',
    )
    rating = models.PositiveSmallIntegerField(choices=RATING_CHOICES)
    title = models.CharField(max_length=120, blank=True)
    comment = models.TextField()
    is_sample = models.BooleanField(
        default=False,
        help_text='Marks demonstration reviews that are not from real customers.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'techfix_review'
        ordering = ['-created_at', '-pk']
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(product__isnull=False, accessory__isnull=True)
                    | Q(product__isnull=True, accessory__isnull=False)
                ),
                name='techfix_review_exactly_one_item',
            ),
            models.UniqueConstraint(
                fields=['user', 'product'],
                condition=Q(product__isnull=False),
                name='techfix_review_unique_user_product',
            ),
            models.UniqueConstraint(
                fields=['user', 'accessory'],
                condition=Q(accessory__isnull=False),
                name='techfix_review_unique_user_accessory',
            ),
        ]

    def __str__(self):
        item = self.product or self.accessory
        return f'{item} - {self.rating}/5 by {self.user}'

    def clean(self):
        if (self.product is None) == (self.accessory is None):
            raise ValidationError(
                'Choose exactly one product or accessory for this review.'
            )


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
