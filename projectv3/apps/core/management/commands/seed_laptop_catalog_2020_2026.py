"""Seed a curated 2020-2026 laptop catalog for the requested brands.

Sony is intentionally absent because Sony sold its VAIO laptop business in
2014 and has not sold laptops since. RedMagic currently has only the Titan 16
Pro. The command is safe to re-run and never overwrites an existing photo.

Run from the project root:
    venv\\Scripts\\python.exe projectv3\\manage.py seed_laptop_catalog_2020_2026
    venv\\Scripts\\python.exe projectv3\\manage.py seed_laptop_catalog_2020_2026 --dry-run
"""

from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.core.models import Category, Product


LAPTOPS = [
    ('Apple', 'Apple MacBook Air 13 M1 (2020)', 52990,
     '13.3in Retina, Apple M1 8-core, 8GB/256GB, 18hr battery, 1.29kg, Touch ID'),
    ('Apple', 'Apple MacBook Pro 13 M1 (2020)', 57990,
     '13.3in Retina, Apple M1 8-core, 8GB/256GB, 20hr battery, 1.4kg, Touch Bar'),
    ('Apple', 'Apple MacBook Pro 14 M1 Pro (2021)', 109990,
     '14.2in Liquid Retina XDR 120Hz, Apple M1 Pro 10-core, 16GB/512GB, 17hr battery, 1.6kg'),
    ('Apple', 'Apple MacBook Pro 16 M1 Max (2021)', 159990,
     '16.2in Liquid Retina XDR 120Hz, Apple M1 Max 32-core GPU, 32GB/1TB, 21hr battery, 2.1kg'),
    ('Apple', 'Apple MacBook Air 13 M2 (2022)', 61990,
     '13.6in Liquid Retina, Apple M2 8-core, 8GB/256GB, 18hr battery, 1.24kg, MagSafe'),
    ('Apple', 'Apple MacBook Pro 13 M2 (2022)', 67990,
     '13.3in Retina, Apple M2 8-core, 8GB/256GB, 20hr battery, 1.4kg, Touch Bar'),
    ('Apple', 'Apple MacBook Air 15 M2 (2023)', 74990,
     '15.3in Liquid Retina, Apple M2 8-core, 8GB/256GB, 18hr battery, 1.51kg'),
    ('Apple', 'Apple MacBook Pro 14 M2 Pro (2023)', 129990,
     '14.2in Liquid Retina XDR 120Hz, Apple M2 Pro 10-core, 16GB/512GB, 18hr battery, 1.6kg'),
    ('Apple', 'Apple MacBook Pro 16 M2 Max (2023)', 179990,
     '16.2in Liquid Retina XDR 120Hz, Apple M2 Max 38-core GPU, 32GB/1TB, 22hr battery, 2.15kg'),
    ('Apple', 'Apple MacBook Air 15 M3 (2024)', 82990,
     '15.3in Liquid Retina, Apple M3 8-core, 8GB/256GB, 18hr battery, 1.51kg'),
    ('Apple', 'Apple MacBook Pro 14 M4 (2024)', 109990,
     '14.2in Liquid Retina XDR 120Hz, Apple M4 10-core, 16GB/512GB, 24hr battery, 1.55kg'),
    ('Apple', 'Apple MacBook Pro 16 M4 Max (2024)', 189990,
     '16.2in Liquid Retina XDR 120Hz, Apple M4 Max 40-core GPU, 36GB/1TB, 22hr battery, 2.14kg'),
    ('Apple', 'Apple MacBook Air 13 M4 (2025)', 69990,
     '13.6in Liquid Retina, Apple M4 10-core, 16GB/256GB, 18hr battery, 1.24kg'),
    ('Apple', 'Apple MacBook Air 15 M4 (2025)', 84990,
     '15.3in Liquid Retina, Apple M4 10-core, 16GB/256GB, 18hr battery, 1.51kg'),
    ('Apple', 'Apple MacBook Pro 14 M5 (2025)', 119990,
     '14.2in Liquid Retina XDR 120Hz, Apple M5 10-core, 16GB/512GB, 24hr battery, 1.55kg'),
    ('Apple', 'Apple MacBook Air 13 M5 (2026)', 74990,
     '13.6in Liquid Retina, Apple M5 10-core, 16GB/512GB, Wi-Fi 7, 18hr battery, 1.24kg'),
    ('Apple', 'Apple MacBook Neo 13 A18 Pro (2026)', 39990,
     '13in Liquid Retina, Apple A18 Pro, 8GB/256GB, aluminum design, all-day battery, 1.2kg'),
    ('Apple', 'Apple MacBook Pro 14 M6 (2026)', 129990,
     '14.2in Liquid Retina XDR 120Hz, Apple M6 10-core, 16GB/512GB, Wi-Fi 7, 24hr battery'),
    ('ASUS', 'ASUS ZenBook 14 UX425 (2020)', 49995,
     '14in FHD, Intel Core i5-1035G1, 8GB/512GB, 67Wh, 1.13kg, NumberPad'),
    ('ASUS', 'ASUS ZenBook 13 OLED UM325 (2021)', 54995,
     '13.3in FHD OLED, AMD Ryzen 7 5700U, 16GB/512GB, 67Wh, 1.14kg'),
    ('ASUS', 'ASUS ZenBook 14 OLED UX3402 (2022)', 64995,
     '14in 2.8K OLED 90Hz, Intel Core i7-1260P, 16GB/512GB, 75Wh, 1.39kg'),
    ('ASUS', 'ASUS Zenbook S 14 OLED UX5406 (2024)', 89995,
     '14in 3K OLED 120Hz, Intel Core Ultra 7 258V, 32GB/1TB, 72Wh, 1.2kg'),
    ('ASUS', 'ASUS Vivobook 15 M513 (2021)', 39995,
     '15.6in FHD, AMD Ryzen 5 5500U, 8GB/512GB, 42Wh, 1.8kg'),
    ('ASUS', 'ASUS Vivobook 16X K3605 (2023)', 54995,
     '16in FHD+ 120Hz, Intel Core i5-12500H, RTX 3050 4GB, 16GB/512GB, 50Wh'),
    ('ASUS', 'ASUS Vivobook S 15 OLED S5507 (2024)', 74995,
     '15.6in 3K OLED 120Hz, Snapdragon X Elite, 16GB/1TB, 70Wh, 1.42kg'),
    ('ASUS', 'ASUS Vivobook Pro 16X OLED K6604 (2023)', 119995,
     '16in 3.2K OLED 120Hz, Intel Core i9-13980HX, RTX 4070 8GB, 32GB/1TB, 90Wh'),
    ('ASUS', 'ASUS ROG Zephyrus G14 GA401 (2020)', 74995,
     '14in FHD 120Hz, AMD Ryzen 9 4900HS, GTX 1660 Ti 6GB, 16GB/1TB, 76Wh, 1.6kg'),
    ('ASUS', 'ASUS ROG Zephyrus G15 GA503 (2021)', 99995,
     '15.6in QHD 165Hz, AMD Ryzen 9 5900HS, RTX 3070 8GB, 16GB/1TB, 90Wh, 1.9kg'),
    ('ASUS', 'ASUS ROG Zephyrus G14 GA402 (2022)', 109995,
     '14in QHD 120Hz, AMD Ryzen 9 6900HS, RX 6800S 8GB, 16GB/1TB, 76Wh, 1.65kg'),
    ('ASUS', 'ASUS ROG Strix G15 G513 (2021)', 84995,
     '15.6in FHD 300Hz, AMD Ryzen 9 5900HX, RTX 3060 6GB, 16GB/512GB, 90Wh'),
    ('ASUS', 'ASUS ROG Strix G16 G614 (2023)', 109995,
     '16in FHD+ 165Hz, Intel Core i7-13650HX, RTX 4060 8GB, 16GB/512GB, 90Wh'),
    ('ASUS', 'ASUS ROG Strix SCAR 16 G634 (2024)', 159995,
     '16in 2.5K Mini LED 240Hz, Intel Core i9-14900HX, RTX 4080 12GB, 32GB/1TB, 90Wh'),
    ('ASUS', 'ASUS TUF Gaming A15 FA506 (2020)', 54995,
     '15.6in FHD 144Hz, AMD Ryzen 7 4800H, GTX 1660 Ti 6GB, 16GB/512GB, 90Wh'),
    ('ASUS', 'ASUS TUF Gaming F15 FX506 (2021)', 59995,
     '15.6in FHD 144Hz, Intel Core i5-11400H, RTX 3050 Ti 4GB, 8GB/512GB, 90Wh'),
    ('ASUS', 'ASUS ProArt PX13 HN7306 (2024)', 129995,
     '13.3in 3K OLED touch, AMD Ryzen AI 9 HX 370, RTX 4060 8GB, 32GB/1TB, 73Wh'),
    ('ASUS', 'ASUS Zenbook DUO UX8406 (2024)', 139995,
     '14in dual 3K OLED 120Hz touch, Intel Core Ultra 9 185H, 32GB/1TB, 75Wh'),
    ('ASUS', 'ASUS Zenbook S 16 UM5606 (2024)', 89995,
     '16in 3K OLED 120Hz, AMD Ryzen AI 9 365, 24GB/1TB, 78Wh, 1.5kg'),
    ('ASUS', 'ASUS ROG Zephyrus G14 (2026) GU405', 149995,
     '14in 3K OLED 120Hz, Intel Core Ultra 9 386H, RTX 5070 Ti 12GB, 32GB/1TB, 73Wh'),
    ('ASUS', 'ASUS ROG Zephyrus G16 (2026) GU606', 189995,
     '16in 2.5K OLED 240Hz, Intel Core Ultra 9 386H, RTX 5080 16GB, 32GB/1TB, 90Wh'),
    ('ASUS', 'ASUS ROG Zephyrus Duo 16 (2026) GX651', 229995,
     '16in dual 3K OLED 120Hz, Intel Core Ultra 9 386H, RTX 5090 24GB, 64GB/2TB, 90Wh'),
    ('ASUS', 'ASUS ROG Strix SCAR 18 (2026) G835', 239995,
     '18in 4K Mini LED 240Hz, Intel Core Ultra 9 290HX Plus, RTX 5090 24GB, 64GB/2TB'),
    ('ASUS', 'ASUS ROG Strix G16 (2026) G615', 139995,
     '16in 2.5K 240Hz, Intel Core Ultra 9 386H, RTX 5070 8GB, 32GB/1TB, 90Wh'),
    ('ASUS', 'ASUS Zenbook A16 (2026) UX5606', 89995,
     '16in 3K OLED 120Hz, Snapdragon X2 Elite, 32GB/1TB, 70Wh, 1.4kg'),
    ('ASUS', 'ASUS ProArt P16 (2026) H7607', 169995,
     '16in 4K OLED, NVIDIA RTX Spark, 32GB/2TB, 90Wh, creator-calibrated'),
    ('ASUS', 'ASUS TUF Gaming A16 (2026) FA608', 89995,
     '16in FHD+ 165Hz, AMD Ryzen 9 8940HX, RTX 5060 8GB, 16GB/1TB, 90Wh'),
    ('Dell', 'Dell XPS 13 9310 (2020)', 69995,
     '13.4in FHD+, Intel Core i7-1165G7, 16GB/512GB, 52Wh, 1.2kg'),
    ('Dell', 'Dell XPS 15 9500 (2020)', 99995,
     '15.6in FHD+, Intel Core i7-10750H, GTX 1650 Ti 4GB, 16GB/512GB, 86Wh'),
    ('Dell', 'Dell XPS 17 9700 (2020)', 129995,
     '17in FHD+, Intel Core i7-10875H, RTX 2060 6GB, 16GB/512GB, 97Wh'),
    ('Dell', 'Dell XPS 13 9305 (2021)', 64995,
     '13.3in FHD, Intel Core i5-1135G7, 8GB/256GB, 52Wh, 1.16kg'),
    ('Dell', 'Dell XPS 13 Plus 9320 (2022)', 89995,
     '13.4in 3.5K OLED touch, Intel Core i7-1260P, 16GB/512GB, 55Wh, 1.26kg'),
    ('Dell', 'Dell XPS 15 9520 (2022)', 119995,
     '15.6in 3.5K OLED touch, Intel Core i7-12700H, RTX 3050 Ti 4GB, 16GB/512GB, 86Wh'),
    ('Dell', 'Dell XPS 17 9720 (2022)', 149995,
     '17in 4K touch, Intel Core i7-12700H, RTX 3060 6GB, 32GB/1TB, 97Wh'),
    ('Dell', 'Dell XPS 13 9345 Snapdragon (2024)', 84995,
     '13.4in FHD+, Snapdragon X Elite, 16GB/512GB, 55Wh, 1.19kg'),
    ('Dell', 'Dell XPS 13 9350 (2024)', 89995,
     '13.4in 3K OLED touch, Intel Core Ultra 7 258V, 32GB/1TB, 55Wh, 1.19kg'),
    ('Dell', 'Dell Inspiron 15 3511 (2022)', 39995,
     '15.6in FHD, Intel Core i5-1135G7, 8GB/512GB, 41Wh, 1.8kg'),
    ('Dell', 'Dell Inspiron 14 7420 2-in-1 (2022)', 54995,
     '14in FHD+ touch, Intel Core i5-1235U, 8GB/512GB, 54Wh, 1.6kg'),
    ('Dell', 'Dell Latitude 7420 (2021)', 69995,
     '14in FHD, Intel Core i7-1185G7, 16GB/512GB, 63Wh, 1.3kg'),
    ('Dell', 'Dell Latitude 7440 (2023)', 79995,
     '14in FHD+, Intel Core i7-1365U, 16GB/512GB, 57Wh, 1.3kg'),
    ('Dell', 'Dell Latitude 7450 (2024)', 84995,
     '14in FHD+, Intel Core Ultra 7 165U, 16GB/512GB, 57Wh, 1.3kg'),
    ('Dell', 'Dell Precision 5570 (2022)', 149995,
     '15.6in FHD+, Intel Core i7-12800H, RTX A2000 8GB, 32GB/1TB, 86Wh'),
    ('Dell', 'Dell Precision 5680 (2023)', 169995,
     '16in FHD+, Intel Core i7-13800H, RTX 4000 Ada 12GB, 32GB/1TB, 99Wh'),
    ('Dell', 'Dell G15 5511 (2021)', 69995,
     '15.6in FHD 120Hz, Intel Core i5-11400H, RTX 3050 4GB, 8GB/512GB, 56Wh'),
    ('Dell', 'Dell G15 5520 (2022)', 74995,
     '15.6in FHD 120Hz, Intel Core i5-12500H, RTX 3050 4GB, 16GB/512GB, 56Wh'),
    ('Dell', 'Dell G16 7620 (2022)', 99995,
     '16in QHD+ 165Hz, Intel Core i7-12700H, RTX 3060 6GB, 16GB/512GB, 86Wh'),
    ('Dell', 'Dell Alienware m15 R5 (2021)', 109995,
     '15.6in FHD 165Hz, AMD Ryzen 7 5800H, RTX 3060 6GB, 16GB/512GB, 86Wh'),
    ('Dell', 'Dell Alienware m15 R7 (2022)', 119995,
     '15.6in QHD 240Hz, Intel Core i7-12700H, RTX 3070 Ti 8GB, 16GB/1TB, 86Wh'),
    ('Dell', 'Dell Alienware m16 R1 (2023)', 139995,
     '16in QHD+ 240Hz, Intel Core i9-13900HX, RTX 4070 8GB, 32GB/1TB, 86Wh'),
    ('Dell', 'Dell Alienware x14 (2022)', 119995,
     '14in FHD 144Hz, Intel Core i7-12700H, RTX 3060 6GB, 16GB/512GB, 80Wh'),
    ('Dell', 'Dell Alienware x16 (2023)', 169995,
     '16in QHD+ 240Hz, Intel Core i9-13900HK, RTX 4080 12GB, 32GB/1TB, 90Wh'),
    ('Dell', 'Dell Alienware 18 Area-51 (2025)', 229995,
     '18in QHD+ 300Hz, Intel Core Ultra 9 275HX, RTX 5080 16GB, 32GB/1TB, 96Wh'),
    ('Dell', 'Dell Alienware 16 Area-51 (2025)', 179995,
     '16in QHD+ 240Hz, Intel Core Ultra 9 275HX, RTX 5070 Ti 12GB, 32GB/1TB, 96Wh'),
    ('Dell', 'Dell XPS 14 (2026) DA14260', 129995,
     '14in 3K OLED 120Hz, Intel Core Ultra 7 355, 16GB/512GB, 70Wh, 1.4kg'),
    ('Dell', 'Dell XPS 16 (2026) DA16260', 159995,
     '16in 4K OLED 120Hz, Intel Core Ultra 9 375H, 32GB/1TB, 99Wh, 1.9kg'),
    ('Dell', 'Dell XPS 13 (2026)', 99995,
     '13in 3K OLED touch, Intel Core Ultra 7 355, 16GB/512GB, 55Wh, 1.1kg'),
    ('Dell', 'Dell XPS 16 Creator Edition (2026)', 219995,
     '16in 4K OLED, NVIDIA RTX Spark, 32GB/2TB, 99Wh, creator-calibrated'),
    ('Dell', 'Dell Alienware 15 (2026)', 139995,
     '15.3in WUXGA 165Hz, Intel Core 7 240H, RTX 4050 6GB, 16GB/512GB'),
    ('Dell', 'Dell Pro 14 Premium (2026)', 119995,
     '14in 2.8K OLED, Intel Core Ultra 7 355, 32GB/1TB, 64Wh, 1.2kg'),
    ('HP', 'HP Spectre x360 13 (2020)', 89995,
     '13.3in 4K OLED touch, Intel Core i7-1065G7, 16GB/512GB, 60Wh, 1.27kg'),
    ('HP', 'HP Spectre x360 14 (2021)', 99995,
     '13.5in 3K2K OLED touch, Intel Core i7-1165G7, 16GB/1TB, 66Wh, 1.36kg'),
    ('HP', 'HP Spectre x360 16 (2022)', 119995,
     '16in 3K+ OLED touch, Intel Core i7-12700H, RTX 3050 4GB, 16GB/1TB, 83Wh'),
    ('HP', 'HP Envy x360 15 (2021)', 64995,
     '15.6in FHD touch, AMD Ryzen 5 5500U, 16GB/512GB, 51Wh, 1.8kg'),
    ('HP', 'HP Pavilion Aero 13 (2021)', 49995,
     '13.3in WUXGA, AMD Ryzen 5 5600U, 16GB/512GB, 43Wh, 0.97kg'),
    ('HP', 'HP Pavilion Plus 14 (2022)', 59995,
     '14in 2.8K OLED, Intel Core i5-12500H, 16GB/512GB, 51Wh, 1.4kg'),
    ('HP', 'HP EliteBook 840 G7 (2020)', 69995,
     '14in FHD, Intel Core i7-10610U, 16GB/512GB, 53Wh, 1.33kg'),
    ('HP', 'HP EliteBook 840 G8 (2021)', 74995,
     '14in FHD, Intel Core i7-1165G7, 16GB/512GB, 53Wh, 1.32kg'),
    ('HP', 'HP EliteBook 840 G9 (2022)', 79995,
     '14in WUXGA, Intel Core i7-1255U, 16GB/512GB, 51Wh, 1.36kg'),
    ('HP', 'HP EliteBook 840 G10 (2023)', 84995,
     '14in WUXGA, Intel Core i7-1355U, 16GB/512GB, 51Wh, 1.36kg'),
    ('HP', 'HP ProBook 450 G8 (2021)', 49995,
     '15.6in FHD, Intel Core i5-1135G7, 8GB/512GB, 45Wh, 1.74kg'),
    ('HP', 'HP ProBook 450 G9 (2022)', 54995,
     '15.6in FHD, Intel Core i5-1235U, 16GB/512GB, 51Wh, 1.74kg'),
    ('HP', 'HP ProBook 450 G10 (2023)', 59995,
     '15.6in FHD, Intel Core i5-1335U, 16GB/512GB, 51Wh, 1.74kg'),
    ('HP', 'HP ZBook Firefly 14 G8 (2021)', 99995,
     '14in FHD+, Intel Core i7-1165G7, NVIDIA T500 4GB, 16GB/512GB, 53Wh'),
    ('HP', 'HP OMEN 15 (2020)', 79995,
     '15.6in FHD 144Hz, Intel Core i7-10750H, RTX 2060 6GB, 16GB/512GB, 70Wh'),
    ('HP', 'HP OMEN 16 (2022)', 99995,
     '16.1in QHD 165Hz, Intel Core i7-12700H, RTX 3060 6GB, 16GB/512GB, 83Wh'),
    ('HP', 'HP OMEN 17 (2023)', 129995,
     '17.3in QHD 240Hz, Intel Core i9-13900HX, RTX 4070 8GB, 32GB/1TB, 83Wh'),
    ('HP', 'HP Victus 16 (2021)', 64995,
     '16.1in FHD 144Hz, AMD Ryzen 5 5600H, RTX 3050 4GB, 8GB/512GB, 70Wh'),
    ('HP', 'HP Victus 15 (2022)', 59995,
     '15.6in FHD 144Hz, Intel Core i5-12450H, RTX 3050 4GB, 8GB/512GB, 70Wh'),
    ('HP', 'HP OmniBook X 14 (2024)', 74995,
     '14in 2.2K touch, Snapdragon X Elite, 16GB/512GB, 59Wh, 1.34kg'),
    ('HP', 'HP OmniBook Ultra 14 (2024)', 89995,
     '14in 2.8K OLED touch, AMD Ryzen AI 9 365, 32GB/1TB, 68Wh, 1.4kg'),
    ('HP', 'HP OmniBook 7 Aero 13 (2025)', 69995,
     '13.3in 2.8K OLED, AMD Ryzen AI 7 350, 16GB/512GB, 43Wh, 0.99kg'),
    ('HP', 'HP OmniBook 5 14 (2026)', 54995,
     '14in 2.8K OLED, Intel Core 5, 16GB/512GB, 59Wh, 1.3kg'),
    ('HP', 'HP OmniBook 3 16 (2026)', 64995,
     '16in 2.5K OLED, Intel Core 7, 16GB/1TB, 59Wh, 1.7kg'),
    ('HP', 'HP OmniBook Ultra 14 (2026)', 109995,
     '14in 2.8K OLED touch, Snapdragon X2 Elite, 32GB/1TB, 68Wh, 1.3kg'),
    ('HP', 'HP EliteBook X G2i 14 (2026)', 129995,
     '14in 2.8K OLED, Intel Core Ultra X7 Series 3, 32GB/1TB, 64Wh, 1.2kg'),
    ('HP', 'HP EliteBook X G2a 14 (2026)', 124995,
     '14in 2.8K OLED, AMD Ryzen AI 9 PRO 400, 32GB/1TB, 64Wh, 1.2kg'),
    ('HP', 'HP EliteBook X Flip G2i 14 (2026)', 134995,
     '14in 2.8K OLED touch 360, Intel Core Ultra X7 Series 3, 32GB/1TB, 64Wh'),
    ('HP', 'HP EliteBook 8 G1i 16 (2025)', 89995,
     '16in WUXGA, Intel Core Ultra 7 255H, 16GB/512GB, 56Wh, 1.8kg'),
    ('HP', 'HP ProBook 4 G1i 14 (2026)', 59995,
     '14in WUXGA, Intel Core Ultra 5 225U, 16GB/512GB, 51Wh, 1.4kg'),
    ('HP', 'HP HyperX OMEN 15 (2026)', 119995,
     '15.3in 3K OLED 120Hz, Intel Core Ultra 9 386H, RTX 5070 8GB, 32GB/1TB'),
    ('HP', 'HP HyperX OMEN 16 (2026)', 149995,
     '16in 2.5K OLED 240Hz, Intel Core Ultra 9 386H, RTX 5080 16GB, 32GB/1TB'),
    ('HP', 'HP HyperX OMEN MAX 16 (2026)', 199995,
     '16in 2.5K OLED 240Hz, Intel Core Ultra 9 290HX Plus, RTX 5090 24GB, 64GB/2TB'),
    ('Lenovo', 'Lenovo ThinkPad X1 Carbon Gen 8 (2020)', 89995,
     '14in FHD, Intel Core i7-10510U, 16GB/512GB, 51Wh, 1.09kg'),
    ('Lenovo', 'Lenovo ThinkPad X1 Carbon Gen 9 (2021)', 99995,
     '14in WUXGA, Intel Core i7-1165G7, 16GB/512GB, 57Wh, 1.13kg'),
    ('Lenovo', 'Lenovo ThinkPad X1 Carbon Gen 10 (2022)', 109995,
     '14in WUXGA, Intel Core i7-1260P, 16GB/512GB, 57Wh, 1.12kg'),
    ('Lenovo', 'Lenovo ThinkPad X1 Carbon Gen 11 (2023)', 119995,
     '14in WUXGA, Intel Core i7-1355U, 16GB/512GB, 57Wh, 1.12kg'),
    ('Lenovo', 'Lenovo ThinkPad X1 Carbon Gen 12 (2024)', 129995,
     '14in 2.8K OLED, Intel Core Ultra 7 155H, 32GB/1TB, 57Wh, 1.09kg'),
    ('Lenovo', 'Lenovo ThinkPad X1 Carbon Gen 14 Aura Edition (2026)', 149995,
     '14in 2.8K OLED, Intel Core Ultra X7 Series 3, 32GB/1TB, 58Wh, 0.98kg'),
    ('Lenovo', 'Lenovo ThinkPad X1 Yoga Gen 5 (2020)', 84995,
     '14in FHD touch 360, Intel Core i7-10510U, 16GB/512GB, 51Wh, 1.36kg'),
    ('Lenovo', 'Lenovo ThinkPad X1 Yoga Gen 6 (2021)', 94995,
     '14in WUXGA touch 360, Intel Core i7-1165G7, 16GB/512GB, 57Wh, 1.4kg'),
    ('Lenovo', 'Lenovo ThinkPad X1 Yoga Gen 7 (2022)', 104995,
     '14in WUXGA touch 360, Intel Core i7-1260P, 16GB/512GB, 57Wh, 1.38kg'),
    ('Lenovo', 'Lenovo ThinkPad X1 Yoga Gen 8 (2023)', 114995,
     '14in 2.8K OLED touch 360, Intel Core i7-1365U, 16GB/512GB, 57Wh'),
    ('Lenovo', 'Lenovo ThinkPad X1 2-in-1 Gen 9 (2024)', 124995,
     '14in 2.8K OLED touch 360, Intel Core Ultra 7 155U, 32GB/1TB, 57Wh'),
    ('Lenovo', 'Lenovo ThinkPad X1 2-in-1 Gen 11 Aura Edition (2026)', 159995,
     '14in 2.8K OLED touch 360, Intel Core Ultra X7 Series 3, 32GB/1TB, 58Wh'),
    ('Lenovo', 'Lenovo ThinkPad T14 Gen 1 (2020)', 64995,
     '14in FHD, Intel Core i7-10510U, 16GB/512GB, 50Wh, 1.55kg'),
    ('Lenovo', 'Lenovo ThinkPad T14 Gen 2 (2021)', 69995,
     '14in FHD, Intel Core i7-1165G7, 16GB/512GB, 50Wh, 1.55kg'),
    ('Lenovo', 'Lenovo ThinkPad T14 Gen 3 (2022)', 74995,
     '14in WUXGA, Intel Core i7-1260P, 16GB/512GB, 52.5Wh, 1.21kg'),
    ('Lenovo', 'Lenovo ThinkPad T14 Gen 4 (2023)', 79995,
     '14in WUXGA, Intel Core i7-1355U, 16GB/512GB, 52.5Wh, 1.21kg'),
    ('Lenovo', 'Lenovo ThinkPad T14 Gen 6 (2025)', 89995,
     '14in WUXGA, Intel Core Ultra 7 255U, 16GB/512GB, 52.5Wh, 1.3kg'),
    ('Lenovo', 'Lenovo ThinkPad T14 Gen 7 (2026)', 99995,
     '14in 2.8K OLED, Intel Core Ultra 7 Series 3, 32GB/1TB, 58Wh, 1.27kg'),
    ('Lenovo', 'Lenovo ThinkPad E14 Gen 4 (2022)', 49995,
     '14in FHD, Intel Core i5-1235U, 8GB/512GB, 45Wh, 1.59kg'),
    ('Lenovo', 'Lenovo ThinkPad E14 Gen 5 (2023)', 54995,
     '14in WUXGA, Intel Core i5-1335U, 16GB/512GB, 45Wh, 1.59kg'),
    ('Lenovo', 'Lenovo ThinkBook 14 G2 (2020)', 39995,
     '14in FHD, Intel Core i5-1035G1, 8GB/512GB, 45Wh, 1.4kg'),
    ('Lenovo', 'Lenovo ThinkBook 14 G4 (2022)', 49995,
     '14in FHD+, Intel Core i5-1240P, 16GB/512GB, 45Wh, 1.4kg'),
    ('Lenovo', 'Lenovo ThinkBook 14 G6 (2024)', 59995,
     '14in 2.8K, Intel Core Ultra 5 125U, 16GB/512GB, 45Wh, 1.4kg'),
    ('Lenovo', 'Lenovo ThinkBook 16 G9 (2026)', 74995,
     '16in 2.5K, Intel Core Ultra 7 Series 3, 16GB/1TB, 71Wh, 1.7kg'),
    ('Lenovo', 'Lenovo IdeaPad 3 15 (2020)', 29995,
     '15.6in FHD, Intel Core i3-1005G1, 8GB/256GB, 45Wh, 1.65kg'),
    ('Lenovo', 'Lenovo IdeaPad 5 15 (2020)', 34995,
     '15.6in FHD, AMD Ryzen 5 4500U, 8GB/512GB, 45Wh, 1.66kg'),
    ('Lenovo', 'Lenovo IdeaPad Slim 5 16 (2023)', 54995,
     '16in 2.5K, AMD Ryzen 5 7530U, 16GB/512GB, 56Wh, 1.7kg'),
    ('Lenovo', 'Lenovo IdeaPad Slim 3x 15 (2025)', 44995,
     '15.3in WUXGA, Snapdragon X Plus, 16GB/512GB, 57Wh, 1.5kg'),
    ('Lenovo', 'Lenovo IdeaPad Pro 5 16 (2023)', 74995,
     '16in 2.5K 120Hz, Intel Core i7-13700H, RTX 4050 6GB, 16GB/512GB, 75Wh'),
    ('Lenovo', 'Lenovo Yoga 7i 14 (2021)', 59995,
     '14in FHD touch 360, Intel Core i7-1165G7, 16GB/512GB, 61Wh, 1.4kg'),
    ('Lenovo', 'Lenovo Yoga 7i 16 (2022)', 69995,
     '16in 2.5K touch 360, Intel Core i7-1260P, 16GB/512GB, 75Wh, 2.1kg'),
    ('Lenovo', 'Lenovo Yoga 9i 14 Gen 7 (2022)', 84995,
     '14in 2.8K OLED touch 360, Intel Core i7-1260P, 16GB/512GB, 75Wh'),
    ('Lenovo', 'Lenovo Yoga 9i 14 Gen 8 (2023)', 94995,
     '14in 2.8K OLED touch 360, Intel Core i7-1360P, 16GB/512GB, 75Wh'),
    ('Lenovo', 'Lenovo Yoga 9i 14 Gen 10 (2024)', 104995,
     '14in 2.8K OLED touch 360, Intel Core Ultra 7 155H, 32GB/1TB, 75Wh'),
    ('Lenovo', 'Lenovo Yoga 9i 2-in-1 Gen 11 Aura Edition (2026)', 129995,
     '14in 2.8K OLED touch 360, Intel Core Ultra X7 Series 3, 32GB/1TB, 75Wh'),
    ('Lenovo', 'Lenovo Yoga Slim 7x 14 (2024)', 69995,
     '14in 3K OLED 120Hz, Snapdragon X Elite, 16GB/512GB, 70Wh, 1.28kg'),
    ('Lenovo', 'Lenovo Yoga Pro 9i 16 Gen 9 (2024)', 129995,
     '16in 3.2K Mini LED 165Hz, Intel Core Ultra 9 185H, RTX 4070 8GB, 32GB/1TB'),
    ('Lenovo', 'Lenovo Yoga Pro 9i 16 Gen 11 (2026)', 149995,
     '16in 3.2K Mini LED 165Hz, Intel Core Ultra 9 Series 3, RTX 5070 8GB, 32GB/1TB'),
    ('Lenovo', 'Lenovo Legion 5 15 (2020)', 69995,
     '15.6in FHD 144Hz, AMD Ryzen 7 4800H, GTX 1660 Ti 6GB, 16GB/512GB, 80Wh'),
    ('Lenovo', 'Lenovo Legion 5 Pro 16 (2021)', 89995,
     '16in QHD 165Hz, AMD Ryzen 7 5800H, RTX 3060 6GB, 16GB/512GB, 80Wh'),
    ('Lenovo', 'Lenovo Legion 5i Gen 7 (2022)', 99995,
     '15.6in QHD 165Hz, Intel Core i7-12700H, RTX 3060 6GB, 16GB/512GB, 80Wh'),
    ('Lenovo', 'Lenovo Legion Pro 5i Gen 10 (2025)', 119995,
     '16in QHD+ 240Hz, Intel Core Ultra 9 275HX, RTX 5060 8GB, 32GB/1TB, 84Wh'),
    ('Lenovo', 'Lenovo Legion Pro 5i Gen 8 (2023)', 119995,
     '16in QHD+ 240Hz, Intel Core i7-13700HX, RTX 4060 8GB, 16GB/1TB, 80Wh'),
    ('Lenovo', 'Lenovo Legion Pro 5i Gen 9 (2024)', 129995,
     '16in QHD+ 240Hz, Intel Core i9-14900HX, RTX 4070 8GB, 32GB/1TB, 80Wh'),
    ('Lenovo', 'Lenovo Legion Slim 5 Gen 8 (2023)', 99995,
     '16in QHD+ 165Hz, Intel Core i7-13700H, RTX 4060 8GB, 16GB/512GB, 80Wh'),
    ('Lenovo', 'Lenovo Legion Pro 7i Gen 9 (2024)', 169995,
     '16in 3.2K 165Hz, Intel Core i9-14900HX, RTX 4080 12GB, 32GB/1TB, 99.9Wh'),
    ('Lenovo', 'Lenovo Legion 9i Gen 8 (2023)', 199995,
     '16in 3.2K Mini LED 165Hz, Intel Core i9-13980HX, RTX 4090 16GB, 32GB/2TB, 99.9Wh'),
    ('Lenovo', 'Lenovo ThinkPad X9-14 Gen 1 (2025)', 119995,
     '14in 2.8K OLED, Intel Core Ultra 7 258V, 32GB/1TB, 64Wh, 1.2kg'),
    ('Lenovo', 'Lenovo ThinkPad X9-15 Gen 1 (2025)', 129995,
     '15.3in 2.8K OLED, Intel Core Ultra 7 258V, 32GB/1TB, 80Wh, 1.5kg'),
    ('Lenovo', 'Lenovo ThinkPad X9 15p (2026)', 139995,
     '15.3in 2.8K OLED, Intel Core Ultra X7 Series 3, 32GB/1TB, 80Wh, 1.5kg'),
    ('Lenovo', 'Lenovo ThinkPad X13 Gen 7 (2026)', 99995,
     '13.3in WUXGA, Intel Core Ultra 7 Series 3, 32GB/1TB, 54.7Wh, 0.98kg'),
    ('Lenovo', 'Lenovo ThinkPad T14s Gen 7 (2026)', 109995,
     '14in 2.8K OLED, Intel Core Ultra 7 Series 3, 32GB/1TB, 58Wh, 1.07kg'),
    ('Lenovo', 'Lenovo ThinkBook 16p Gen 6 (2025)', 119995,
     '16in 3.2K 165Hz, Intel Core Ultra 9 275HX, RTX 5060 8GB, 32GB/1TB'),
    ('Lenovo', 'Lenovo ThinkBook 14 G8+ (2026)', 84995,
     '14in 2.8K OLED, Intel Core Ultra 7 Series 3, 32GB/1TB, 63Wh, 1.4kg'),
    ('Samsung', 'Samsung Galaxy Book Flex 15 (2020)', 69990,
     '15.6in QLED touch 360, Intel Core i7-1065G7, 12GB/512GB, 69.7Wh, S Pen'),
    ('Samsung', 'Samsung Galaxy Book Ion 15 (2020)', 64990,
     '15.6in QLED touch, Intel Core i7-10510U, 16GB/512GB, 69.7Wh, 1.19kg'),
    ('Samsung', 'Samsung Galaxy Book Pro 360 13 (2021)', 79990,
     '13.3in FHD AMOLED touch 360, Intel Core i7-1165G7, 16GB/512GB, 63Wh, S Pen'),
    ('Samsung', 'Samsung Galaxy Book Pro 15 (2021)', 74990,
     '15.6in FHD AMOLED, Intel Core i7-1165G7, 16GB/512GB, 68Wh, 1.05kg'),
    ('Samsung', 'Samsung Galaxy Book2 Pro 13 (2022)', 69990,
     '13.3in FHD AMOLED, Intel Core i7-1260P, 16GB/512GB, 63Wh, 0.87kg'),
    ('Samsung', 'Samsung Galaxy Book2 Pro 360 15 (2022)', 89990,
     '15.6in FHD AMOLED touch 360, Intel Core i7-1260P, 16GB/1TB, 68Wh, S Pen'),
    ('Samsung', 'Samsung Galaxy Book3 Pro 14 (2023)', 79990,
     '14in 3K AMOLED 120Hz, Intel Core i7-1360P, 16GB/512GB, 63Wh, 1.17kg'),
    ('Samsung', 'Samsung Galaxy Book3 Pro 360 16 (2023)', 99990,
     '16in 3K AMOLED touch 360, Intel Core i7-1360P, 16GB/1TB, 76Wh, S Pen'),
    ('Samsung', 'Samsung Galaxy Book3 Ultra 16 (2023)', 149990,
     '16in 3K AMOLED 120Hz, Intel Core i9-13900H, RTX 4070 8GB, 32GB/1TB, 76Wh'),
    ('Samsung', 'Samsung Galaxy Book4 Pro 14 (2024)', 89990,
     '14in 3K AMOLED touch 120Hz, Intel Core Ultra 7 155H, 16GB/512GB, 63Wh'),
    ('Samsung', 'Samsung Galaxy Book4 Pro 360 16 (2024)', 109990,
     '16in 3K AMOLED touch 360, Intel Core Ultra 7 155H, 16GB/1TB, 76Wh, S Pen'),
    ('Samsung', 'Samsung Galaxy Book4 Ultra 16 (2024)', 159990,
     '16in 3K AMOLED 120Hz, Intel Core Ultra 9 185H, RTX 4070 8GB, 32GB/1TB, 76Wh'),
    ('Samsung', 'Samsung Galaxy Book5 Pro 360 16 (2025)', 119990,
     '16in 3K AMOLED touch 360, Intel Core Ultra 7 258V, 32GB/1TB, 76Wh, S Pen'),
    ('Samsung', 'Samsung Galaxy Book6 Pro 14 (2026)', 99990,
     '14in 3K AMOLED 120Hz, Intel Core Ultra 7 Series 3, 32GB/1TB, 63Wh, 1.2kg'),
    ('Samsung', 'Samsung Galaxy Book6 Ultra 16 (2026)', 179990,
     '16in 3K AMOLED 120Hz, Intel Core Ultra 9 Series 3, RTX 5070 8GB, 32GB/1TB, 76Wh'),
    ('Samsung', 'Samsung Galaxy Book6 14 (2026)', 69990,
     '14in WUXGA, Intel Core 5, 16GB/512GB, 61Wh, 1.35kg'),
    ('Samsung', 'Samsung Galaxy Book6 Pro 360 16 (2026)', 129990,
     '16in 3K AMOLED touch 360, Intel Core Ultra 7 Series 3, 32GB/1TB, 76Wh, S Pen'),
]


