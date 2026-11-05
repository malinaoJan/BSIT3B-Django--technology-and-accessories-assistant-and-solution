"""Seed a curated 2020-2026 tablet catalog for the requested brands.

Sony is intentionally absent because Sony has not released a tablet since the
Xperia Z4 Tablet in 2015. The command is safe to re-run, preserves existing
photos, and moves misclassified tablets into the Tablets category.

Run from the project root:
    venv\\Scripts\\python.exe projectv3\\manage.py seed_tablet_catalog_2020_2026
    venv\\Scripts\\python.exe projectv3\\manage.py seed_tablet_catalog_2020_2026 --dry-run
"""

from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.core.models import Category, Product


TABLETS = [
    ('Apple', 'Apple iPad 8th Gen 10.2 (2020)', 22990,
     '10.2in Retina, Apple A12 Bionic, 3GB/32GB, Apple Pencil 1, 8827mAh, 490g'),
    ('Apple', 'Apple iPad Air 4th Gen 10.9 (2020)', 32990,
     '10.9in Liquid Retina, Apple A14 Bionic, 4GB/64GB, USB-C, Apple Pencil 2, 7606mAh'),
    ('Apple', 'Apple iPad Pro 11 2nd Gen (2020)', 42990,
     '11in Liquid Retina 120Hz, Apple A12Z Bionic, 6GB/128GB, LiDAR, Face ID, 7538mAh'),
    ('Apple', 'Apple iPad Pro 12.9 4th Gen (2020)', 52990,
     '12.9in Liquid Retina 120Hz, Apple A12Z Bionic, 6GB/128GB, LiDAR, Face ID, 9720mAh'),
    ('Apple', 'Apple iPad 9th Gen 10.2 (2021)', 19990,
     '10.2in Retina, Apple A13 Bionic, 3GB/64GB, Center Stage, Apple Pencil 1, 8557mAh'),
    ('Apple', 'Apple iPad mini 6th Gen 8.3 (2021)', 27990,
     '8.3in Liquid Retina, Apple A15 Bionic, 4GB/64GB, USB-C, Apple Pencil 2, 5078mAh'),
    ('Apple', 'Apple iPad Pro 11 M1 3rd Gen (2021)', 47990,
     '11in Liquid Retina 120Hz, Apple M1, 8GB/128GB, Thunderbolt, Face ID, 7538mAh'),
    ('Apple', 'Apple iPad Pro 12.9 M1 5th Gen (2021)', 62990,
     '12.9in Liquid Retina XDR 120Hz, Apple M1, 8GB/128GB, Thunderbolt, 10758mAh'),
    ('Apple', 'Apple iPad 10th Gen', 26990,
     '10.9in Liquid Retina, Apple A14 Bionic, 4GB/64GB, USB-C, landscape front camera, 7606mAh'),
    ('Apple', 'Apple iPad Air 5th Gen 10.9 M1 (2022)', 37990,
     '10.9in Liquid Retina, Apple M1, 8GB/64GB, USB-C, Apple Pencil 2, 7606mAh'),
    ('Apple', 'Apple iPad Pro 11 M2 4th Gen (2022)', 54990,
     '11in Liquid Retina 120Hz, Apple M2, 8GB/128GB, ProRes, Apple Pencil hover, 7538mAh'),
    ('Apple', 'Apple iPad Pro 12.9 M2 6th Gen (2022)', 69990,
     '12.9in Liquid Retina XDR 120Hz, Apple M2, 8GB/128GB, ProRes, Apple Pencil hover, 10758mAh'),
    ('Apple', 'Apple iPad Air 11 M2 (2024)', 39990,
     '11in Liquid Retina, Apple M2, 8GB/128GB, Apple Pencil Pro, 7606mAh'),
    ('Apple', 'Apple iPad Air 13 M2 (2024)', 49990,
     '13in Liquid Retina, Apple M2, 8GB/128GB, Apple Pencil Pro, 9705mAh'),
    ('Apple', 'Apple iPad Pro 11 M4 (2024)', 59990,
     '11in Ultra Retina XDR OLED 120Hz, Apple M4, 8GB/256GB, Face ID, 8160mAh'),
    ('Apple', 'Apple iPad Pro 13 M4 (2024)', 79990,
     '13in Ultra Retina XDR OLED 120Hz, Apple M4, 8GB/256GB, Face ID, 10290mAh'),
    ('Apple', 'Apple iPad mini 7th Gen 8.3 A17 Pro (2024)', 34990,
     '8.3in Liquid Retina, Apple A17 Pro, 8GB/128GB, Apple Pencil Pro, 5078mAh'),
    ('Apple', 'Apple iPad 11th Gen 11 A16 (2025)', 21990,
     '11in Liquid Retina, Apple A16, 6GB/128GB, USB-C, Apple Pencil 1 support, 7606mAh'),
    ('Apple', 'Apple iPad Air 11 M3 (2025)', 42990,
     '11in Liquid Retina, Apple M3, 8GB/128GB, Apple Pencil Pro, 7606mAh'),
    ('Apple', 'Apple iPad Air 13 M3 (2025)', 52990,
     '13in Liquid Retina, Apple M3, 8GB/128GB, Apple Pencil Pro, 9705mAh'),
    ('Apple', 'Apple iPad Pro 11 M5 (2025)', 64990,
     '11in Ultra Retina XDR OLED 120Hz, Apple M5, 12GB/256GB, Face ID, 8160mAh'),
    ('Apple', 'Apple iPad Pro 13 M5 (2025)', 84990,
     '13in Ultra Retina XDR OLED 120Hz, Apple M5, 12GB/256GB, Face ID, 10290mAh'),
    ('Apple', 'Apple iPad Air 11 M4 (2026)', 46990,
     '11in Liquid Retina, Apple M4, 12GB/128GB, Apple Pencil Pro, 7606mAh'),
    ('Apple', 'Apple iPad Air 13 M4 (2026)', 56990,
     '13in Liquid Retina, Apple M4, 12GB/128GB, Apple Pencil Pro, 9705mAh'),
    ('Apple', 'Apple iPad mini 8th Gen 8.5 A20 Pro (2026)', 39990,
     '8.5in OLED, Apple A20 Pro, 8GB/128GB, Apple Pencil Pro, 5078mAh'),

    ('ASUS', 'ASUS ROG Flow Z13 (2022)', 89995,
     '13.4in FHD+ 120Hz touch, Intel Core i9-12900H, RTX 3050 Ti 4GB, 16GB/1TB, 56Wh'),
    ('ASUS', 'ASUS ROG Flow Z13 (2023)', 109995,
     '13.4in QHD 165Hz touch, Intel Core i9-13900H, RTX 4060 8GB, 16GB/1TB, 56Wh'),
    ('ASUS', 'ASUS ROG Flow Z13 (2024)', 129995,
     '13.4in QHD 165Hz touch, AMD Ryzen 9 8945HS, RTX 4070 8GB, 32GB/1TB, 70Wh'),
    ('ASUS', 'ROG Flow Z13 (2025)', 149995,
     '13in 2.5K 180Hz touch, AMD Ryzen AI Max+ 395, Radeon 8060S, 32GB/1TB, 70Wh'),
    ('ASUS', 'ASUS ProArt PZ13 (2024)', 99995,
     '13.3in 3K OLED touch, Snapdragon X Plus, 16GB/1TB, 70Wh, 0.85kg'),
    ('ASUS', 'ASUS ExpertBook B3 Detachable (2022)', 34995,
     '10.5in WUXGA touch, Snapdragon 7c Gen 2, 8GB/128GB, 21hr battery, garaged stylus'),
    ('ASUS', 'ASUS Chromebook Detachable CM3 (2021)', 24995,
     '10.5in WUXGA touch, MediaTek MT8183, 4GB/64GB, ChromeOS, garaged stylus'),
    ('ASUS', 'ASUS Chromebook Detachable CZ1 (2022)', 19995,
     '10.1in WUXGA touch, MediaTek Kompanio 500, 4GB/64GB, ChromeOS, military-grade durability'),

    ('Dell', 'Dell Latitude 7320 Detachable (2021)', 69995,
     '13in 3:2 FHD+ touch, Intel Core i5-1130G7, 8GB/256GB, 789g tablet, Thunderbolt 4'),
    ('Dell', 'Dell Latitude 7230 Rugged Extreme Tablet (2022)', 89995,
     '12in FHD 1000-nit touch, Intel Core i5-1240U, 16GB/512GB, IP-65, MIL-STD-810H'),
    ('Dell', 'Dell Latitude 7030 Rugged Extreme Tablet (2023)', 79995,
     '10.1in FHD 1000-nit touch, Intel Core i5-1230U, 16GB/512GB, IP-65, MIL-STD-810H'),
    ('Dell', 'Dell Latitude 7350 Detachable (2024)', 99995,
     '13in 3:2 QHD+ touch, Intel Core Ultra 7 165U, 16GB/512GB, Wi-Fi 7, 8MP cameras'),
    ('Dell', 'Dell Pro Rugged 10 Tablet (2025)', 89995,
     '10.1in FHD 1200-nit touch, Intel Core Ultra 5 225U, 16GB/512GB, IP-66, 1.04kg'),
    ('Dell', 'Dell Pro Rugged 12 Tablet (2025)', 109995,
     '12in FHD 1200-nit touch, Intel Core Ultra 7 265U, 16GB/512GB, IP-65, dual hot-swap battery'),

    ('HP', 'HP Elite x2 G8 (2021)', 69995,
     '13in 3:2 touch 1000-nit, Intel Core i5-1135G7, 8GB/256GB, 820g tablet, Thunderbolt 4'),
    ('HP', 'HP Chromebook x2 11 (2021)', 32995,
     '11in 2K 3:2 touch, Snapdragon 7c, 8GB/64GB, ChromeOS, USI pen and keyboard included'),

    ('Lenovo', 'Lenovo Chromebook Duet 10.1 (2020)', 15990,
     '10.1in FHD touch, MediaTek Helio P60T, 4GB/64GB, ChromeOS, detachable keyboard'),
    ('Lenovo', 'Lenovo Tab M10 HD (2020)', 10990,
     '10.1in HD touch, MediaTek Helio P22T, 2GB/32GB, Android, 5000mAh'),
    ('Lenovo', 'Lenovo Tab M10 FHD Plus (2020)', 13990,
     '10.3in FHD touch, MediaTek Helio P22T, 4GB/64GB, Android, 5000mAh'),
    ('Lenovo', 'Lenovo Tab P11 (2021)', 18990,
     '11in 2K touch, Snapdragon 662, 6GB/128GB, Android, 7700mAh'),
    ('Lenovo', 'Lenovo Tab P11 Pro (2021)', 32990,
     '11.5in 2K OLED touch, Snapdragon 730G, 6GB/128GB, Android, 8600mAh'),
    ('Lenovo', 'Lenovo ThinkPad X12 Detachable Gen 1 (2021)', 69995,
     '12.3in FHD+ 3:2 touch, Intel Core i5-1130G7, 8GB/256GB, Windows 11, detachable keyboard'),
    ('Lenovo', 'Lenovo Chromebook Duet 5 (2021)', 26990,
     '13.3in FHD OLED touch, Snapdragon 7c Gen 2, 8GB/128GB, ChromeOS, detachable keyboard'),
    ('Lenovo', 'Lenovo Tab P11 Pro 2nd Gen (2022)', 34990,
     '11.2in 2.5K OLED 120Hz touch, MediaTek Kompanio 1300T, 8GB/256GB, Android, 8000mAh'),
    ('Lenovo', 'Lenovo Tab M10 Plus 3rd Gen (2022)', 14990,
     '10.6in 2K touch, MediaTek Helio G80, 4GB/128GB, Android, 7700mAh'),
    ('Lenovo', 'Lenovo Chromebook Duet 3 (2022)', 20990,
     '10.95in 2K touch, Snapdragon 7c Gen 2, 4GB/64GB, ChromeOS, detachable keyboard'),
    ('Lenovo', 'Lenovo Tab P12 12.7', 27990,
     '12.7in 3K touch, MediaTek Dimensity 7050, 8GB/128GB, Android, 10200mAh'),
    ('Lenovo', 'Lenovo Tab P12 Pro (2023)', 39990,
     '12.6in 2K AMOLED 120Hz touch, Snapdragon 870, 8GB/256GB, Android, 10200mAh'),
    ('Lenovo', 'Lenovo Tab Extreme (2023)', 59990,
     '14.5in 3K OLED 120Hz touch, MediaTek Dimensity 9000, 12GB/256GB, Android, 12300mAh'),
    ('Lenovo', 'Lenovo Tab M9 (2023)', 9990,
     '9in HD touch, MediaTek Helio G80, 4GB/64GB, Android, 5100mAh'),
    ('Lenovo', 'Lenovo Tab M11 11', 14990,
     '11in FHD 90Hz touch, MediaTek Helio G88, 4GB/128GB, Android, 7040mAh'),
    ('Lenovo', 'Lenovo Yoga Tab 11 (2024)', 19990,
     '11in 2K touch, MediaTek Helio G99, 8GB/128GB, Android, 7700mAh'),
    ('Lenovo', 'Lenovo Legion Y700 (2022)', 29990,
     '8.8in 2.5K 120Hz touch, Snapdragon 870, 8GB/128GB, Android, 6550mAh'),
    ('Lenovo', 'Lenovo Legion Y700 2nd Gen (2023)', 34990,
     '8.8in 2.5K 144Hz touch, Snapdragon 8+ Gen 1, 12GB/256GB, Android, 6550mAh'),
    ('Lenovo', 'Lenovo Legion Y700 (2024)', 39990,
     '8.8in 2.5K 165Hz touch, Snapdragon 8 Gen 3, 12GB/256GB, Android, 6550mAh'),
    ('Lenovo', 'Lenovo Legion Tab Y700 (2025)', 44990,
     '8.8in 2.5K 165Hz touch, Snapdragon 8 Gen 3, 12GB/256GB, Android, 6550mAh'),
    ('Lenovo', 'Lenovo Tab Plus (2024)', 21990,
     '11.5in 2K touch, MediaTek Helio G99, 8GB/128GB, Android, 8600mAh, 8 JBL speakers'),
    ('Lenovo', 'Lenovo Yoga Pad Pro AI (2024)', 42990,
     '12.7in 3K touch, Snapdragon 8 Gen 3, 12GB/256GB, Android, 10200mAh'),
    ('Lenovo', 'Lenovo Yoga Tab Plus AI (2025)', 44990,
     '12.7in 3K touch, Snapdragon 8 Gen 3, 12GB/256GB, Android, 10200mAh'),
    ('Lenovo', 'Lenovo Yoga Tab 11.1 AI (2025)', 34990,
     '11.1in 3.2K 144Hz touch, MediaTek Dimensity 8400, 12GB/256GB, Android, 10200mAh'),
    ('Lenovo', 'Lenovo Idea Tab 11 (2025)', 16990,
     '11in 2.5K touch, MediaTek Dimensity 6300, 8GB/128GB, Android, 7040mAh'),
    ('Lenovo', 'Lenovo Idea Tab Pro 12.7 (2025)', 26990,
     '12.7in 3K touch, MediaTek Dimensity 7300, 8GB/128GB, Android, 10200mAh'),
    ('Lenovo', 'Lenovo Idea Tab Plus (2025)', 19990,
     '12.1in 2.5K touch, MediaTek Dimensity 6400, 8GB/128GB, Android, 10000mAh'),
    ('Lenovo', 'Legion Tab Gen 5', 54990,
     '8.8in 3K 165Hz touch, Snapdragon 8 Elite Gen 5, 12GB/256GB, Android, 9000mAh'),
    ('Lenovo', 'Lenovo Yoga Tab 11.1 Gen 2 (2026)', 39990,
     '11.1in 3.2K 144Hz touch, Snapdragon 8s Gen 4, 12GB/256GB, Android, 10200mAh'),
    ('Lenovo', 'Lenovo Yoga Tab Plus 13 Gen 2 (2026)', 49990,
     '13in 3.2K 144Hz touch, Snapdragon 8 Elite Gen 5, 16GB/512GB, Android, 11000mAh'),
    ('Lenovo', 'Lenovo Tab Plus Gen 2 (2026)', 24990,
     '11.5in 2.5K touch, MediaTek Dimensity 7300, 8GB/256GB, Android, 8600mAh'),
    ('Lenovo', 'Lenovo Idea Tab Pro Gen 2 (2026)', 29990,
     '13in 3K touch, Snapdragon 8s Gen 4, 12GB/256GB, Android, 10200mAh'),

    ('Samsung', 'Samsung Galaxy Tab S6 Lite (2020)', 17990,
     '10.4in 2K touch, Exynos 9611, 4GB/64GB, Android, S Pen, 7040mAh'),
    ('Samsung', 'Samsung Galaxy Tab S6 5G (2020)', 42990,
     '10.5in 2K AMOLED touch, Snapdragon 855, 6GB/128GB, Android, 5G, 7040mAh'),
    ('Samsung', 'Samsung Galaxy Tab S7 (2020)', 37990,
     '11in 2.5K 120Hz touch, Snapdragon 865+, 6GB/128GB, Android, S Pen, 8000mAh'),
    ('Samsung', 'Samsung Galaxy Tab S7+ (2020)', 47990,
     '12.4in 2.8K AMOLED 120Hz touch, Snapdragon 865+, 6GB/128GB, Android, S Pen, 10090mAh'),
    ('Samsung', 'Samsung Galaxy Tab A 8.4 (2020)', 12990,
     '8.4in 2K touch, 3GB/32GB, Android, 5000mAh, LTE'),
    ('Samsung', 'Samsung Galaxy Tab A7 10.4 (2020)', 15990,
     '10.4in 2K touch, Snapdragon 662, 3GB/32GB, Android, 7040mAh'),
    ('Samsung', 'Samsung Galaxy Tab Active3 (2020)', 29990,
     '8in 2K touch, Exynos 9810, 4GB/64GB, Android, IP68, MIL-STD-810H, S Pen'),
    ('Samsung', 'Samsung Galaxy Tab S7 FE (2021)', 27990,
     '12.4in 2.5K touch, Snapdragon 750G, 4GB/64GB, Android, S Pen, 10090mAh'),
    ('Samsung', 'Samsung Galaxy Tab A7 Lite (2021)', 9990,
     '8.7in HD+ touch, MediaTek Helio P22T, 3GB/32GB, Android, 5100mAh'),
    ('Samsung', 'Samsung Galaxy Tab S8 (2022)', 41990,
     '11in 2.5K 120Hz touch, Snapdragon 8 Gen 1, 8GB/128GB, Android, S Pen, 8000mAh'),
    ('Samsung', 'Samsung Galaxy Tab S8+ (2022)', 52990,
     '12.4in 2.8K AMOLED 120Hz touch, Snapdragon 8 Gen 1, 8GB/128GB, Android, S Pen, 10090mAh'),
    ('Samsung', 'Samsung Galaxy Tab S8 Ultra (2022)', 64990,
     '14.6in 2.9K AMOLED 120Hz touch, Snapdragon 8 Gen 1, 8GB/128GB, Android, S Pen, 11200mAh'),
    ('Samsung', 'Samsung Galaxy Tab S6 Lite (2022)', 18990,
     '10.4in 2K touch, Snapdragon 720G, 4GB/64GB, Android, S Pen, 7040mAh'),
    ('Samsung', 'Samsung Galaxy Tab A8 10.5 (2022)', 14990,
     '10.5in 2K touch, Unisoc Tiger T618, 3GB/32GB, Android, 7040mAh'),
    ('Samsung', 'Samsung Galaxy Tab Active4 Pro (2022)', 36990,
     '10.1in 2K touch, Snapdragon 778G, 6GB/128GB, Android, IP68, MIL-STD-810H, S Pen'),
    ('Samsung', 'Samsung Galaxy Tab S9 (2023)', 47990,
     '11in 2.5K AMOLED 120Hz touch, Snapdragon 8 Gen 2, 8GB/128GB, Android, S Pen, 8400mAh'),
    ('Samsung', 'Samsung Galaxy Tab S9+ (2023)', 58990,
     '12.4in 2.8K AMOLED 120Hz touch, Snapdragon 8 Gen 2, 12GB/256GB, Android, S Pen, 10090mAh'),
    ('Samsung', 'Samsung Galaxy Tab S9 Ultra (2023)', 72990,
     '14.6in 2.9K AMOLED 120Hz touch, Snapdragon 8 Gen 2, 12GB/256GB, Android, S Pen, 11200mAh'),
    ('Samsung', 'Samsung Galaxy Tab S9 FE', 27990,
     '10.9in 2.3K 90Hz touch, Exynos 1380, 6GB/128GB, Android, S Pen, 8000mAh'),
    ('Samsung', 'Samsung Galaxy Tab S9 FE+ (2023)', 36990,
     '12.4in 2.5K 90Hz touch, Exynos 1380, 8GB/128GB, Android, S Pen, 10090mAh'),
    ('Samsung', 'Samsung Galaxy Tab A9 8.7 (2023)', 10990,
     '8.7in HD+ touch, MediaTek Helio G99, 4GB/64GB, Android, 5100mAh'),
    ('Samsung', 'Samsung Galaxy Tab A9+', 16990,
     '11in 2K 90Hz touch, Snapdragon 695, 4GB/64GB, Android, 7040mAh'),
    ('Samsung', 'Samsung Galaxy Tab S6 Lite (2024)', 16990,
     '10.4in 2K touch, Snapdragon 720G, 4GB/64GB, Android, S Pen, 7040mAh'),
    ('Samsung', 'Samsung Galaxy Tab S10+', 62990,
     '12.4in 2.8K AMOLED 120Hz touch, MediaTek Dimensity 9300+, 12GB/256GB, Android, S Pen, 10090mAh'),
    ('Samsung', 'Samsung Galaxy Tab S10 Ultra', 76990,
     '14.6in 2.9K AMOLED 120Hz touch, MediaTek Dimensity 9300+, 12GB/256GB, Android, S Pen, 11200mAh'),
    ('Samsung', 'Samsung Galaxy Tab Active5 (2024)', 39990,
     '8in 2K touch, Exynos 1380, 6GB/128GB, Android, IP68, MIL-STD-810H, S Pen'),
    ('Samsung', 'Samsung Galaxy Tab S10 FE (2025)', 32990,
     '10.9in 2.3K 90Hz touch, Exynos 1580, 8GB/128GB, Android, S Pen, 8000mAh'),
    ('Samsung', 'Samsung Galaxy Tab S10 FE+', 42990,
     '12.4in 2.5K 90Hz touch, Exynos 1580, 8GB/128GB, Android, S Pen, 10090mAh'),
    ('Samsung', 'Samsung Galaxy Tab S10 Lite (2025)', 24990,
     '10.9in 2.1K 90Hz touch, Exynos 1380, 6GB/128GB, Android, S Pen, 8000mAh'),
    ('Samsung', 'Samsung Galaxy Tab S11 (2025)', 52990,
     '11in 2.5K AMOLED 120Hz touch, MediaTek Dimensity 9400+, 12GB/256GB, Android, S Pen, 8400mAh'),
    ('Samsung', 'Samsung Galaxy Tab S11+ (2025)', 64990,
     '12.4in 2.8K AMOLED 120Hz touch, MediaTek Dimensity 9400+, 12GB/256GB, Android, S Pen, 10090mAh'),
    ('Samsung', 'Samsung Galaxy Tab S11 Ultra (2025)', 82990,
     '14.6in 2.9K AMOLED 120Hz touch, MediaTek Dimensity 9400+, 12GB/256GB, Android, S Pen, 11600mAh'),
    ('Samsung', 'Samsung Galaxy Tab A11 (2025)', 12990,
     '8.7in HD+ 90Hz touch, MediaTek Helio G99, 4GB/64GB, Android, 5100mAh'),
    ('Samsung', 'Samsung Galaxy Tab A11+ (2025)', 18990,
     '11in 2K 90Hz touch, Snapdragon 695, 6GB/128GB, Android, 7040mAh'),

    ('RedMagic', 'RedMagic Nova Gaming Tablet', 34990,
     '10.9in 2.8K 144Hz touch, Snapdragon 8 Gen 3 Leading Version, 12GB/256GB, Android, 10100mAh, 66W'),
    ('RedMagic', 'RedMagic Astra Gaming Tablet', 39990,
     '9.06in 2.4K OLED 165Hz touch, Snapdragon 8 Elite, 12GB/256GB, Android, 8200mAh, 80W'),
    ('RedMagic', 'RedMagic Astra 2 Gaming Tablet (2026)', 44990,
     '9.06in 2.4K OLED 165Hz touch, Snapdragon 8 Elite Gen 5, 12GB/256GB, Android, 8200mAh, 80W'),
]


