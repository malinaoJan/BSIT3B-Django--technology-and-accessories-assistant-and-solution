from django.core.management.base import BaseCommand
from django.db import transaction

from apps.core.models import Accessory, Category, Product


PRODUCTS = (
    (
        'Samsung',
        'Smartphones',
        'Galaxy S26',
        'Samsung Galaxy S26 smartphone.',
        '6.3-inch display, 50 MP wide camera, customized processor, 7.2 mm thickness, 167 g.',
        'https://www.samsung.com/us/smartphones/galaxy-s26/',
    ),
    (
        'Samsung',
        'Smartphones',
        'Galaxy S26+',
        'Samsung Galaxy S26+ smartphone.',
        '6.7-inch display, 50 MP wide camera, customized processor, 7.3 mm thickness, 190 g.',
        'https://www.samsung.com/us/smartphones/galaxy-s26/',
    ),
    (
        'Apple',
        'Smartphones',
        'iPhone 18 Pro',
        'Apple iPhone 18 Pro smartphone.',
        'A20 Pro chip with vapor cooling, 48 MP Fusion Main camera with variable aperture, Ceramic Shield front and back.',
        'https://www.apple.com/iphone-18-pro/',
    ),
    (
        'Apple',
        'Smartphones',
        'iPhone 17e',
        'Apple iPhone 17e smartphone.',
        '6.1-inch Super Retina XDR display, A19 chip, 48 MP Fusion camera, up to 26 hours video playback, MagSafe.',
        'https://www.apple.com/iphone-17e/',
    ),
    (
        'RedMagic',
        'Smartphones',
        'REDMAGIC 11S Pro',
        'REDMAGIC 11S Pro gaming smartphone, listed in the current official REDMAGIC store catalog.',
        '',
        'https://global.redmagic.gg/collections/redmagic-11-series',
    ),
    (
        'Google',
        'Smartphones',
        'Pixel 11 Pro Fold',
        'Google Pixel 11 Pro Fold foldable smartphone.',
        'Google Tensor G6, 16 GB RAM, 4806 mAh typical battery, 239 g, 48 MP wide + 10.5 MP ultrawide + 10.8 MP 5x telephoto rear cameras.',
        'https://support.google.com/pixelphone/answer/7158570?hl=en',
    ),
    (
        'HONOR',
        'Smartphones',
        'HONOR Magic8 Pro',
        'HONOR Magic8 Pro smartphone.',
        '200 MP telephoto camera with 3.7x optical zoom, 50 MP main camera, 50 MP ultrawide camera, 50 MP front camera.',
        'https://www.honor.com/global/phones/honor-magic8-pro/',
    ),
    (
        'Huawei',
        'Smartphones',
        'HUAWEI Pura 80 Pro',
        'HUAWEI Pura 80 Pro smartphone.',
        '1-inch Ultra Lighting Camera sensor, Ultra Lighting Macro Telephoto Camera with 5 cm focus distance, 2nd-generation Kunlun Glass.',
        'https://consumer.huawei.com/en/phones/pura80-pro/',
    ),
    (
        'Infinix',
        'Smartphones',
        'NOTE 60 Pro',
        'Infinix NOTE 60 Pro smartphone.',
        'Snapdragon 7s Gen 4 5G, 144 Hz 1.5K display, 90 W charging, 6500 mAh battery.',
        'https://ph.infinixmobility.com/note-60-pro',
    ),
    (
        'OnePlus',
        'Smartphones',
        'OnePlus 15',
        'OnePlus 15 smartphone.',
        'OxygenOS 16, Wi-Fi 7, Bluetooth 6.0, dual eSIM, 4K 120 fps Dolby Vision video recording.',
        'https://www.oneplus.com/us/15',
    ),
    (
        'OPPO',
        'Smartphones',
        'Find X9 Pro',
        'OPPO Find X9 Pro smartphone.',
        '200 MP Hasselblad telephoto camera, 1.15 mm ultra-thin display bezels.',
        'https://www.oppo.com/en/smartphones/series-find-x/find-x9-pro/',
    ),
    (
        'realme',
        'Smartphones',
        'realme GT 8 Pro',
        'realme GT 8 Pro smartphone.',
        'Snapdragon 8 Elite Gen 5, 200 MP telephoto camera, 2K 7000-nit display, 7000 mAh battery, 120 W wired and 50 W wireless charging.',
        'https://www.realme.com/global/realme-gt-8-pro',
    ),
    (
        'realme',
        'Smartphones',
        'realme C85 Pro',
        'realme C85 Pro smartphone.',
        '7000 mAh battery, 45 W fast charging, 120 Hz AMOLED display, IP69 Pro water resistance.',
        'https://www.realme.com/global/realme-c85-pro',
    ),
    (
        'vivo',
        'Smartphones',
        'vivo X300 Pro',
        'vivo X300 Pro smartphone.',
        '6.78-inch display, 200 MP ZEISS APO telephoto camera, 50 MP front camera, 4K 120 fps Dolby Vision video.',
        'https://www.vivo.com/en/products/x300-pro',
    ),
    (
        'Xiaomi',
        'Smartphones',
        'Xiaomi 17 Ultra',
        'Xiaomi 17 Ultra smartphone.',
        'Snapdragon 8 Elite Gen 5, Leica 1-inch ultra-dynamic camera, 200 MP telephoto with 75–100 mm mechanical optical zoom, 6000 mAh typical battery.',
        'https://www.mi.com/global/product/xiaomi-17-ultra/',
    ),
    (
        'ASUS',
        'Smartphones',
        'ROG Phone 9',
        'ASUS ROG Phone 9 gaming smartphone.',
        'Snapdragon 8 Elite, GameCool 9 cooling, AI-powered X Sense features, AniMe Vision.',
        'https://www.asus.com/mobile-handhelds/phones/rog-phone/',
    ),
    (
        'Razer',
        'Laptops',
        'Razer Blade 16',
        'Razer Blade 16 gaming laptop.',
        'Intel Core Ultra 9 processor, up to 165 W GPU TGP, LPDDR5X-9600 memory, OLED QHD display up to 240 Hz, Thunderbolt 5.',
        'https://www.razer.com/gaming-laptops/razer-blade-16',
    ),
    (
        'Epson',
        'Printers',
        'EcoTank ET-4950',
        'Epson EcoTank ET-4950 wireless all-in-one color supertank printer.',
        'PrecisionCore Heat-Free technology, Ethernet and Wi-Fi, print and scan support, refillable EcoFit ink tanks.',
        'https://epson.com/For-Home/Printers/Inkjet/EcoTank-ET-4950-Wireless-All-in-One-Color-Supertank-Printer-%E2%80%93-Black/p/C11CL40201',
    ),
    (
        'LG',
        'Monitors',
        'LG UltraGear 27G850A-B',
        'LG UltraGear 27G850A-B gaming monitor.',
        '',
        'https://www.lg.com/us/monitors/lg-27g850a-b-gaming-monitor',
    ),
    (
        'TP-Link',
        'Networking',
        'Archer BE800',
        'TP-Link Archer BE800 BE19000 tri-band Wi-Fi 7 router.',
        'Tri-band Wi-Fi 7 up to 19 Gbps, two 10 Gbps WAN/LAN ports, four 2.5 Gbps LAN ports, USB 3.0.',
        'https://www.tp-link.com/us/home-networking/wifi-router/archer-be800/',
    ),
    (
        'Lenovo',
        'Tablets',
        'Legion Tab Gen 5',
        'Lenovo Legion Tab Gen 5 gaming tablet.',
        'Official Lenovo Legion listing identifies this as a gaming tablet and links to its product page.',
        'https://www.lenovo.com/us/en/p/LEN103G0003',
    ),
    (
        'Logitech',
        'Peripherals',
        'MX Master 4',
        'Logitech MX Master 4 high-performance wireless mouse with haptic feedback.',
        '8K DPI tracking, MagSpeed scroll wheel, customizable haptic feedback, Actions Ring shortcuts.',
        'https://www.logitech.com/en-us/shop/p/mx-master-4.910-007558',
    ),
)

