from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.core.models import Accessory, Category, Product
from old_accessories_data import OLD_ACCESSORIES
from old_products_data import OLD_PRODUCTS

BRAND_KEYS = (
    'samsung',
    'Acer',
    'Anker',
    'apple',
    'ASUS',
    'Baseus',
    'Canon',
    'Dell',
    'Epson',
    'Gigabyte',
    'Google',
)

BRAND_NAMES = {
    'samsung': 'Samsung',
    'Acer': 'Acer',
    'Anker': 'Anker',
    'apple': 'Apple',
    'ASUS': 'ASUS',
    'Baseus': 'Baseus',
    'Canon': 'Canon',
    'Dell': 'Dell',
    'Epson': 'Epson',
    'Gigabyte': 'Gigabyte',
    'Google': 'Google',
}


class Command(BaseCommand):
    help = 'Add the curated products and accessories for the requested brands.'

    def handle(self, *args, **options):
        missing = [
            brand for brand in BRAND_KEYS
            if brand not in OLD_PRODUCTS or brand not in OLD_ACCESSORIES
        ]
        if missing:
            raise CommandError(
                'Catalog data is missing for: %s' % ', '.join(missing)
            )

        known_brands = {}
        for value in (
            list(Product.objects.exclude(brand='').values_list('brand', flat=True))
            + list(Accessory.objects.exclude(brand='').values_list('brand', flat=True))
        ):
            known_brands.setdefault(value.casefold(), value)

        created_products = 0
        existing_products = 0
        created_accessories = 0
        existing_accessories = 0
        category_cache = {}

        def get_category(name):
            if name not in category_cache:
                category_cache[name], _ = Category.objects.get_or_create(name=name)
            return category_cache[name]

        with transaction.atomic():
            for key in BRAND_KEYS:
                brand = known_brands.get(
                    BRAND_NAMES[key].casefold(), BRAND_NAMES[key]
                )
                products = []
                for (
                    category_name,
                    name,
                    description,
                    specs,
                    price,
                    stock,
                ) in OLD_PRODUCTS[key]:
                    product, created = Product.objects.get_or_create(
                        brand=brand,
                        name=name,
                        defaults={
                            'category': get_category(category_name),
                            'description': description,
                            'specifications': specs,
                            'price': Decimal(str(price)),
                            'stock_quantity': stock,
                        },
                    )
                    products.append(product)
                    if created:
                        created_products += 1
                    else:
                        existing_products += 1

                for (
                    category_name,
                    name,
                    description,
                    compatibility,
                    price,
                    stock,
                    product_indexes,
                ) in OLD_ACCESSORIES[key]:
                    accessory, created = Accessory.objects.get_or_create(
                        brand=brand,
                        name=name,
                        defaults={
                            'category': get_category(category_name),
                            'description': description,
                            'compatibility_notes': compatibility,
                            'price': Decimal(str(price)),
                            'stock_quantity': stock,
                        },
                    )
                    if created:
                        created_accessories += 1
                    else:
                        existing_accessories += 1

                    accessory.compatible_products.add(
                        *(
                            products[index]
                            for index in product_indexes
                            if 0 <= index < len(products)
                        )
                    )

        self.stdout.write(self.style.SUCCESS(
            'Products: %s added, %s already present; accessories: %s added, '
            '%s already present.'
            % (
                created_products,
                existing_products,
                created_accessories,
                existing_accessories,
            )
        ))
