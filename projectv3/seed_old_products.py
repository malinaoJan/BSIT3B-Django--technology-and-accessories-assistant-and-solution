"""Seed OLD (legacy / discontinued) products, accessories and repair solutions
for every brand already present in the TechFix catalog.

For each of the 34 brands this adds:
  * 10 classic / end-of-life products
  *  3 old accessories (linked to the matching old products)
  *  1 repair solution per old product (340 solutions total)

Run from the TECHFIX project root:
    venv\\Scripts\\python.exe manage.py shell -c "exec(open('projectv3/seed_old_products.py', encoding='utf-8').read())"

Safe to re-run (uses get_or_create on brand+name / accessory name / solution title).
"""
import os
import sys
from decimal import Decimal

from apps.core.models import Accessory, Category, Product, Solution

_here = os.path.dirname(os.path.abspath(__import__("apps").__file__))
_root = os.path.dirname(_here)
if _root not in sys.path:
    sys.path.insert(0, _root)

from old_accessories_data import OLD_ACCESSORIES  # noqa: E402
from old_products_data import OLD_PRODUCTS  # noqa: E402

# ---------------------------------------------------------------------------
# repair guide pools: one issue per old product, rotating by category
# each entry = (title tail, problem, steps, difficulty)
# ---------------------------------------------------------------------------

