"""Seed laptop products for every major laptop brand missing from the catalog.
Run: venv\\Scripts\\python.exe manage.py shell < projectv3\\seed_laptops.py
Safe to re-run (uses get_or_create on brand+name).
"""
from decimal import Decimal
from apps.core.models import Category, Product

lap, _ = Category.objects.get_or_create(
    name="Laptops",
    defaults={"description": "Portable notebook computers for work, school, and gaming."},
)

LAPTOPS = [
    # Apple
    dict(brand="Apple", name="Apple MacBook Air 13 M3 (2024)",
         description="Thin-and-light 13in ultrabook with Apple Silicon.",
         specifications="13.6in Liquid Retina, Apple M3 8-core, 8GB/256GB, 18hr battery, 1.24kg, Touch ID",
         price=Decimal("71990.00"), stock_quantity=10),
    dict(brand="Apple", name="Apple MacBook Pro 14 M3 Pro",
         description="Pro 14in workstation laptop for creators and developers.",
         specifications="14.2in Liquid Retina XDR 120Hz, Apple M3 Pro, 18GB/512GB, 22hr battery, 1.55kg, HDMI+SDXC",
         price=Decimal("129990.00"), stock_quantity=6),
    # MSI
    dict(brand="MSI", name="MSI GF63 Thin 12VE",
         description="Budget 15.6in gaming laptop.",
         specifications="15.6in FHD 144Hz, Intel i5-12450H, RTX 4050 6GB, 8GB/512GB, 51Wh, 1.86kg",
         price=Decimal("46995.00"), stock_quantity=8),
    dict(brand="MSI", name="MSI Cyborg 15 A13V",
         description="Translucent-design 15.6in gaming laptop.",
         specifications="15.6in FHD 144Hz, Intel i7-13620H, RTX 4060 8GB, 16GB/512GB, 53.5Wh 200W, 1.98kg",
         price=Decimal("69995.00"), stock_quantity=5),
    dict(brand="MSI", name="MSI Modern 14 C13M",
         description="Slim 14in productivity ultrabook.",
         specifications="14in FHD IPS, Intel i5-1335U, Intel Iris Xe, 16GB/512GB, 39.3Wh, 1.4kg, backlit KB",
         price=Decimal("42995.00"), stock_quantity=9),
    # Microsoft
    dict(brand="Microsoft", name="Microsoft Surface Laptop 7 13.8 Copilot+",
         description="ARM 13.8in Copilot+ PC with all-day battery.",
         specifications="13.8in PixelSense Flow 120Hz, Snapdragon X Elite, 16GB/512GB, 20hr battery, 1.34kg",
         price=Decimal("79999.00"), stock_quantity=6),
    dict(brand="Microsoft", name="Microsoft Surface Pro 11 Copilot+",
         description="2-in-1 detachable with OLED option and pen support.",
         specifications="13in PixelSense Flow OLED 120Hz touch, Snapdragon X Plus, 16GB/256GB, 14hr battery, 0.89kg",
         price=Decimal("69999.00"), stock_quantity=7),
    # Huawei
    dict(brand="Huawei", name="Huawei MateBook D 15 (2024)",
         description="Value 15.6in office and school laptop.",
         specifications="15.6in FHD IPS, Intel i5-12450H, 16GB/512GB, 56Wh 65W, 1.68kg, fingerprint power button",
         price=Decimal("37990.00"), stock_quantity=10),
    dict(brand="Huawei", name="Huawei MateBook X Pro (2024)",
         description="Flagship 14.2in lightweight OLED ultrabook.",
         specifications="14.2in 3.1K OLED 120Hz, Intel Core Ultra 7 155H, 16GB/1TB, 70Wh, 0.98kg",
         price=Decimal("89990.00"), stock_quantity=5),
    # LG
    dict(brand="LG", name="LG Gram 16 (2024)",
         description="Featherweight 16in ultrabook with huge battery.",
         specifications="16in WQXGA IPS, Intel Core Ultra 7 155H, 16GB/512GB, 77Wh, 1.19kg, MIL-STD-810H",
         price=Decimal("94990.00"), stock_quantity=5),
    dict(brand="LG", name="LG Gram 14 (2024)",
         description="Ultralight 14in travel laptop.",
         specifications="14in WUXGA IPS, Intel Core Ultra 5 125H, 16GB/512GB, 72Wh, 0.99kg, MIL-STD-810H",
         price=Decimal("79990.00"), stock_quantity=6),
    # Razer
    dict(brand="Razer", name="Razer Blade 14 (2024)",
         description="Premium 14in thin gaming laptop, all-CNC aluminum.",
         specifications="14in QHD+ 240Hz, Ryzen 9 8940HS, RTX 4070 8GB, 16GB/1TB, 68Wh, 1.84kg, per-key RGB",
         price=Decimal("149990.00"), stock_quantity=4),
    dict(brand="Razer", name="Razer Blade 16 (2024)",
         description="Flagship 16in OLED gaming and creator laptop.",
         specifications="16in QHD+ OLED 240Hz, Intel i9-14900HX, RTX 4080 12GB, 32GB/1TB, 95Wh, 2.45kg, vapor chamber",
         price=Decimal("229990.00"), stock_quantity=3),
    # Gigabyte
    dict(brand="Gigabyte", name="Gigabyte G5 KF5",
         description="Value 15.6in RTX gaming laptop.",
         specifications="15.6in FHD 144Hz, Intel i5-12500H, RTX 4060 8GB, 16GB/512GB, 54Wh 150W, 1.9kg",
         price=Decimal("59995.00"), stock_quantity=7),
    dict(brand="Gigabyte", name="Gigabyte Aero 16 OLED",
         description="16in 4K OLED creator laptop, X-Rite calibrated.",
         specifications="16in 4K AMOLED, Intel i9-13900H, RTX 4070 8GB, 16GB/1TB, 88Wh, 2.0kg, X-Rite Pantone",
         price=Decimal("129995.00"), stock_quantity=4),
    # Xiaomi
    dict(brand="Xiaomi", name="Xiaomi RedmiBook 15 (2024)",
         description="Budget 15.6in everyday laptop.",
         specifications="15.6in FHD, Intel i5-12450H, 16GB/512GB, 46Wh 65W, 1.78kg, Xiaomi HyperOS Connect",
         price=Decimal("32990.00"), stock_quantity=12),
    dict(brand="Xiaomi", name="Xiaomi Book 14 (2024)",
         description="Slim 14in 2.8K 120Hz productivity laptop.",
         specifications="14in 2.8K 120Hz, Intel Core Ultra 5 125H, 16GB/512GB, 56Wh, 1.37kg",
         price=Decimal("45990.00"), stock_quantity=9),
    # Google
    dict(brand="Google", name="Google Pixelbook Go",
         description="Lightweight ChromeOS laptop with silent fanless design.",
         specifications="13.3in FHD touch, Intel m3/i5, 8GB/128GB, 12hr battery, 1.06kg, Titan C chip",
         price=Decimal("38990.00"), stock_quantity=6),
]

created, skipped = 0, 0
for item in LAPTOPS:
    _, was_created = Product.objects.get_or_create(
        brand=item["brand"], name=item["name"],
        defaults={**item, "category": lap},
    )
    if was_created:
        created += 1
    else:
        skipped += 1

print(f"done: {created} created, {skipped} already existed")
print("laptop brands now:",
      sorted(set(Product.objects.filter(category=lap).values_list("brand", flat=True))))
print("laptop count:", Product.objects.filter(category=lap).count())
