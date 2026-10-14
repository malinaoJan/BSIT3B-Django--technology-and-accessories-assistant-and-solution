from decimal import Decimal

from django.core.management.base import BaseCommand

from catalog.models import (
    Category,
    Compatibility,
    Device,
    Product,
    TroubleshootingGuide,
)


CATEGORIES = {
    "Laptops": "Portable computers for work, school, and gaming.",
    "Smartphones": "Mobile phones and everyday communication devices.",
    "Audio": "Headphones, speakers, and sound accessories.",
    "Chargers & Cables": "Power adapters, cables, and charging accessories.",
    "Peripherals": "Keyboards, mice, and input devices.",
    "Storage": "External drives, SSDs, and memory cards.",
    "Networking": "Routers, adapters, and connectivity devices.",
}

DEVICES = [
    ("Apple", "MacBook Pro 14", "laptop", "USB-C"),
    ("Apple", "iPhone 15", "phone", "USB-C"),
    ("Samsung", "Galaxy S24", "phone", "USB-C"),
    ("Dell", "XPS 13", "laptop", "USB-C"),
    ("Lenovo", "ThinkPad X1", "laptop", "USB-C"),
    ("Sony", "WH-1000XM5", "other", "Bluetooth"),
]

PRODUCTS = [
    # name, brand, category, price, stock, description, specs
    ("ProBook Ultra 14", "Acer", "Laptops", "52990.00", 8,
     "A lightweight 14-inch laptop built for productivity and long battery life.",
     {"Processor": "Intel Core i7", "RAM": "16GB", "Storage": "512GB SSD", "Display": "14\" 2.8K"}),
    ("VivoBook Air 15", "Asus", "Laptops", "38990.00", 12,
     "Everyday laptop with a vivid display and slim aluminum body.",
     {"Processor": "AMD Ryzen 5", "RAM": "8GB", "Storage": "512GB SSD", "Display": "15.6\" FHD"}),
    ("PixelView 6", "Google", "Smartphones", "41990.00", 20,
     "Flagship smartphone with an advanced camera system and clean Android experience.",
     {"Display": "6.4\" OLED", "Camera": "50MP", "Battery": "4600mAh", "Storage": "128GB"}),
    ("Galaxy Nova 8", "Samsung", "Smartphones", "34990.00", 15,
     "Feature-packed phone with a brilliant AMOLED screen.",
     {"Display": "6.6\" AMOLED", "Camera": "64MP", "Battery": "5000mAh", "Storage": "256GB"}),
    ("StudioPods Max", "SoundCore", "Audio", "8990.00", 30,
     "Over-ear noise cancelling headphones with rich, balanced audio.",
     {"Type": "Over-ear", "ANC": "Active Noise Cancelling", "Battery": "40 hours", "Bluetooth": "5.3"}),
    ("BassBuds Pro", "JBL", "Audio", "4490.00", 45,
     "True wireless earbuds with deep bass and clear calls.",
     {"Type": "In-ear TWS", "ANC": "Hybrid", "Battery": "28 hours", "Water": "IPX5"}),
    ("GaN 65W Charger", "Anker", "Chargers & Cables", "1990.00", 60,
     "Compact 3-port GaN fast charger for laptops and phones.",
     {"Power": "65W", "Ports": "2x USB-C, 1x USB-A", "Technology": "GaN II"}),
    ("USB-C Braided Cable 2m", "Baseus", "Chargers & Cables", "499.00", 120,
     "Durable braided USB-C cable supporting 100W charging and data transfer.",
     {"Length": "2 meters", "Power": "100W PD", "Data": "480Mbps"}),
    ("MechType K87 Keyboard", "Keychron", "Peripherals", "4290.00", 25,
     "Mechanical keyboard with hot-swappable switches and RGB backlight.",
     {"Layout": "87 keys TKL", "Switch": "Hot-swap Red", "Connection": "Bluetooth + USB-C"}),
    ("Precision Mouse X", "Logitech", "Peripherals", "2490.00", 40,
     "Ergonomic wireless mouse with high-precision tracking.",
     {"DPI": "8000", "Connection": "2.4GHz + Bluetooth", "Battery": "18 months"}),
    ("Portable SSD 1TB", "SanDisk", "Storage", "6490.00", 18,
     "Pocket-sized SSD with fast transfer speeds for work on the go.",
     {"Capacity": "1TB", "Speed": "1050MB/s", "Interface": "USB 3.2"}),
    ("WiFi 6 Mesh Router", "TP-Link", "Networking", "5990.00", 10,
     "Whole-home mesh router with WiFi 6 coverage and easy setup.",
     {"Standard": "WiFi 6", "Bands": "Dual-band", "Coverage": "Up to 230 sqm"}),
]