ACCESSORIES = (
    (
        'Anker',
        'Chargers & Cables',
        'Anker Nano Charger (45W, Smart Display, 180° Foldable)',
        'USB-C wall charger with smart display, foldable rotating prongs, and up to 45 W Power Delivery output.',
        'USB-C devices that support USB Power Delivery; charging speed depends on the connected device.',
        'https://www.anker.com/products/a121d-45w-usb-c-fast-charger-foldable-plug-compact',
    ),
    (
        'Anker',
        'Power Banks',
        'Anker Prime Power Bank (26K, 300W)',
        'Portable power bank with 26,250 mAh capacity, up to 300 W total output, and up to 250 W dual-port input.',
        'Official Anker compatibility list includes laptops, phones, tablets, and other USB charging devices.',
        'https://www.anker.com/products/a110a-anker-prime-26k-300w-power-bank',
    ),
    (
        'Baseus',
        'Power Banks',
        'Baseus PicoGo AM41 Ultra-Slim Qi2 Magnetic Power Bank 10000mAh 27W',
        'Official Baseus listing describes a 10,000 mAh Qi2 magnetic power bank with up to 27 W output.',
        'Qi2-compatible magnetic devices; verify device support and alignment before use.',
        'https://www.baseus.com/products/picogo-ultra-slim-qi2-magnetic-power-bank-10000mah',
    ),
    (
        'Baseus',
        'Power Banks',
        'Baseus PicoGo Ultra-Slim Magnetic Power Bank 5000mAh 20W',
        'Official Baseus listing describes a 5,000 mAh ultra-slim magnetic power bank with up to 20 W output.',
        'Magnetic wireless charging and USB-C devices; verify device support before use.',
        'https://www.baseus.com/products/picogo-ultra-slim-magnetic-power-bank-5000mah',
    ),
    (
        'Baseus',
        'Power Banks',
        'Baseus EnerFill FM12 Qi2 Magnetic Power Bank 10000mAh 22.5W',
        'Official Baseus listing describes a 10,000 mAh Qi2 magnetic power bank with up to 22.5 W output.',
        'Qi2-compatible magnetic devices; verify device support and alignment before use.',
        'https://www.baseus.com/products/enerfill-fm12-qi2-magnetic-power-bank-22-5w-10000mah',
    ),
    (
        'Baseus',
        'Power Banks',
        'Baseus EnerCore CR11 Power Bank with Retractable Cable 10000mAh 45W',
        'Official Baseus listing describes a 10,000 mAh power bank with retractable cable and up to 45 W output.',
        'USB-C devices compatible with the built-in cable and supported charging protocols.',
        'https://www.baseus.com/products/enercore-cr11-power-bank-with-retractable-cable-10000mah-45w',
    ),
    (
        'UGREEN',
        'Peripherals',
        'UGREEN Revodok 206 USB-C Hub',
        'USB-C hub; official UGREEN information lists dual 4K at 60 Hz on compatible Windows systems or up to 8K at 30 Hz on one display.',
        'Host must support USB-C data; video features require compatible video output support.',
        'https://us.ugreen.com/products/ugreen-revodok-pro-6-in-1-usb-c-hub',
    ),
)