def _description(name, specs):
    return '%s with %s.' % (name, specs)


class Command(BaseCommand):
    help = 'Add curated 2020-2026 tablets for Apple, ASUS, Dell, HP, Lenovo, Samsung and RedMagic.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Report what would change without writing to the database.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        seen = set()
        for brand, name, price, specs in TABLETS:
            key = (brand.casefold(), name.casefold())
            if key in seen:
                raise CommandError('Duplicate catalog entry: %s %s' % (brand, name))
            seen.add(key)

        known_brands = {}
        for value in Product.objects.exclude(brand='').values_list('brand', flat=True).distinct():
            known_brands.setdefault(value.casefold(), value)

        created = 0
        existing = 0
        moved = 0
        category_cache = {}

        def get_category(name, description=''):
            if name not in category_cache:
                category_cache[name], _ = Category.objects.get_or_create(
                    name=name, defaults={'description': description}
                )
            return category_cache[name]

        if dry_run:
            tablet_category = Category.objects.filter(name='Tablets').first()
        else:
            tablet_category = get_category(
                'Tablets',
                'Portable touch-screen computers for work, study, creativity, and gaming.',
            )

        with transaction.atomic():
            for index, (brand, name, price, specs) in enumerate(TABLETS):
                canonical_brand = known_brands.get(brand.casefold(), brand)
                product = Product.objects.filter(
                    brand__iexact=canonical_brand, name__iexact=name
                ).first()
                if product:
                    existing += 1
                    if tablet_category and product.category_id != tablet_category.id:
                        moved += 1
                        if not dry_run:
                            product.category = tablet_category
                            product.save(update_fields=['category'])
                    continue

                if dry_run:
                    created += 1
                    continue

                Product.objects.create(
                    brand=canonical_brand,
                    name=name,
                    category=tablet_category,
                    description=_description(name, specs),
                    specifications=specs,
                    price=Decimal(str(price)),
                    stock_quantity=8 + (index % 7),
                )
                created += 1

        prefix = 'dry run: ' if dry_run else ''
        self.stdout.write(self.style.SUCCESS(
            '%s%d added, %d already present, %d moved to Tablets.'
            % (prefix, created, existing, moved)
        ))