ISSUES = {
    "Smartphones": [
        ("Battery drains quickly",
         "The {name} loses its charge within a few hours of light use and shuts down unexpectedly below 20%.",
         "1. Open Settings > Battery and check which apps use the most power.\n"
         "2. Lower screen brightness and disable location services for unused apps.\n"
         "3. Boot to Recovery mode and wipe the cache partition.\n"
         "4. If battery health is under 80%, replace the cell - old batteries need service.",
         "Easy"),
        ("Stuck on the boot logo / restart loop",
         "The {name} freezes on the brand logo or keeps rebooting and never reaches the home screen.",
         "1. Force restart by holding Power + Volume Down for 10 seconds.\n"
         "2. Boot into Recovery mode and wipe the cache partition.\n"
         "3. Back up what you can, then do a factory reset.\n"
         "4. If the loop returns, reflash the firmware with the brand desktop tool.",
         "Hard"),
        ("Touchscreen dead zones",
         "Parts of the {name} screen ignore taps or respond late, usually after a drop or moisture exposure.",
         "1. Remove the screen protector and case, then clean the glass.\n"
         "2. Restart the phone and test again.\n"
         "3. Boot into Safe Mode to rule out a rogue app.\n"
         "4. Run the hardware test code; if it fails, replace the display assembly.",
         "Medium"),
        ("Overheating while charging",
         "The {name} gets very hot during charging or camera use and slows down.",
         "1. Use only the original charger and cable.\n"
         "2. Remove the case while charging and keep it out of direct sun.\n"
         "3. Close background apps and install the latest software update.\n"
         "4. Persistent heat means the charging board or battery needs checking.",
         "Easy"),
    ],
    "Laptops": [
        ("Not charging / no power light",
         "The {name} shows no charging LED and does not power on with the adapter connected.",
         "1. Test the adapter on another laptop and check the pin for damage.\n"
         "2. Unplug the battery, hold Power for 30 seconds, then reconnect everything.\n"
         "3. Try a different wall outlet and inspect the DC jack for looseness.\n"
         "4. A loose jack or dead board needs a technician repair.",
         "Medium"),
        ("Fan noise and overheating",
         "The {name} runs loud, gets hot near the vents and throttles under load.",
         "1. Clear the vents with compressed air and never block them on a bed or pillow.\n"
         "2. Use a cooling pad and raise the rear of the laptop.\n"
         "3. Open the base and replace the dried thermal paste.\n"
         "4. Replace the fan if the bearing rattles.",
         "Medium"),
        ("Extremely slow boot and apps",
         "The {name} takes many minutes to boot and applications hang constantly.",
         "1. Run Disk Cleanup and remove startup programs you do not need.\n"
         "2. Check Task Manager for a drive stuck at 100 percent use.\n"
         "3. Scan for malware with up-to-date antivirus software.\n"
         "4. The biggest fix on older laptops is swapping the HDD for an SSD.",
         "Easy"),
        ("Keyboard or trackpad not responding",
         "Some keys on the {name} stop working or the cursor jumps without input.",
         "1. Clean between the keys with compressed air.\n"
         "2. Reinstall or update the touchpad and chipset drivers.\n"
         "3. Plug in an external keyboard to see if the fault is hardware.\n"
         "4. Replace the keyboard assembly if keys stay dead.",
         "Medium"),
    ],
    "Tablets": [
        ("Will not charge past 1%",
         "The {name} plugs in but the battery icon stays at 0-1 percent or shows a charging error.",
         "1. Clean the charging port with a wooden pick and compressed air.\n"
         "2. Try a different cable and at least a 2A adapter.\n"
         "3. Leave it connected to power for 30 minutes before trying to boot.\n"
         "4. An inflated or dead battery must be replaced professionally.",
         "Medium"),
        ("Touchscreen not responding",
         "Taps and swipes on the {name} are ignored, mostly after a fall.",
         "1. Force restart and hold Power + Home for 15 seconds.\n"
         "2. Remove any screen protector that may be lifting.\n"
         "3. Test the screen in Safe Mode.\n"
         "4. Replace the digitiser if dead zones remain.",
         "Medium"),
        ("Wi-Fi keeps disconnecting",
         "The {name} drops the Wi-Fi connection while other devices stay online.",
         "1. Forget the network, reboot the router and reconnect.\n"
         "2. Set the router channel manually to 1, 6 or 11.\n"
         "3. Reset network settings on the tablet.\n"
         "4. Install system updates - many old tablets shipped with buggy Wi-Fi firmware.",
         "Easy"),
    ],
    "Wearables": [
        ("Will not pair with the phone",
         "The {name} cannot be found in Bluetooth settings or pairing always fails.",
         "1. Turn Bluetooth off and on again on the phone, then restart the watch.\n"
         "2. Forget the device and delete its app data, then pair from scratch.\n"
         "3. Update the companion app and the watch firmware.\n"
         "4. Factory reset the watch if it still will not connect.",
         "Easy"),
        ("Battery no longer holds a charge",
         "The {name} runs for less than a few hours and dies before the end of the day.",
         "1. Reduce screen brightness and disable always-on display.\n"
         "2. Turn off 24/7 heart rate monitoring and GPS when unused.\n"
         "3. Clean the charging pins and reseat it on the dock.\n"
         "4. Batteries age - replace the unit or cell if capacity is below 60%.",
         "Easy"),
        ("Charger not recognised",
         "The {name} does not light up or charge on its original dock.",
         "1. Clean the magnetic contacts and pins with a dry cloth.\n"
         "2. Try a different USB cable and a phone charger, not a laptop port.\n"
         "3. Reset the watch while it is on the charger.\n"
         "4. Replace the dock if the cable tests fine elsewhere.",
         "Medium"),
    ],
    "Desktops": [
        ("Powers on but no display",
         "The {name} fans spin and lights come on, but the monitor stays black.",
         "1. Reseat the RAM and the graphics card.\n"
         "2. Try a different video cable and input on the monitor.\n"
         "3. Clear CMOS by removing the battery for five minutes.\n"
         "4. Listen for beep codes - they identify the failed component.",
         "Medium"),
        ("Blue screen or boot loop",
         "The {name} crashes with a stop error or repairs itself in a loop at startup.",
         "1. Boot from installation media and run startup repair.\n"
         "2. Open the command prompt and run chkdsk /f /r.\n"
         "3. Test the RAM with the Windows memory diagnostic.\n"
         "4. Back up data and reinstall Windows if the drive is failing.",
         "Hard"),
        ("Extremely slow performance",
         "The {name} has become unusably slow even for browsing documents.",
         "1. Remove startup programs and run a malware scan.\n"
         "2. Check disk health in Task Manager > Performance.\n"
         "3. Add more RAM and replace the hard drive with an SSD.\n"
         "4. Back up data, then do a clean OS reinstall.",
         "Easy"),
        ("Loud fan and random shutdowns",
         "The {name} roars under load and powers off without warning.",
         "1. Dust the filters, fans and heatsinks with compressed air.\n"
         "2. Reapply thermal paste on the CPU and GPU.\n"
         "3. Monitor temperatures with hardware monitoring software.\n"
         "4. Replace the PSU if voltages are unstable.",
         "Medium"),
    ],
    "Smart TVs": [
        ("Sound but no picture",
         "The {name} plays audio but the screen stays black or very dim.",
         "1. Cover the room - an image may be visible, pointing to backlight failure.\n"
         "2. Reseat the HDMI cable and switch to another input.\n"
         "3. Unplug the TV for 60 seconds, then power it on again.\n"
         "4. A dead backlight strip needs a technician repair.",
         "Medium"),
        ("Apps freeze or crash",
         "Apps on the {name} hang, crash back to the home screen or never load.",
         "1. Clear the app cache and data from settings.\n"
         "2. Uninstall and reinstall the failing app.\n"
         "3. Update the TV firmware from Settings > Support.\n"
         "4. As a last resort, reset the TV to factory settings.",
         "Easy"),
        ("Cannot connect to Wi-Fi",
         "The {name} will not see or join the home wireless network.",
         "1. Restart the router and move it closer to the TV.\n"
         "2. Forget the network on the TV and re-enter the password.\n"
         "3. Set the router to 2.4GHz - many older TVs do not see 5GHz.\n"
         "4. Reset network settings on the TV if the password is correct.",
         "Easy"),
        ("No signal on HDMI",
         "Switching to the console or stick on the {name} shows no signal.",
         "1. Reseat the HDMI cable at both ends and use another HDMI port.\n"
         "2. Turn off the source device, plug it in, then switch the TV input first.\n"
         "3. Disable CEC/Anynet and test again.\n"
         "4. Try a known-good cable to rule out a dead port.",
         "Easy"),
    ],
    "Cameras": [
        ("Photos come out blurry",
         "Every shot from the {name} is soft or smeared, even in good light.",
         "1. Clean the front element with a lens cloth.\n"
         "2. Switch the focus mode and use a single centre focus point.\n"
         "3. Check the shutter speed and raise ISO if it is too slow to hand-hold.\n"
         "4. A misaligned or jammed lens assembly needs service.",
         "Easy"),
        ("Will not power on",
         "The {name} is completely dead with batteries or the pack fitted.",
         "1. Test the batteries in another device or use a fresh set.\n"
         "2. Clean the battery contacts with a dry cloth.\n"
         "3. Remove the battery for five minutes, reinsert and try again.\n"
         "4. Check the power board if the camera stays dead.",
         "Easy"),
        ("Memory card not recognised",
         "The {name} reports no card, cannot format or refuses to save images.",
         "1. Try another card - older cameras cap out at 32GB and Class 10.\n"
         "2. Slide the card lock switch to unlocked.\n"
         "3. Format the card inside the camera, not on a computer.\n"
         "4. Clean the card pins in the slot.",
         "Easy"),
        ("Stuck shutter or ERR message",
         "The {name} shows an error code or the shutter stops responding.",
         "1. Remove and reinsert the battery to clear the error.\n"
         "2. Switch to an empty lens mount and test the body.\n"
         "3. Do not force the lens - power down and start again.\n"
         "4. Shutter mechanisms need a technician after very high shot counts.",
         "Hard"),
    ],
    "Printers": [
        ("Paper keeps jamming",
         "Every job on the {name} jams or pulls in multiple sheets at once.",
         "1. Remove the paper, fan the stack and reload below the tray limit.\n"
         "2. Pull out all sheets and check the tray for torn paper fragments.\n"
         "3. Clean the rubber pickup roller with a damp cloth.\n"
         "4. Adjust the paper guides firmly against the stack.",
         "Easy"),
        ("Prints are faded or streaked",
         "Output from the {name} has grey text, white bands or missing colours.",
         "1. Run the built-in nozzle check / print quality report.\n"
         "2. Run the head cleaning cycle up to three times from the driver.\n"
         "3. Replace low or dried-out cartridges.\n"
         "4. On ink tank models, shake the bottle and refill the empty tank.",
         "Easy"),
        ("Will not connect to Wi-Fi",
         "The {name} drops off the network or will not join it at all.",
         "1. Print a network configuration page and check the signal.\n"
         "2. Reconnect from the printer panel using WPS or the Wi-Fi Setup menu.\n"
         "3. Keep the printer within range of the router on 2.4GHz.\n"
         "4. Reinstall the driver and print a test page from the PC.",
         "Medium"),
        ("Streaks after a new cartridge",
         "Printouts from the {name} show bands right after a cartridge change.",
         "1. Remove the cartridge and peel off the orange protective tape.\n"
         "2. Wipe the electrical contacts with a dry lint-free cloth.\n"
         "3. Reseat the cartridge until it clicks and run cleaning twice.\n"
         "4. Align the print head from the printer software.",
         "Easy"),
    ],
    "Networking": [
        ("No internet but Wi-Fi is connected",
         "Devices join the {name} network but pages will not load.",
         "1. Restart the modem and the router in that order.\n"
         "2. Check that the WAN cable is plugged into the correct port.\n"
         "3. Release and renew the IP address on the affected device.\n"
         "4. Reset the router to factory defaults if the modem line is fine.",
         "Easy"),
        ("Very slow or weak signal",
         "The {name} coverage is poor and speed drops in other rooms.",
         "1. Move the router to a central, elevated position away from walls.\n"
         "2. Switch to a clear channel - use 1, 6 or 11 on 2.4GHz.\n"
         "3. Remove old cordless phone and microwave interference.\n"
         "4. Add a range extender or mesh node for distant rooms.",
         "Easy"),
        ("Cannot open the admin page",
         "Browsing to the {name} setup address times out or asks for a wrong password.",
         "1. Connect by cable or to the default SSID first.\n"
         "2. Try the default IP printed on the router label, not a website name.\n"
         "3. Disable VPN and proxy settings, then clear the browser cache.\n"
         "4. Hold reset for 10 seconds to restore factory settings.",
         "Medium"),
        ("Keeps dropping connection",
         "The {name} randomly disconnects every few minutes across all devices.",
         "1. Update the router firmware from the admin page.\n"
         "2. Reduce the number of connected devices and disable unused bands.\n"
         "3. Change the Wi-Fi channel and set a fixed 2.4GHz channel width.\n"
         "4. Replace the unit if it restarts on its own - that signals a power fault.",
         "Medium"),
    ],
    "Audio": [
        ("Sound only in one ear",
         "One side of the {name} is silent or cuts in and out when the cable moves.",
         "1. Clean the driver mesh and ear tips of wax and debris.\n"
         "2. Test another device to confirm the fault follows the earbuds.\n"
         "3. On wired models, bend the cable near the jack - a drop means a broken wire.\n"
         "4. For true wireless, put both buds in the case and reset them.",
         "Easy"),
        ("Will not hold a charge",
         "The {name} dies within minutes even after a full charge cycle.",
         "1. Clean the charging contacts with a dry cotton swab.\n"
         "2. Leave it on charge for 30 minutes before use and use a 5V adapter.\n"
         "3. Update the firmware from the companion app.\n"
         "4. Old cells fade - battery replacement or a new unit is the fix.",
         "Easy"),
        ("Pairing fails or drops",
         "The {name} disappears from the device list or will not complete pairing.",
         "1. Forget the device on the phone, then restart both devices.\n"
         "2. Clear the pairing list on the headphones and pair again.\n"
         "3. Move away from Wi-Fi routers and USB 3.0 hubs that cause interference.\n"
         "4. Update the app and firmware to the latest version.",
         "Easy"),
        ("Distortion at higher volume",
         "The {name} crackles or sounds muffled when the volume goes up.",
         "1. Lower the source volume and disable any equaliser boosts.\n"
         "2. Clean the speaker grille and check for a torn driver surround.\n"
         "3. Test on a second device to confirm it is not the source.\n"
         "4. A blown driver needs replacement.",
         "Medium"),
    ],
    "Monitors": [
        ("Monitor stays black",
         "The {name} powers on with an LED but shows no picture at all.",
         "1. Press the input/source button to select the correct input.\n"
         "2. Reseat the video cable at both ends and try another cable.\n"
         "3. Test the monitor on another PC or plug in a different display.\n"
         "4. A dead power board or backlight needs repair.",
         "Medium"),
        ("Flickering or unstable image",
         "The {name} blinks, shows horizontal lines or loses sync randomly.",
         "1. Swap in a known-good cable - cheap HDMI leads cause most flicker.\n"
         "2. Lower the refresh rate to 60Hz and disable adaptive sync.\n"
         "3. Update the graphics driver and remove overclocked display modes.\n"
         "4. Persistent flicker with a new cable means the panel is failing.",
         "Medium"),
        ("Picture looks blurry",
         "Text and images on the {name} are soft or pixelated.",
         "1. Set the resolution to the panel's native Full HD value.\n"
         "2. Raise the refresh rate to 60Hz or higher in display settings.\n"
         "3. Use a digital cable instead of VGA where possible.\n"
         "4. On old monitors, degauss and reset the picture defaults.",
         "Easy"),
        ("No signal message",
         "The {name} shows no signal when the computer starts.",
         "1. Turn the PC on after the monitor, so it detects the input.\n"
         "2. Try another cable and another port on the graphics card.\n"
         "3. Clear CMOS if the PC only outputs from the wrong socket.\n"
         "4. Test the monitor on another computer to isolate the fault.",
         "Easy"),
    ],
    "Peripherals": [
        ("Device not detected",
         "The {name} does not show up on the computer at all.",
         "1. Plug it into another USB port, avoiding hubs and pass-throughs.\n"
         "2. Test it on a second computer.\n"
         "3. Reinstall the driver from Device Manager > Uninstall device.\n"
         "4. Replace the cable if it is detachable.",
         "Easy"),
        ("Double clicks on a single press",
         "The {name} registers two clicks or scrolls the wrong way.",
         "1. Clean around the buttons and the scroll wheel with compressed air.\n"
         "2. Test in another application to confirm it is hardware.\n"
         "3. Toggle single or double click speed in mouse settings.\n"
         "4. Replace the microswitches or the unit if cleaning fails.",
         "Medium"),
        ("Lag, ghosting or stutter",
         "The {name} hesitates, jumps or stops responding for a moment.",
         "1. Use the direct port on the back of the PC, not the front panel.\n"
         "2. Remove old drivers and install the latest one.\n"
         "3. Disconnect other USB devices, especially USB 3.0 hard drives.\n"
         "4. Replace the cable or battery if the device is wireless.",
         "Easy"),
        ("Keys or buttons not responding",
         "Some keys on the {name} need repeated presses or never register.",
         "1. Clean under the keycaps with compressed air.\n"
         "2. Try the device on another computer.\n"
         "3. Disable sticky keys and filter keys in accessibility settings.\n"
         "4. Replace the key switch or membrane sheet if cleaning fails.",
         "Medium"),
    ],
    "Chargers & Cables": [
        ("Charging very slowly or not at all",
         "The {name} charges devices far slower than rated or not at all.",
         "1. Use a wall outlet, not a laptop USB port.\n"
         "2. Clean lint and dust from the device's charging port.\n"
         "3. Try a known-good cable to confirm which side is at fault.\n"
         "4. Stop using the charger if it is hot, swollen or smells burnt.",
         "Easy"),
        ("Device not recognised when connected",
         "Plugging in with the {name} gives no reaction or a 'not recognised' error.",
         "1. Reseat the connector - push it in fully until it clicks.\n"
         "2. Try the other direction for reversible connectors and another cable.\n"
         "3. Restart the device and test the port for bent pins or debris.\n"
         "4. Replace the cable if the port works with other leads.",
         "Easy"),
        ("Connector loose or sparking",
         "The {name} falls out of the port or crackles while charging.",
         "1. Stop using the cable - a loose connection can overheat the port.\n"
         "2. Inspect the tip for bent pins, fraying or exposed wire.\n"
         "3. Straighten a bent tip carefully or cut off a frayed end.\n"
         "4. Replace the cable or charger - do not repair it with tape.",
         "Easy"),
        ("Power bank will not charge",
         "The {name} does not accept a charge or its LEDs flash and stop.",
         "1. Hold the power button for 10 seconds to wake the circuit.\n"
         "2. Use a 2A adapter and a good cable - thin cables starve big banks.\n"
         "3. Clean the ports and let it charge uninterrupted for one hour.\n"
         "4. Deeply discharged cells may be beyond recovery and need replacing.",
         "Medium"),
    ],
    "Storage": [
        ("Card not detected",
         "The {name} is not recognised by the camera, phone or computer.",
         "1. Unlock the card's write-protect switch.\n"
         "2. Insert it fully and test in another device or reader.\n"
         "3. Reformat it in the device that will use it.\n"
         "4. If it asks to be formatted every time, the card is failing - replace it.",
         "Easy"),
        ("Files corrupted or missing",
         "Photos and documents on the {name} open as broken files or disappear.",
         "1. Stop writing to the card and copy everything off immediately.\n"
         "2. Run a file system check (chkdsk) on a computer.\n"
         "3. Use data recovery software for important files.\n"
         "4. Never reuse a card that has already corrupted once.",
         "Medium"),
        ("Very slow transfer speeds",
         "Copying from the {name} takes far longer than the rated speed.",
         "1. Use a UHS-I reader on a USB 3.0 port.\n"
         "2. Format the card in the device and keep it below 80% full.\n"
         "3. Avoid counterfeit cards - test the true capacity with h2testw.\n"
         "4. Replace the card if speeds stay low after a full format.",
         "Easy"),
    ],
    "Gaming Handhelds": [
        ("Overheating during long sessions",
         "The {name} gets hot and slows down after 20-30 minutes of play.",
         "1. Clean the vents and grilles with compressed air.\n"
         "2. Play in a cool room and avoid charging while gaming.\n"
         "3. Lower the brightness and close background downloads.\n"
         "4. Replace the drying thermal paste if heat persists.",
         "Medium"),
        ("Buttons or sticks drifting",
         "Characters move or menus jump without touching the {name} controls.",
         "1. Recalibrate the stick from the settings menu.\n"
         "2. Clean around the stick with compressed air and isopropyl alcohol.\n"
         "3. Update the firmware and test in the built-in diagnostic screen.\n"
         "4. Replace the stick module if drift remains.",
         "Medium"),
        ("Battery drains while docked",
         "The {name} loses charge even when it is plugged in or on a dock.",
         "1. Use the original adapter - third-party chargers may under-power it.\n"
         "2. Clean the port and dock contacts.\n"
         "3. Power it off completely for 30 minutes while charging.\n"
         "4. An aged battery should be replaced to restore runtime.",
         "Easy"),
        ("Will not read game cards",
         "The {name} does not detect inserted cartridges or cards.",
         "1. Power off and reseat the card until it clicks.\n"
         "2. Clean the card contacts and the slot gently.\n"
         "3. Test a second game to rule out a bad copy.\n"
         "4. A damaged slot needs professional repair.",
         "Medium"),
    ],
    "Cases & Protection": [
        ("Torn stitching or broken zipper",
         "The {name} has started to fray, the zipper sticks or the strap broke.",
         "1. Clean the fabric and brush dirt out of the zipper teeth.\n"
         "2. Lubricate the slider with a graphite pencil or candle wax.\n"
         "3. Reinforce early fraying before it turns into a full tear.\n"
         "4. Retire the item once the padding is crushed - it no longer protects.",
         "Easy"),
        ("Poor fit or blocked ports",
         "The {name} does not line up with buttons, ports or cameras.",
         "1. Confirm you have the exact model size - most cases are model-specific.\n"
         "2. Trim only the manufacturing flash inside the cut-outs.\n"
         "3. Remove thick screen protectors that push the case off the edges.\n"
         "4. Replace the case if it interferes with buttons or charging.",
         "Easy"),
        ("Cracked or clouded material",
         "The {name} has yellowed, cracked or the clear panel has gone cloudy.",
         "1. Wash with mild soap and warm water, then dry fully.\n"
         "2. Use a UV-protectant wipe to slow further yellowing.\n"
         "3. Sand out light scuffs with a microfibre cloth.\n"
         "4. A cracked case transfers impact - replace it.",
         "Easy"),
    ],
}