class Command(BaseCommand):
    help = 'Import products and accessories verified on current official catalog pages.'

    def handle(self, *args, **options):
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
            for brand_name, category_name, name, description, specs, source_url in PRODUCTS:
                brand = known_brands.get(brand_name.casefold(), brand_name)
                _, created = Product.objects.update_or_create(
                    brand=brand,
                    name=name,
                    defaults={
                        'category': get_category(category_name),
                        'description': description,
                        'specifications': specs,
                        'source_url': source_url,
                        'price': None,
                        'stock_quantity': None,
                    },
                )
                if created:
                    created_products += 1
                else:
                    existing_products += 1

            for (
                brand_name,
                category_name,
                name,
                description,
                compatibility,
                source_url,
            ) in ACCESSORIES:
                brand = known_brands.get(brand_name.casefold(), brand_name)
                _, created = Accessory.objects.update_or_create(
                    brand=brand,
                    name=name,
                    defaults={
                        'category': get_category(category_name),
                        'description': description,
                        'compatibility_notes': compatibility,
                        'source_url': source_url,
                        'price': None,
                        'stock_quantity': None,
                    },
                )
                if created:
                    created_accessories += 1
                else:
                    existing_accessories += 1

        self.stdout.write(self.style.SUCCESS(
            'Products: %s added, %s refreshed; accessories: %s added, '
            '%s refreshed. Unknown prices and stock were left blank.'
            % (
                created_products,
                existing_products,
                created_accessories,
                existing_accessories,
            )
        ))