GUIDES = [
    ("Laptop won't turn on", "Laptop", "Laptop does not power on",
     "No lights, no fan, black screen even when plugged in.",
     "Confirm the charger is connected and the outlet works.\nPress and hold the power button for 15 seconds, then release.\nDisconnect the battery if removable and hold power for 30 seconds.\nReconnect the charger and try powering on again.\nIf it still fails, test with a known-good charger.",
     "Newer laptops have sealed batteries. Avoid opening the case if under warranty."),
    ("Phone battery drains fast", "Phone", "Smartphone battery drains quickly",
     "Battery percentage drops rapidly during normal use.",
     "Check Battery usage in Settings to find power-hungry apps.\nLower screen brightness and enable adaptive brightness.\nTurn off background app refresh for rarely used apps.\nDisable Bluetooth, GPS, and hotspot when not needed.\nCalibrate the battery by charging to 100% then draining to 5% once.",
     "If the battery health is below 80%, replace it at an authorized service center."),
    ("WiFi keeps disconnecting", "Networking", "Frequent WiFi drops",
     "Internet disconnects repeatedly on multiple devices.",
     "Restart the router and modem, then wait two minutes.\nMove the router away from walls and metal objects.\nUpdate the router firmware.\nChange the WiFi channel to reduce interference.\nIf needed, reset the router and reconfigure it.",
     "Contact your ISP if disconnections continue after a full reset."),
    ("Headphones have no sound", "Audio", "No audio from headphones",
     "Headphones connect but produce no sound.",
     "Increase the volume on both the device and headphones.\nDisconnect and reconnect the headphones or Bluetooth.\nSelect the correct audio output device in settings.\nTest the headphones with another device.\nCharge the headphones if the battery is low.",
     "Bluetooth headphones sometimes pair as a call-only device; re-pair if needed."),
]


class Command(BaseCommand):
    help = "Seed the database with demo technology products, devices, and guides."

    def handle(self, *args, **options):
        cats = {}
        for name, desc in CATEGORIES.items():
            cat, _ = Category.objects.get_or_create(name=name, defaults={"description": desc})
            cats[name] = cat

        devices = {}
        for brand, model, dtype, connector in DEVICES:
            dev, _ = Device.objects.get_or_create(
                brand=brand, model_name=model,
                defaults={"device_type": dtype, "connector_type": connector},
            )
            devices[f"{brand} {model}"] = dev

        products = {}
        for name, brand, cat, price, stock, desc, specs in PRODUCTS:
            prod, _ = Product.objects.get_or_create(
                name=name, brand=brand,
                defaults={
                    "category": cats[cat],
                    "price": Decimal(price),
                    "stock_quantity": stock,
                    "description": desc,
                    "specifications": specs,
                },
            )
            products[name] = prod

        # Compatibility
        compat_map = {
            "ProBook Ultra 14": ["Samsung Galaxy S24", "Apple iPhone 15"],
            "GaN 65W Charger": ["Apple MacBook Pro 14", "Dell XPS 13", "Samsung Galaxy S24", "Apple iPhone 15"],
            "USB-C Braided Cable 2m": ["Samsung Galaxy S24", "Apple iPhone 15", "Apple MacBook Pro 14"],
            "StudioPods Max": ["Apple iPhone 15", "Samsung Galaxy S24", "Lenovo ThinkPad X1"],
            "Portable SSD 1TB": ["Apple MacBook Pro 14", "Dell XPS 13", "Lenovo ThinkPad X1"],
        }
        for prod_name, dev_names in compat_map.items():
            for dev_name in dev_names:
                Compatibility.objects.get_or_create(
                    product=products[prod_name],
                    device=devices[dev_name],
                    defaults={"verified": True, "compatibility_notes": "Tested and confirmed working."},
                )

        for title, dtype, issue, symptoms, steps, safety in GUIDES:
            TroubleshootingGuide.objects.get_or_create(
                title=title,
                defaults={
                    "device_type": dtype,
                    "issue": issue,
                    "symptoms": symptoms,
                    "steps": steps,
                    "safety_note": safety,
                    "is_published": True,
                },
            )

        self.stdout.write(self.style.SUCCESS(
            f"Seeded {Category.objects.count()} categories, "
            f"{Product.objects.count()} products, "
            f"{Device.objects.count()} devices, "
            f"{Compatibility.objects.count()} compatibilities, "
            f"{TroubleshootingGuide.objects.count()} guides."
        ))