# ---------------------------------------------------------------------------
# categories used by the seed data
# ---------------------------------------------------------------------------

CAT_DESCRIPTIONS = {
    "Smartphones": "Mobile phones and phablets.",
    "Laptops": "Portable notebook computers for work, school, and gaming.",
    "Tablets": "Touchscreen tablets and 2-in-1 slates.",
    "Monitors": "Desktop displays and gaming monitors.",
    "Desktops": "Towers, mini PCs and all-in-one computers.",
    "Smart TVs": "Connected TVs and streaming devices.",
    "Cameras": "Digital cameras, compacts and camcorders.",
    "Printers": "Printers, all-in-ones and scanners.",
    "Networking": "Routers, switches and network gear.",
    "Audio": "Headphones, earbuds, speakers and microphones.",
    "Wearables": "Smartwatches, bands and trackers.",
    "Peripherals": "Mice, keyboards, webcams and docks.",
    "Chargers & Cables": "Adapters, power banks and cables.",
    "Cases & Protection": "Sleeves, covers and cases.",
    "Storage": "Memory cards, SSDs and drives.",
    "Gaming Handhelds": "Portable game consoles and handhelds.",
    "Troubleshooting": "Step-by-step repair and troubleshooting guides.",
}

# ---------------------------------------------------------------------------
# seed
# ---------------------------------------------------------------------------

