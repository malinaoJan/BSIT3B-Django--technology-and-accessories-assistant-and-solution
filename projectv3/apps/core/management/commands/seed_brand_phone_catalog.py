"""Seed the current smartphone lineups for the requested brands.

Covers Infinix, TECNO, ASUS, OPPO, realme, vivo, HONOR and itel, plus the
complete current Samsung Galaxy A, S and Z families. Existing products are
left untouched, so the command is safe to re-run.

Run:
    venv\\Scripts\\python.exe manage.py seed_brand_phone_catalog
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.core.models import Category, Product


BRANDS = {
    'Infinix': 'https://www.infinixmobility.com/smartphone/',
    'TECNO': 'https://www.tecno-mobile.com/phones/product-list/',
    'ASUS': 'https://www.asus.com/mobile-handhelds/phones/all-series/',
    'OPPO': 'https://www.oppo.com/en/smartphones/',
    'realme': 'https://www.realme.com/global/',
    'vivo': 'https://www.vivo.com/en/products',
    'HONOR': 'https://www.honor.com/global/phones/',
    'itel': 'https://www.itel-life.com/',
    'Samsung': 'https://www.samsung.com/us/smartphones/',
}

PHONES = {
    'Infinix': [
        ('Infinix GT 50 Pro', '6.78in AMOLED 144Hz, flagship gaming chipset, 6500mAh battery'),
        ('Infinix GT 30', '6.78in AMOLED 120Hz, gaming triggers, customizable LED lighting'),
        ('Infinix HOT 70', '6.78in 90Hz display, 50MP camera, 6000mAh battery'),
        ('Infinix HOT 70 Pro', '6.78in AMOLED 120Hz, 50MP camera, 45W fast charging'),
        ('Infinix HOT 70 Pro 5G+', '5G, 6.78in AMOLED 120Hz, 50MP camera, large battery'),
        ('Infinix HOT 60i', '6.6in 90Hz display, 50MP camera, 5000mAh battery'),
        ('Infinix HOT 60i 5G', '5G, 6.6in 120Hz display, 50MP camera, 5000mAh battery'),
        ('Infinix HOT 60 5G+', '5G, 6.78in AMOLED 120Hz, 50MP camera, 5000mAh battery'),
        ('Infinix NOTE 60', '6.78in 1.5K AMOLED 120Hz, 50MP camera, 6500mAh battery'),
        ('Infinix NOTE 60 Ultra', '6.78in 1.5K AMOLED, 200MP camera, 7000mAh battery'),
        ('Infinix Note Edge', '6.78in 1.5K curved AMOLED, 50MP camera, 6500mAh battery'),
        ('Infinix NOTE 50', '6.78in AMOLED 120Hz, 50MP camera, 5200mAh battery'),
        ('Infinix NOTE 50 Pro+ 5G', '5G, 6.78in AMOLED 120Hz, 50MP camera, 100W charging'),
        ('Infinix NOTE 50s', '6.78in AMOLED 120Hz, 50MP camera, large battery'),
        ('Infinix NOTE 50x', '5G, 6.78in 120Hz display, 50MP camera, large battery'),
        ('Infinix SMART 20', '6.78in 90Hz display, 8MP camera, 5200mAh battery'),
        ('Infinix SMART 20 HD', '6.67in 90Hz display, 8MP camera, 5000mAh battery'),
        ('Infinix SMART 10', '6.6in 90Hz display, 50MP camera, 5000mAh battery'),
        ('Infinix SMART 10 HD', '6.6in HD+ display, 8MP camera, 5000mAh battery'),
        ('Infinix SMART 10 Plus', '6.6in 90Hz display, 50MP camera, 5000mAh battery'),
        ('Infinix ZERO Flip', 'Flip foldable, 6.9in inner AMOLED, 50MP camera'),
        ('Infinix ZERO 40', '6.78in AMOLED 120Hz, 108MP camera, 5000mAh battery'),
    ],
    'TECNO': [
        ('TECNO CAMON 50', '6.78in AMOLED, 50MP camera, 6500mAh battery'),
        ('TECNO CAMON 50 Pro', '6.78in AMOLED, 50MP camera, 6500mAh battery'),
        ('TECNO CAMON 50 Ultra 5G', '5G, 200MP camera, 6.78in AMOLED, large battery'),
        ('TECNO CAMON Slim', 'Slim AMOLED design, 50MP camera, 5600mAh battery'),
        ('TECNO CAMON Slim 5G', '5G, slim AMOLED design, 50MP camera, 6000mAh battery'),
        ('TECNO CAMON 40 Premier', '6.78in AMOLED, 50MP camera, 5100mAh battery'),
        ('TECNO SPARK 50', '6.78in 120Hz display, 50MP camera, 7000mAh battery'),
        ('TECNO SPARK 50 5G', '5G, 6.78in 120Hz display, 50MP camera, 6500mAh battery'),
        ('TECNO SPARK 50 Pro', '6.78in 120Hz display, 50MP camera, 6000mAh battery'),
        ('TECNO SPARK 50C', '6.6in 90Hz display, 13MP camera, 5200mAh battery'),
        ('TECNO SPARK 40', '6.6in 120Hz display, 50MP camera, 5200mAh battery'),
        ('TECNO SPARK 40 Pro', '6.6in 120Hz AMOLED, 50MP camera, 5200mAh battery'),
        ('TECNO SPARK 40 Pro+', '6.6in 120Hz AMOLED, 50MP camera, 5200mAh battery'),
        ('TECNO SPARK 40C', '6.6in 90Hz display, 13MP camera, 6000mAh battery'),
        ('TECNO SPARK Go 2', '6.6in 90Hz display, 13MP camera, 5000mAh battery'),
        ('TECNO SPARK Go 3', '6.6in 90Hz display, 13MP camera, 5000mAh battery'),
        ('TECNO SPARK Go 5G', '5G, 6.6in 120Hz display, 50MP camera, 5000mAh battery'),
        ('TECNO SPARK Slim', 'Ultra-slim design, 6.78in AMOLED, 50MP camera, 5160mAh battery'),
        ('TECNO POVA 8 5G', '5G, 6.78in 120Hz display, 50MP camera, 8000mAh battery'),
        ('TECNO POVA 8 Pro 5G', '5G, 6.78in AMOLED 120Hz, 50MP camera, 6500mAh battery'),
        ('TECNO POVA Curve 2 5G', '5G, curved AMOLED, 50MP camera, 8000mAh battery'),
        ('TECNO POVA 7', '6.78in 120Hz display, 108MP camera, 7000mAh battery'),
        ('TECNO POVA 7 5G', '5G, 6.78in 120Hz display, 50MP camera, 6000mAh battery'),
        ('TECNO POVA 7 Pro', '6.78in 120Hz display, 64MP camera, 6000mAh battery'),
        ('TECNO POVA 7 Ultra', '6.78in 120Hz display, 108MP camera, 6000mAh battery'),
        ('TECNO POVA Slim 5G', '5G, slim design, 50MP camera, 5160mAh battery'),
        ('TECNO POVA Curve 5G', '5G, curved AMOLED, 64MP camera, 5500mAh battery'),
        ('TECNO PHANTOM V Fold2 5G', 'Book-style foldable, 7.85in inner AMOLED, 50MP camera'),
        ('TECNO PHANTOM V Flip2 5G', 'Flip foldable, 6.9in inner AMOLED, 50MP camera'),
        ('TECNO POP 20', '6.6in 90Hz display, 13MP camera, 5000mAh battery'),
        ('TECNO POP 10 Pro', '6.6in 90Hz display, 13MP camera, 5000mAh battery'),
    ],
    'ASUS': [
        ('ROG Phone 9 Pro Edition', 'Snapdragon 8 Elite, 24GB/1TB, 6.78in AMOLED 185Hz, 5800mAh'),
        ('ROG Phone 8 Pro Edition', 'Snapdragon 8 Gen 3, 24GB/1TB, 6.78in AMOLED 165Hz, 5500mAh'),
    ],
    'OPPO': [
        ('Find X10 Pro Max', 'Triple 200MP Hasselblad camera system, flagship Snapdragon'),
        ('Find X10', 'Dual 200MP camera system, 8000mAh battery'),
        ('Find X10 E', 'Flagship camera system, large high-refresh AMOLED display'),
        ('Find X9 Ultra', 'Dual 200MP Hasselblad cameras, 50MP 10x optical telephoto, 8K video'),
        ('Find X9', '6.59in AMOLED 120Hz, Dimensity 9500, 7025mAh battery'),
        ('Find X9s', '50MP triple camera, Dimensity 9500s, 7025mAh battery'),
        ('Find X9s Pro', 'Flagship triple camera, Dimensity 9500s, large battery'),
        ('Find N6', 'Book-style foldable, 6000mAh battery, Snapdragon 8 Elite Gen 5'),
        ('Find N5', 'Ultra-slim book foldable, 8.93mm body, 5600mAh battery'),
        ('OPPO Reno16 Pro 5G', '6.78in AMOLED 120Hz, 50MP camera, ColorOS 16'),
        ('OPPO Reno16 5G', '6.59in AMOLED 120Hz, 50MP 3.5x telephoto, ColorOS 16'),
        ('OPPO Reno16 F 5G', '6.7in AMOLED 120Hz, 50MP camera, ColorOS 16'),
        ('OPPO Reno16 FS 5G', '6.7in AMOLED 120Hz, 50MP camera, ColorOS 16'),
        ('OPPO Reno16c 5G', '6.7in AMOLED 120Hz, 50MP 3.5x telephoto, ColorOS 16'),
        ('OPPO Reno15 Pro Max 5G', '6.78in AMOLED 120Hz, 200MP main camera, 4K HDR video'),
        ('OPPO Reno15 Pro 5G', '6.78in AMOLED 120Hz, 200MP main camera, 4K HDR video'),
        ('OPPO Reno15 Pro Mini 5G', 'Compact 6.31in AMOLED, 200MP camera, large battery'),
        ('OPPO Reno15 5G', '6.59in AMOLED 120Hz, 50MP ultrawide selfie, 3.5x telephoto'),
        ('OPPO Reno15 F 5G', '6.7in AMOLED 120Hz, 50MP camera, 7000mAh battery'),
        ('OPPO Reno15 FS 5G', '6.7in AMOLED 120Hz, 50MP camera, large battery'),
        ('OPPO Reno15c 5G', '6.7in AMOLED 120Hz, 50MP camera, large battery'),
        ('OPPO Reno14 F 5G', '6.7in AMOLED 120Hz, 50MP camera, 6000mAh battery'),
        ('OPPO Reno14 FS 5G', '6.7in AMOLED 120Hz, 50MP camera, large battery'),
        ('OPPO A7 Pro Max 5G', '1.5K AMOLED, 50MP AI zoom selfie, 10000mAh battery'),
        ('OPPO A7 Pro 5G', '6.7in AMOLED 120Hz, 50MP camera, NetworkBoost chip'),
        ('OPPO A6 Pro 5G', '6.7in AMOLED 120Hz, 50MP camera, large battery'),
        ('OPPO A6 5G', '6.7in 120Hz display, 50MP camera, 6000mAh battery'),
        ('OPPO A6c', '6.7in 90Hz display, 50MP camera, 5000mAh battery'),
        ('OPPO A6s 5G', '5G, 6.7in 120Hz display, 50MP camera, large battery'),
        ('OPPO A6x', '6.7in 90Hz display, 50MP camera, large battery'),
        ('OPPO A5x 5G', '5G, 6.7in 120Hz display, 50MP camera, large battery'),
        ('OPPO F35 Pro 5G', '5G, 6.7in AMOLED 120Hz, 50MP camera, large battery'),
        ('OPPO F33 Pro 5G', '5G, 6.7in AMOLED 120Hz, 50MP camera, large battery'),
        ('OPPO F31 Pro+ 5G', '5G, 6.7in AMOLED 120Hz, 50MP camera, large battery'),
        ('OPPO F31 Pro 5G', '5G, 6.7in AMOLED 120Hz, 50MP camera, large battery'),
        ('OPPO F31 5G', '5G, 6.7in 120Hz display, 50MP camera, large battery'),
        ('OPPO K14 Plus 5G', '5G, 6.7in AMOLED 120Hz, 50MP camera, large battery'),
        ('OPPO K14 5G', '5G, 6.7in 120Hz display, 50MP camera, large battery'),
        ('OPPO K14 Lite', '6.7in 120Hz display, 50MP camera, large battery'),
        ('OPPO K14x 5G', '5G, 6.7in 120Hz display, 50MP camera, large battery'),
        ('OPPO K15', '6.7in 120Hz display, 50MP camera, large battery'),
        ('OPPO K15 Pro', '6.7in 120Hz display, 50MP camera, large battery'),
        ('OPPO K15 Pro+', '6.7in AMOLED 120Hz, 50MP camera, large battery'),
        ('OPPO K15s', '6.7in 120Hz display, 50MP camera, large battery'),
    ],
    'realme': [
        ('realme GT 8', 'Snapdragon 8 Elite Gen 5, 2K 144Hz AMOLED, 7000mAh battery'),
        ('realme GT 7T', 'Flagship performance, 120Hz AMOLED, large battery'),
        ('realme 16 Pro+ 5G', '5G, curved AMOLED 120Hz, 50MP periscope telephoto'),
        ('realme 16 Pro 5G', '5G, curved AMOLED 120Hz, 50MP camera'),
        ('realme 15 Pro 5G', '5G, 6.78in AMOLED 120Hz, 50MP camera, 7000mAh battery'),
        ('realme 15 5G', '5G, 6.78in AMOLED 120Hz, 50MP camera, 7000mAh battery'),
        ('realme 15x 5G', '5G, 6.81in 144Hz display, 50MP camera, 7000mAh battery'),
        ('realme 15 Lite', '6.67in AMOLED 120Hz, 50MP camera, 5000mAh battery'),
        ('realme 15T', '6.8in AMOLED 120Hz, 50MP camera, 7000mAh battery'),
        ('realme P4 5G', '5G, 6.78in AMOLED 120Hz, 50MP camera, large battery'),
        ('realme P4 Pro 5G', '5G, 6.78in AMOLED 120Hz, 50MP camera, large battery'),
        ('realme Note 80', '6.74in 90Hz display, 50MP camera, large battery'),
        ('realme Note 70', '6.74in 90Hz display, 13MP camera, 6300mAh battery'),
        ('realme Note 70T', '6.74in 90Hz display, 13MP camera, 6000mAh battery'),
        ('realme Neo 8', 'Snapdragon flagship chipset, 165Hz display, 50MP periscope camera'),
        ('realme Neo 7', 'Flagship performance, 120Hz AMOLED, large battery'),
        ('realme Neo 7 Turbo', 'Flagship performance, 144Hz AMOLED, large battery'),
        ('realme C85', '6.7in 120Hz display, 50MP camera, 7000mAh battery'),
    ],
    'vivo': [
        ('vivo X500 Pro Max', 'Dimensity 9600 Pro, ZEISS cameras, 6.8in AMOLED 120Hz'),
        ('vivo X500 Pro', 'Dimensity 9600 Pro, ZEISS cameras, 6.8in AMOLED 120Hz'),
        ('vivo X500', 'Dimensity 9600, ZEISS cameras, 6.8in AMOLED 120Hz'),
        ('vivo X300 Ultra', 'ZEISS master lens set, flagship Snapdragon, 2K AMOLED'),
        ('vivo X300', 'ZEISS 200MP main camera, 6.31in AMOLED 120Hz'),
        ('vivo X300 FE', 'ZEISS cameras, 6.31in AMOLED 120Hz, compact flagship'),
        ('vivo X300s', 'ZEISS APO telephoto, 6.78in AMOLED 120Hz'),
        ('vivo X Fold6', 'Book-style foldable, 8.03in inner AMOLED, Dimensity 9500'),
        ('vivo X Fold5', 'Ultra-light book foldable, 217g, 6000mAh battery'),
        ('vivo X200 Ultra', 'ZEISS triple camera, flagship Snapdragon, 2K AMOLED'),
        ('vivo X200s', 'ZEISS cameras, 6.67in AMOLED 120Hz'),
        ('vivo V70 FE', '6.78in AMOLED 120Hz, 50MP camera, large battery'),
        ('vivo V70', '6.78in AMOLED 120Hz, 50MP camera, large battery'),
        ('vivo V60', '6.78in AMOLED 120Hz, 50MP ZEISS camera, 6500mAh battery'),
        ('vivo V60 Lite', '6.78in AMOLED 120Hz, 50MP camera, large battery'),
        ('vivo Y05e', '6.74in 90Hz display, 13MP camera, 5000mAh battery'),
        ('vivo Y600i', '6.78in 120Hz display, 50MP camera, 8000mAh battery'),
        ('vivo Y600 Turbo', '6.78in 120Hz display, 50MP camera, large battery'),
        ('vivo Y600 Pro', '6.78in 120Hz display, 50MP camera, large battery'),
        ('vivo Y60', '6.74in 90Hz display, 50MP camera, 6500mAh battery'),
        ('vivo Y500i', '6.74in 90Hz display, 50MP camera, 7200mAh battery'),
        ('vivo Y500 Pro', '6.78in AMOLED 120Hz, 200MP camera, large battery'),
        ('vivo Y500', '6.78in 120Hz display, 50MP camera, 8200mAh battery'),
        ('vivo Y50 5G', '5G, 6.74in 120Hz display, 50MP camera, 6000mAh battery'),
        ('vivo Y300 GT', '5G, 6.78in AMOLED 120Hz, 50MP camera, large battery'),
        ('vivo Y300t', '6.78in AMOLED 120Hz, 50MP camera, 6500mAh battery'),
    ],
    'HONOR': [
        ('HONOR Magic V6', 'Book-style foldable, Snapdragon flagship, large inner AMOLED'),
        ('HONOR Magic V5', 'Worlds slimmest book foldable, 5820mAh battery'),
        ('HONOR Magic8', 'Flagship Snapdragon, 6.58in AMOLED 120Hz, AI cameras'),
        ('HONOR Magic7', 'Snapdragon 8 Elite, 6.7in AMOLED 120Hz, 50MP camera'),
        ('HONOR Magic7 RSR Porsche Design', 'PORSCHE DESIGN flagship, Snapdragon 8 Elite, 200MP camera'),
        ('HONOR 600 Pro', '200MP AI night camera, 7000mAh battery, AI image to video'),
        ('HONOR 600', '200MP AI night camera, 7000mAh battery, AI image to video'),
        ('HONOR 600 Lite', 'AI camera button, 108MP camera, 6520mAh battery'),
        ('HONOR 500 Smart 5G', '5G, 5260mAh battery, 50MP AI camera, 256GB storage'),
        ('HONOR 400 Smart 5G', '5G, 6500mAh dual-cell battery, IP65, AI button'),
        ('HONOR 400 Lite', 'AI camera button, 108MP camera, 3500-nit AMOLED display'),
        ('HONOR X9e Pro', '11000mAh battery, 108MP OIS camera, 80W SuperCharge'),
        ('HONOR X9e s', '8560mAh battery, IP69K, 2.5m drop resistance'),
        ('HONOR X9d', '8300mAh battery, IP69K, 108MP OIS AI camera'),
        ('HONOR X8d', '7000mAh battery, slim design, IP65, AI button'),
        ('HONOR X7e Plus', '8100mAh battery, IP69K, 2.5m drop resistance'),
        ('HONOR X7e', '7500mAh battery, 45W charging, AI button'),
        ('HONOR X7d', '6500mAh dual-cell battery, IP65, AI button'),
        ('HONOR X6e', '7500mAh battery, 45W charging, 50MP AI camera'),
        ('HONOR X6d 5G', '5G, 5260mAh battery, 50MP AI camera, 256GB storage'),
        ('HONOR X5d Plus', '5260mAh battery, 50MP camera, 256GB storage'),
        ('HONOR X5d', '5260mAh battery, 13MP camera, 6.74in 90Hz display'),
        ('HONOR X5c Plus', '5260mAh battery, 50MP camera, 128GB storage'),
        ('HONOR X5c', '5260mAh battery, 13MP camera, 6.74in 90Hz display'),
        ('HONOR X5b Plus', '5200mAh battery, 50MP camera, large storage'),
        ('HONOR X5b', '5200mAh battery, 13MP dual camera, 64GB storage'),
        ('HONOR Play10', '6.6in 90Hz display, Helio G81, 5000mAh battery'),
        ('HONOR Play20A', '6.9in display, 6000mAh battery, rear-display experience'),
    ],
    'itel': [
        ('itel S26 Ultra', '6.78in AMOLED 144Hz, 50MP camera, 6-year smoothness'),
        ('itel S18 Pro', '6.78in AMOLED 120Hz, 50MP camera, large battery'),
        ('itel RS4', '6.78in AMOLED 120Hz, 50MP camera, fast charging'),
        ('itel Power 80', '6.78in 120Hz display, 50MP camera, 10000mAh battery'),
        ('itel Power 70', '6.78in 120Hz display, 50MP camera, 10000mAh dual battery'),
        ('itel Power 65', '6.78in 120Hz display, 50MP camera, 7000mAh battery'),
        ('itel Power 55 T', '6.6in 90Hz display, 50MP camera, 5000mAh battery'),
        ('itel Power 55', '6.6in 90Hz display, 50MP camera, 5000mAh battery'),
        ('itel Power 55+', '6.6in 90Hz display, 50MP camera, 5000mAh battery'),
        ('itel Power 55 5G', '5G, 6.6in 120Hz display, 50MP camera, 5000mAh battery'),
        ('itel City 300 5G', '5G, 6.67in 120Hz display, 13MP camera, 5000mAh battery'),
        ('itel City 200s', '6.6in 90Hz display, 13MP camera, large battery'),
        ('itel City 200', '6.6in 90Hz display, 13MP camera, large battery'),
        ('itel City 100', '6.6in 90Hz display, 13MP camera, 5000mAh battery'),
        ('itel A300+', '6.56in 90Hz display, 8MP camera, 6000mAh battery'),
        ('itel A300C', '6.56in 90Hz display, 8MP camera, 6000mAh battery'),
        ('itel A200+', '6.6in 90Hz display, 13MP camera, 5000mAh battery'),
        ('itel A200', '6.6in 90Hz display, 13MP camera, 5000mAh battery'),
        ('itel A100C', '6.6in 90Hz display, 8MP camera, 5000mAh battery'),
        ('itel A100', '6.6in 90Hz display, 8MP camera, 5000mAh battery'),
        ('itel A90', '6.6in 90Hz display, 8MP camera, 5000mAh battery'),
        ('itel A50', '6.6in 90Hz display, 8MP camera, 5000mAh battery'),
        ('itel A50C', '6.6in 90Hz display, 8MP camera, 5000mAh battery'),
        ('itel A20', '6.6in 90Hz display, 8MP camera, 5000mAh battery'),
        ('itel A06', '6.6in 90Hz display, 8MP camera, 5000mAh battery'),
        ('itel Zeno 300', '6.56in 90Hz display, 8MP camera, 6000mAh battery'),
        ('itel Zeno 200', '6.6in 90Hz display, 13MP camera, 5000mAh battery'),
        ('itel Zeno 100 Pro', '6.6in 90Hz display, 8MP camera, 5000mAh battery'),
        ('itel Zeno 100', '6.6in 90Hz display, 8MP camera, 5000mAh battery'),
        ('itel Zeno 20', '6.6in 90Hz display, 8MP camera, 5000mAh battery'),
        ('itel Zeno 10', '6.6in 90Hz display, 8MP camera, 5000mAh battery'),
    ],
    'Samsung': [
        # Galaxy A series - current generations
        ('Samsung Galaxy A07', '6.7in 90Hz PLS LCD, Helio G99, 5000mAh 25W, 50MP camera'),
        ('Samsung Galaxy A07 5G', '5G, 6.7in 120Hz display, Dimensity 6300, 6000mAh 25W'),
        ('Samsung Galaxy A08', '6.7in 90Hz PLS LCD, Helio G99, 6000mAh 25W, 50MP camera'),
        ('Samsung Galaxy A17', '6.7in 90Hz Super AMOLED, Helio G99, 5000mAh 25W, 50MP camera'),
        ('Samsung Galaxy A17 5G', '5G, 6.7in 90Hz Super AMOLED, Exynos 1330, 5000mAh'),
        ('Samsung Galaxy A18', '6.7in Super AMOLED, Exynos 1610, 5000mAh, 50MP camera'),
        ('Samsung Galaxy A27 5G', '5G, 6.7in 120Hz AMOLED, Snapdragon 6 Gen 3, 5000mAh'),
        ('Samsung Galaxy A37 5G', '5G, 6.7in 120Hz AMOLED, Exynos 1480, 5000mAh 45W, IP68'),
        ('Samsung Galaxy A57 5G', '5G, 6.7in FHD+ Super AMOLED Plus 120Hz, Exynos 1680, 50MP OIS + 12MP UW + 5MP macro, 5000mAh 45W, IP68'),
        # Galaxy S series - current and recent flagship generations
        ('Galaxy S26 Ultra', '6.9in QHD+ AMOLED 120Hz, Snapdragon 8 Elite Gen 5 for Galaxy, 200MP camera, 5000mAh 60W, S Pen'),
        ('Galaxy S26 FE', '6.7in AMOLED 120Hz, Exynos 2500, 50MP camera, 4900mAh 45W'),
        ('Galaxy S25 Edge', '5.8mm ultra-thin, 6.7in AMOLED 120Hz, Snapdragon 8 Elite, 200MP camera, 3900mAh'),
        ('Galaxy S24', '6.2in FHD+ AMOLED 120Hz, Exynos 2400, 50MP camera, 4000mAh 25W'),
        ('Galaxy S24+', '6.7in QHD+ AMOLED 120Hz, Exynos 2400, 50MP camera, 4900mAh 45W'),
        ('Galaxy S24 Ultra', '6.8in QHD+ AMOLED 120Hz, Snapdragon 8 Gen 3, 200MP camera, 5000mAh 45W, S Pen, titanium frame'),
        ('Galaxy S24 FE', '6.7in AMOLED 120Hz, Exynos 2400e, 50MP camera, 4700mAh 25W'),
        # Galaxy Z foldables - current lineup
        ('Galaxy Z Fold8', 'Book-style foldable, 8.0in inner AMOLED 120Hz, Snapdragon 8 Elite Gen 5'),
        ('Galaxy Z Fold8 Ultra', 'Premium book foldable, 8.2in inner AMOLED, 200MP camera, Snapdragon 8 Elite Gen 5'),
        ('Galaxy Z Flip8', 'Flip foldable, 6.9in inner AMOLED 120Hz, 4.0in cover display'),
        ('Galaxy Z Fold7', 'Book foldable, 8.0in inner AMOLED 120Hz, Snapdragon 8 Elite, 200MP camera, 4400mAh'),
        ('Galaxy Z Flip7', 'Flip foldable, 6.9in inner AMOLED 120Hz, 4.1in cover display, Exynos 2500, 4300mAh'),
        ('Galaxy Z Flip7 FE', 'Flip foldable, 6.7in inner AMOLED 120Hz, 3.4in cover display, Exynos 2400'),
        ('Galaxy Z TriFold', 'Tri-fold design, 10in main AMOLED display, Snapdragon 8 Elite'),
    ],
}


class Command(BaseCommand):
    help = (
        'Add the current phone lineups for Infinix, TECNO, ASUS, OPPO, realme, '
        'vivo, HONOR, itel and Samsung (with complete Galaxy A, S and Z series).'
    )

    def handle(self, *args, **options):
        category, _ = Category.objects.get_or_create(
            name='Smartphones',
            defaults={'description': 'Mobile phones for calls, photography, gaming, and everyday use.'},
        )

        created = 0
        skipped = 0
        per_brand = {}

        with transaction.atomic():
            for brand, phones in PHONES.items():
                brand_created = 0
                brand_skipped = 0
                for name, specs in phones:
                    _, was_created = Product.objects.get_or_create(
                        brand=brand,
                        name=name,
                        defaults={
                            'category': category,
                            'description': f'{name} smartphone.',
                            'specifications': specs,
                            'source_url': BRANDS[brand],
                            'price': None,
                            'stock_quantity': None,
                        },
                    )
                    if was_created:
                        created += 1
                        brand_created += 1
                    else:
                        skipped += 1
                        brand_skipped += 1
                per_brand[brand] = (brand_created, brand_skipped)

        for brand, (brand_created, brand_skipped) in per_brand.items():
            self.stdout.write(
                f'  {brand}: {brand_created} added, {brand_skipped} already present'
            )

        self.stdout.write(self.style.SUCCESS(
            f'Phone catalog refreshed: {created} added, {skipped} already present.'
        ))
        self.stdout.write(
            'Smartphones in catalog: %s' % Product.objects.filter(category=category).count()
        )