def _description(name, specs):
    return '%s with %s.' % (name, specs)


class Command(BaseCommand):
    help = 'Add curated 2020-2026 laptops for Apple, ASUS, Dell, HP, Lenovo, Samsung and RedMagic.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Report what would change without writing to the database.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        seen = set()
        for brand, name, price, specs in LAPTOPS:
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
            laptop_category = Category.objects.filter(name='Laptops').first()
            phone_category = Category.objects.filter(name='Smartphones').first()
        else:
            laptop_category = get_category(
                'Laptops', 'Portable notebook computers for work, school, and gaming.'
            )
            phone_category = get_category(
                'Smartphones', 'Mobile phones and connected handheld devices.'
            )

        with transaction.atomic():
            for index, (brand, name, price, specs) in enumerate(LAPTOPS):
                canonical_brand = known_brands.get(brand.casefold(), brand)
                product = Product.objects.filter(
                    brand__iexact=canonical_brand, name__iexact=name
                ).first()
                if product:
                    existing += 1
                    if not dry_run and laptop_category and product.category_id != laptop_category.id:
                        product.category = laptop_category
                        product.save(update_fields=['category'])
                    continue

                if dry_run:
                    created += 1
                    continue

                Product.objects.create(
                    brand=canonical_brand,
                    name=name,
                    category=laptop_category,
                    description=_description(name, specs),
                    specifications=specs,
                    price=Decimal(str(price)),
                    stock_quantity=8 + (index % 7),
                )
                created += 1

            if not dry_run:
                moved = Product.objects.filter(
                    brand__iexact='Samsung', name__icontains='Galaxy A55'
                ).update(category=phone_category)

        prefix = 'dry run: ' if dry_run else ''
        self.stdout.write(self.style.SUCCESS(
            '%s%d added, %d already present, %d Samsung Galaxy A55 moved to Smartphones.'
            % (prefix, created, existing, moved)
        ))