# canonical brand casing as stored in the catalog
_known = set(Product.objects.exclude(brand="").values_list("brand", flat=True))
_known |= set(Accessory.objects.exclude(brand="").values_list("brand", flat=True))
CANON = {b.strip().lower(): b.strip() for b in _known if b and b.strip()}

created_products = 0
skipped_products = 0
created_accessories = 0
skipped_accessories = 0
created_solutions = 0
skipped_solutions = 0

category_cache = {}


def get_category(name):
    if name not in category_cache:
        cat, _ = Category.objects.get_or_create(
            name=name, defaults={"description": CAT_DESCRIPTIONS.get(name, "")}
        )
        category_cache[name] = cat
    return category_cache[name]


brand_products = {}

for key, items in OLD_PRODUCTS.items():
    brand = CANON.get(key, key)
    products = []
    for cat_name, name, description, specifications, price, stock in items:
        obj, was_created = Product.objects.get_or_create(
            brand=brand,
            name=name,
            defaults={
                "category": get_category(cat_name),
                "description": description,
                "specifications": specifications,
                "price": Decimal(str(price)),
                "stock_quantity": stock,
            },
        )
        if was_created:
            created_products += 1
        else:
            skipped_products += 1
        products.append(obj)
    brand_products[key] = products

print(f"products: {created_products} created, {skipped_products} already existed")

