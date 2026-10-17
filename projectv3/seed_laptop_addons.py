"""Seed accessories + solutions for EVERY laptop product.
Run: venv\\Scripts\\python.exe manage.py shell -c "exec(open('projectv3/seed_laptop_addons.py', encoding='utf-8').read())"
Safe to re-run (get_or_create + M2M add, no duplicates).

Per laptop (77 total):
  - 1 fitted accessory (sleeve case naming the laptop) linked to it
  - links to 6 universal laptop accessories (hub/stand/cooler/mouse/chargers)
  - 2 troubleshooting solutions (rotated from a pool of 10) linked via related_product
"""
from decimal import Decimal
from apps.core.models import Category, Product, Accessory, Solution

lap = Category.objects.get(name="Laptops")
trouble = Category.objects.get(name="Troubleshooting")
cases = Category.objects.get(name="Cases & Protection")
power = Category.objects.get(name="Chargers & Cables")
periph = Category.objects.get(name="Peripherals")

laptops = list(Product.objects.filter(category=lap).order_by("id"))
print("laptops found:", len(laptops))

# ---------- 6 universal accessories, compatible with ALL laptops ----------
UNIVERSALS = [
    dict(name="TechFix USB-C 6-in-1 Hub (HDMI+USB+SD+PD)", category=periph,
         brand="TechFix", description="One-cable docking: 4K HDMI, 3x USB-A, SD/microSD, 100W pass-through charging.",
         price=Decimal("1990.00"), compatibility_notes="Works with any laptop with a full-function USB-C port.",
         stock_quantity=60),
    dict(name="TechFix Aluminum Laptop Stand (Foldable)", category=periph,
         brand="TechFix", description="Ergonomic foldable stand, 6 height levels, holds up to 17in laptops.",
         price=Decimal("1490.00"), compatibility_notes="Fits 11-17in laptops of any brand.",
         stock_quantity=60),
    dict(name="TechFix Laptop Cooling Pad 15.6in (5-Fan, RGB)", category=periph,
         brand="TechFix", description="5-fan cooling pad with adjustable height and quiet 1000RPM fans.",
         price=Decimal("1290.00"), compatibility_notes="Fits 12-17in laptops; ideal for gaming and editing workloads.",
         stock_quantity=50),
    dict(name="TechFix Wireless Silent Mouse 2.4G+BT", category=periph,
         brand="TechFix", description="Silent-click wireless mouse, Bluetooth + 2.4G receiver, 18-month battery.",
         price=Decimal("890.00"), compatibility_notes="Pairs with any laptop via Bluetooth or USB receiver.",
         stock_quantity=80),
    dict(name="TechFix 65W GaN Charger + 100W USB-C Cable", category=power,
         brand="TechFix", description="Compact 65W GaN fast charger with 1.8m 100W USB-C cable included.",
         price=Decimal("1590.00"), compatibility_notes="Charges any USB-C laptop up to 65W (ultrabooks, school laptops).",
         stock_quantity=70),
    dict(name="TechFix 100W GaN Charger (Gaming Laptops)", category=power,
         brand="TechFix", description="100W 3-port GaN charger for power-hungry laptops and phones.",
         price=Decimal("2490.00"), compatibility_notes="For gaming/creator laptops needing 90-100W USB-C charging.",
         stock_quantity=40),
]

uni_objs = []
for u in UNIVERSALS:
    obj, _ = Accessory.objects.get_or_create(
        brand=u["brand"], name=u["name"], defaults={**u},
    )
    uni_objs.append(obj)

# ---------- pool of 10 common laptop issues (rotated per laptop) ----------
ISSUES = [
    ("Laptop won't turn on", "Pressing power does nothing; no lights or fan spin.",
     "Step 1: Hold power 15s to force-drain. Step 2: Unplug all USB devices and charger. "
     "Step 3: Plug the original charger, wait 10 mins, try again. Step 4: Reseat battery if removable. "
     "Step 5: Try a known-good charger. Step 6: Bring to service if still dead (possible board issue).",
     "Easy"),
    ("Battery drains too fast", "Battery drops quickly even on light use.",
     "Step 1: Lower brightness to 50% and enable Battery Saver. Step 2: Check battery usage in Settings, "
     "close background hogs. Step 3: Update BIOS and drivers. Step 4: Generate battery report "
     "(powercfg /batteryreport) and check wear. Step 5: Replace battery if wear exceeds 30%.",
     "Easy"),
    ("Laptop overheats / fan very loud", "Hot chassis, loud fans, sudden slowdowns or shutdowns.",
     "Step 1: Use on a hard flat surface (not bed/pillow). Step 2: Clean vents with compressed air. "
     "Step 3: Check Task Manager for runaway processes. Step 4: Use a cooling pad. "
     "Step 5: Re-paste CPU/GPU and replace thermal pads if temps stay above 95C (service center).",
     "Medium"),
    ("WiFi keeps disconnecting", "WiFi drops randomly while other devices stay connected.",
     "Step 1: Forget the network and reconnect. Step 2: Update the WiFi driver from the maker site. "
     "Step 3: In Device Manager, disable 'allow computer to turn off this device' for the WiFi adapter. "
     "Step 4: Switch between 2.4GHz and 5GHz bands. Step 5: Reset network stack (netsh winsock reset).",
     "Easy"),
    ("Very slow boot / Windows sluggish", "Takes minutes to boot; apps lag and freeze.",
     "Step 1: Disable unnecessary Startup apps in Task Manager. Step 2: Free disk space (min 15% free). "
     "Step 3: Run antivirus/malware scan. Step 4: Upgrade to SSD and add RAM if still on HDD/4GB. "
     "Step 5: Reinstall Windows as a last resort after backup.",
     "Medium"),
    ("Screen flickering", "Display flickers, flashes, or shows lines.",
     "Step 1: Update display and GPU drivers. Step 2: Test with an external monitor to isolate panel vs GPU. "
     "Step 3: Change refresh rate to the panel default (60/120/144Hz). Step 4: Check the display cable "
     "if flicker changes with lid angle. Step 5: Replace panel/cable at service if hardware-side.",
     "Medium"),
    ("Some keyboard keys not working", "Certain keys type nothing or repeat characters.",
     "Step 1: Blow out debris with compressed air, shake gently upside down. Step 2: Test with an external "
     "keyboard. Step 3: Update/reinstall keyboard driver. Step 4: Check for sticky-keys or filter-keys "
     "settings. Step 5: Replace keyboard module if a row/column is dead.",
     "Easy"),
    ("No sound from speakers", "Videos play but no audio from built-in speakers.",
     "Step 1: Check volume mixer and that the right output is selected. Step 2: Unplug HDMI/Bluetooth "
     "devices that may hijack audio. Step 3: Reinstall audio driver from maker site. Step 4: Run the "
     "built-in audio troubleshooter. Step 5: Test with earphones to isolate speaker hardware.",
     "Easy"),
    ("Blue screen / random crashes", "BSOD errors or sudden restarts under load.",
     "Step 1: Note the stop code and failing driver file. Step 2: Update GPU/chipset drivers and Windows. "
     "Step 3: Run memory test (mdsched) and disk check (chkdsk). Step 4: Stress-test thermals; overheating "
     "causes crashes. Step 5: Back up data and reinstall OS; service board/RAM if it persists.",
     "Hard"),
    ("Touchpad not responding", "Cursor frozen or touchpad gestures dead.",
     "Step 1: Press the touchpad toggle key (Fn+F-key). Step 2: Check Settings > Bluetooth & devices > "
     "Touchpad is enabled. Step 3: Reinstall precision touchpad driver. Step 4: Test in BIOS to rule out "
     "software. Step 5: Reseat/replace the touchpad ribbon cable at service.",
     "Easy"),
]

acc_new = sol_new = 0
for i, laptop in enumerate(laptops):
    # 1) fitted sleeve accessory for this exact laptop
    sleeve_name = f"Laptop Sleeve Case for {laptop.name}"
    sleeve, made = Accessory.objects.get_or_create(
        brand=laptop.brand or "TechFix", name=sleeve_name,
        defaults=dict(
            category=cases,
            description=f"Padded water-resistant sleeve tailored for the {laptop.name}.",
            price=Decimal("690.00"),
            compatibility_notes=f"Custom fit for {laptop.name}; extra pocket for charger and mouse.",
            stock_quantity=20,
        ),
    )
    if made:
        acc_new += 1
    sleeve.compatible_products.add(laptop)
    # 2) link all universals
    for u in uni_objs:
        u.compatible_products.add(laptop)

    # 3) two rotated solutions
    for k in (0, 1):
        title, prob, steps, diff = ISSUES[(i * 2 + k) % len(ISSUES)]
        full_title = f"{title} — {laptop.name}"
        _, made = Solution.objects.get_or_create(
            title=full_title, related_product=laptop,
            defaults=dict(
                problem_description=f"[{laptop.brand} {laptop.name}] {prob}",
                steps=steps, difficulty_level=diff,
                category=trouble, video_url="",
            ),
        )
        if made:
            sol_new += 1

print(f"done: {acc_new} fitted accessories created, {sol_new} solutions created")
print("accessory count:", Accessory.objects.count())
print("solution count:", Solution.objects.count())
# verify every laptop has >=1 accessory and >=1 solution
bare_acc = [p.name for p in laptops if p.compatible_accessories.count() == 0]
bare_sol = [p.name for p in laptops if p.solutions.count() == 0]
print("laptops with 0 accessories:", len(bare_acc), bare_acc[:5])
print("laptops with 0 solutions:", len(bare_sol), bare_sol[:5])