for key, items in OLD_ACCESSORIES.items():
    brand = CANON.get(key, key)
    products = brand_products.get(key, [])
    for cat_name, name, description, compat, price, stock, links in items:
        obj, was_created = Accessory.objects.get_or_create(
            brand=brand,
            name=name,
            defaults={
                "category": get_category(cat_name),
                "description": description,
                "compatibility_notes": compat,
                "price": Decimal(str(price)),
                "stock_quantity": stock,
            },
        )
        if was_created:
            created_accessories += 1
            for index in links:
                if 0 <= index < len(products):
                    obj.compatible_products.add(products[index])
        else:
            skipped_accessories += 1

print(f"accessories: {created_accessories} created, {skipped_accessories} already existed")

troubleshooting = get_category("Troubleshooting")
issue_cursor = {}

for key, products in brand_products.items():
    brand = CANON.get(key, key)
    for product in products:
        cat_name = product.category.name if product.category else ""
        pool = ISSUES.get(cat_name) or ISSUES["Smartphones"]
        position = issue_cursor.get(cat_name, 0)
        issue_cursor[cat_name] = position + 1
        title_tail, problem, steps, difficulty = pool[position % len(pool)]
        title = f"Fix {product.name}: {title_tail}"
        _, was_created = Solution.objects.get_or_create(
            title=title,
            defaults={
                "problem_description": problem.format(name=product.name),
                "steps": steps,
                "difficulty_level": difficulty,
                "category": troubleshooting,
                "related_product": product,
            },
        )
        if was_created:
            created_solutions += 1
        else:
            skipped_solutions += 1

print(f"solutions: {created_solutions} created, {skipped_solutions} already existed")

brands_summary = []
for key, products in brand_products.items():
    brand = CANON.get(key, key)
    accessory_count = Accessory.objects.filter(brand=brand).count()
    solution_count = Solution.objects.filter(related_product__brand=brand).count()
    brands_summary.append((brand, len(products), accessory_count, solution_count))

print(f"brands covered: {len(brands_summary)}")
print(f"totals -> products: {Product.objects.count()}, "
      f"accessories: {Accessory.objects.count()}, "
      f"solutions: {Solution.objects.count()}")
