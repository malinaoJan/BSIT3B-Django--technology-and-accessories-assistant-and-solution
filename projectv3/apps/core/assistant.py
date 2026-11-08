"""Question answering for the TechFix assistant.

The engine matches a free-text question against repair guides, products and
accessories, then returns a specific answer with numbered steps. Gemini can
enrich the result through ``apps.core.gemini``; the local answer remains the
fallback when the API is unavailable.
"""

import json
import re
import urllib.parse
import urllib.request
from functools import lru_cache

TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9\-]*")
STEP_RE = re.compile(r"(?:^|[\s\n])(?:step\s*)?(\d{1,2})[.)]\s+", re.IGNORECASE)

_STOPWORDS = frozenset("""
a an the and or but if then than so because as of to in on at by for with from
into over under about after before during while when where who whom which what
why how is are was were be been being am do does did doing done have has had
having can could should would will shall may might must i me my mine we us our
you your he him his she her it its they them their this that these those there
here not no yes nor any all some each every other another more most few many
both either neither too very really just only also even still again ever never
always sometimes now once please help someone tell know want need like get got
gets make makes made use using used try trying tried fix fixes fixed repair
repairs solution solutions troubleshoot troubleshooting problem problems issue
issues keeps keep kept starts started start stops stopped stop working works
show browse search list see good great
work anymore suddenly wrong pro max plus ultra mini lite smart wireless wired
bluetooth gen series edition new latest price cost spec specs specification
specifications feature features review reviews compare buy purchase much best
recommend recommendation
""".split())

_TOKEN_ALIASES = {
    'smartphone': 'phone',
    'smartphones': 'phone',
    'cellphone': 'phone',
    'cellphones': 'phone',
    'mobile': 'phone',
    'mobiles': 'phone',
    'notebook': 'laptop',
    'notebooks': 'laptop',
    'television': 'tv',
    'televisions': 'tv',
    'earbuds': 'earbud',
    'earphones': 'earphone',
    'headphones': 'headphone',
    'airpods': 'earbud',
    'speakers': 'speaker',
    'cameras': 'camera',
    'printers': 'printer',
    'routers': 'router',
    'tablets': 'tablet',
    'laptops': 'laptop',
    'phones': 'phone',
}

_GENERIC_TOKENS = frozenset({
    'phon', 'laptop', 'tablet', 'tv', 'camera', 'printer', 'router',
    'speaker', 'headphon', 'headset', 'earbud', 'earphon', 'monitor',
    'watch', 'console', 'devic', 'product', 'accessory', 'gadget',
    'techfix', 'charger', 'cabl', 'case', 'battery', 'keyboard', 'mous',
    'controller', 'gamepad', 'projector', 'scanner', 'storag', 'drive',
    'stand', 'dock', 'hub', 'adapter', 'adaptor', 'remote', 'screen',
    'display', 'usb', 'hdmi', 'lcd', 'led', 'hdr', 'uhd', 'fhd', 'ips',
    'nfc', 'gps', 'anc', 'rgb',
})

_MODEL_WORDS = frozenset({
    'pro', 'max', 'plus', 'ultra', 'mini', 'lite', 'air', 'fold', 'flip',
    'fe', 'se', 'xl', 'note', 'edge', 'neo', 'prime', 'titan', 'gt',
    '2nd', '3rd', '4th', '5th', '10th', '11th', '12th',
})

_DISTINCTIVE_ALIASES = frozenset({'airpods'})

_ACCESSORY_QUERY_WORDS = frozenset({
    'case', 'cover', 'sleeve', 'bag', 'backpack', 'charger', 'adapter',
    'adaptor', 'cable', 'earbud', 'earphone', 'headphone', 'headset',
    'speaker', 'powerbank', 'battery', 'hub', 'dock', 'stand', 'keyboard',
    'mouse', 'mousemat', 'pen', 'stylus', 'strap', 'protector', 'glass',
    'ink', 'paper', 'toner', 'cartridge', 'storage', 'ssd', 'card', 'reader',
    'remote', 'controller', 'gamepad', 'trigger', 'cooler', 'light',
    'webcam', 'tripod', 'mount', 'lens', 'filter', 'mic', 'microphone',
    'label', 'ribbon', 'drum', 'fuser', 'lamp', 'bulb',
})
_PRODUCT_LIST_TOKENS = frozenset({
    'product', 'devic', 'gadget', 'item', 'thing',
})
_ACCESSORY_LIST_TOKENS = frozenset({'accessory'})

_DEVICE_TOKENS = frozenset({
    'phon', 'laptop', 'tablet', 'tv', 'camera', 'printer', 'router',
    'speaker', 'headphon', 'headset', 'earbud', 'earphon', 'monitor',
    'watch', 'console', 'projector', 'scanner', 'keyboard', 'mous',
    'controller', 'gamepad',
})

_ISSUE_SIGNAL_TOKENS = frozenset({
    'charg', 'freez', 'crash', 'power', 'boot', 'start', 'pair', 'bluetooth',
    'connect', 'sound', 'audio', 'screen', 'display', 'battery', 'drain',
    'overheat', 'heat', 'slow', 'lag', 'stuck', 'error', 'fail', 'drift',
    'storage', 'memory', 'card', 'button', 'touch', 'network', 'wifi',
    'signal', 'restart', 'reboot', 'hang', 'unresponsive', 'flicker',
    'distort', 'distortion', 'mut', 'volum', 'dead', 'broken', 'damage',
    'noise', 'static', 'warm', 'shutdown', 'lock', 'brick',
})

_ISSUE_EXPANSIONS = (
    (r"\b(?:won'?t|wont|doesn'?t|does not|isn'?t|is not|not|can'?t|cant)\b[^.!?]{0,24}\b(?:turn|turns|turning|power|powers|powering|boot|booting|start|starting)\b[^.!?]{0,8}\bon\b", 'power boot start'),
    (r"\b(?:won'?t|wont|doesn'?t|does not|not|isn'?t|is not|can'?t|cant)\b[^.!?]{0,20}\bcharg(?:e|es|ing|er)\b", 'charging battery charger'),
    (r"\b(?:won'?t|wont|doesn'?t|does not|not|can'?t|cant)\b[^.!?]{0,20}\b(?:connect|pair|sync)\w*\b", 'connect pairing bluetooth'),
    (r"\bno\s+(?:sound|audio|picture|signal)\b", 'sound audio signal'),
    (r"\b(?:keep|keeps|constantly|randomly)\s+(?:freez|crash|restart|reboot)\w*", 'freeze crash restart'),
    (r"\b(?:overheat|overheating|too hot|getting hot|gets hot)\w*", 'overheat heat'),
    (r"\bbattery\s+(?:drain|drains|draining|dies|life)\w*", 'battery drain'),
    (r"\b(?:blank|black|dead)\s+(?:screen|display)\b", 'screen display'),
    (r"\b(?:freez|unresponsive|stuck|hang)\w*", 'freeze hang unresponsive'),
    (r"\b(?:slow|lag|laggy)\b", 'slow lag performance'),
    (r"\b(?:error|fault|glitch)\b", 'error fault'),
    (r"\b(?:memory card|sd card|microsd|storage full)\b", 'memory card storage'),
    (r"\b(?:drift|drifting|joystick|stick)\b", 'drift stick controller'),
)

_TOPIC_PATTERNS = (
    ('overheat', (r'overheat', r'too hot', r'getting hot', r'gets hot', r'heat(?:ing)?\s*up')),
    ('pairing', (r'\bpair', r'bluetooth', r'\bconnect')),
    ('display', (r'\bscreen\b', r'\bdisplay\b', r'\btouch', r'flicker', r'\bpixel', r'\blines?\b')),
    ('audio', (r'\bsound\b', r'\baudio\b', r'\bspeaker', r'\bvolume\b', r'\bmute', r'\bmicrophone\b', r'\bmic\b', r'distort')),
    ('storage', (r'\bstorage\b', r'memory card', r'\bsd card\b', r'microsd', r'\bdisk\b', r'\bspace\b', r'\bfull\b')),
    ('performance', (r'\bslow\b', r'\blag', r'freez', r'\bcrash', r'\bhang', r'\bstuck\b', r'unresponsive', r'\brestart', r'\breboot')),
    ('network', (r'wi-?fi', r'\binternet\b', r'\bnetwork\b', r'\brouter\b', r'offline', r'\bsignal\b', r'ethernet')),
    ('battery', (r'\bbattery\b(?![^.!?]*\bcharg)', r'\bdrain', r'\bhealth\b')),
    ('charging', (r'\bcharg', r'\bbattery\b', r'power adapter', r'\badapter\b')),
    ('power', (r'\bpower\b', r'turn(?:s|ing)? on', r'\bboot', r'\bstart', r'\bdead\b', r'black screen')),
)

_TOPIC_LABELS = {
    'overheat': 'overheating',
    'pairing': 'pairing and connection',
    'display': 'display',
    'audio': 'audio',
    'storage': 'storage',
    'performance': 'performance',
    'network': 'network',
    'battery': 'battery drain',
    'charging': 'charging',
    'power': 'power',
    'default': 'troubleshooting',
}

_TOPIC_STEPS = {
    'power': (
        'Disconnect the device from power and wait at least 30 seconds.',
        'Use the original charger and cable, and try a different wall outlet.',
        'Hold the power button for 10 to 15 seconds to force a restart.',
        'Check the manufacturer support page for a firmware update or reset procedure.',
        'If the device stays dead, have the battery or power board inspected by a technician.',
    ),
    'battery': (
        'Check battery usage and limit apps running in the background.',
        'Lower screen brightness and turn off always-on or high-refresh features.',
        'Install the latest software update and restart the device.',
        'Check battery health and replace the battery if it is degraded.',
        'If the drain continues, have the battery and charging board inspected.',
    ),
    'charging': (
        'Use the original charger and cable, and try a different wall outlet.',
        'Clean the charging port and connector gently with a dry brush or compressed air.',
        'Remove the case and let the device cool while charging.',
        'Test another known-good charger, cable and battery if possible.',
        'If charging still fails, have the charging port or battery checked.',
    ),
    'performance': (
        'Restart the device and close background apps.',
        'Free up storage space and remove unused apps or files.',
        'Clear the cache of the app that freezes or crashes.',
        'Install the latest software or firmware update.',
        'Back up your data and try a factory reset as a last resort.',
    ),
    'network': (
        'Restart the router and the device, then wait two minutes.',
        'Forget the Wi-Fi network and join it again with the correct password.',
        'Move closer to the router and keep the device away from metal or thick walls.',
        'Update the router firmware and the device software.',
        'Test another device on the same network to isolate the problem.',
    ),
    'audio': (
        'Check that the volume is up and the device is not muted.',
        'Test another source, cable or app to confirm where the sound is lost.',
        'Clean the speaker grille, port or earbuds gently.',
        'Re-pair Bluetooth devices and install the latest firmware.',
        'Test the device on another system; if the sound is still bad, the speaker or driver may need service.',
    ),
    'display': (
        'Check the brightness, input source and display cable connections.',
        'Force a restart and test the device again.',
        'Reseat or replace the HDMI or display cable where possible.',
        'Boot into safe mode or test another screen to rule out software.',
        'If lines, dead zones or cracks remain, have the display assembly checked.',
    ),
    'storage': (
        'Back up important files before changing anything.',
        'Free space by removing unused apps, photos and downloads.',
        'Format the memory card inside the device after backing it up.',
        'Try another card, reader or USB port.',
        'Run a storage diagnostic and replace the card or drive if it reports errors.',
    ),
    'pairing': (
        'Turn Bluetooth off and on again on both devices.',
        'Forget the accessory on the phone or computer, then put it back in pairing mode.',
        'Keep both devices within one metre and away from USB 3 hubs and Wi-Fi routers.',
        'Update the companion app and the accessory firmware.',
        'Reset the pairing list on the accessory and pair once more.',
    ),
    'overheat': (
        'Stop charging or running heavy tasks and let the device cool down.',
        'Remove the case and keep the device out of direct sunlight.',
        'Use only the original charger and cable.',
        'Close background apps and install the latest software update.',
        'If it keeps overheating, have the battery or charging board inspected.',
    ),
    'default': (
        'Restart the device and check all cables and connections.',
        'Confirm the device has power and the correct input or accessory is selected.',
        'Install the latest software or firmware update.',
        'Back up your data and reset the settings if the problem continues.',
        'Contact the manufacturer or a technician if the issue is still present.',
    ),
}

_PRODUCT_LOOKUP_WORDS = (
    'price', 'cost', 'how much', 'spec', 'feature', 'buy', 'purchase',
    'stock', 'available', 'review', 'compare',
)

_TROUBLE_WORDS = (
    'fix', 'problem', 'issue', 'trouble', 'wrong', 'broken', 'fail', 'error',
    'stuck', 'not ', 'wont', 'cant', 'cannot', 'dead', 'freeze', 'crash',
    'slow', 'lag', 'drain', 'overheat', 'repair', 'why', 'how', 'help',
)

_TECH_STANDARD_TOKENS = frozenset({
    '2g', '3g', '4g', '5g', '6g', 'lte', 'wifi', 'wifi6', 'wifi6e', 'wifi7',
    'bluetooth', 'usb', 'usba', 'usbc', 'hdmi', 'displayport', 'thunderbolt',
    'ethernet', '4k', '8k', '1080p', '1440p', '2160p', '60hz', '90hz',
    '120hz', '144hz', '165hz', '240hz', 'ddr3', 'ddr4', 'ddr5', 'lpddr4',
    'lpddr5', 'pcie3', 'pcie4', 'pcie5', 'nvme', 'sata', 'ip67', 'ip68',
    'oled', 'lcd', 'led', 'qled', 'miniled', 'microled', 'amoled', 'ips',
    'va', 'tn', 'hdr', 'hdr10', 'dolby', 'atmos',
})

_CATALOG_QUERY_RE = re.compile(
    r"\b(?:price|pricing|cost|how much|stock|in stock|out of stock|"
    r"available|availability|do you (?:have|sell|carry|stock)|show me|"
    r"list (?:all|the|your)|catalog|product page|"
    r"where (?:can|do|to) (?:i )?buy|buy (?:it|this|one|now))\b",
    re.IGNORECASE,
)

_RECOMMENDATION_RE = re.compile(
    r'\b(?:recommend\w*|suggest\w*|best|top)\b',
    re.IGNORECASE,
)

_COMPONENT_MODEL_RE = re.compile(
    r"\b(?:rtx|gtx|geforc\w*|radeon|rx\s?\d{3,4}|"
    r"m[1-9](?:\s+(?:pro|max|ultra))?|"
    r"a\d{2,4}(?:\s+(?:bionic|pro|fusion))?|"
    r"snapdragon|exynos|dimensity|tensor|ryzen|threadripper|"
    r"core\s+i[3-9]|xeon|arc\s+a\d+|iris\s+xe)\b",
    re.IGNORECASE,
)

_QUESTION_LIKE_RE = re.compile(
    r"^\s*(?:what|why|how|which|who|whom|whose|when|where|is|are|am|do|"
    r"does|did|can|could|should|would|will|tell|explain|define|describe|"
    r"find|look|looking|recommend|suggest|best|cheapest|top)\b"
    r"|\b(?:difference between|compared? (?:to|with)|versus|vs\.?|"
    r"better than|which (?:one )?is better|what should i (?:buy|get))\b",
    re.IGNORECASE,
)

_COMPARISON_RE = re.compile(
    r"\b(?:difference between|compare|comparison|versus|vs\.?|better than|"
    r"which (?:one )?is better)\b",
    re.IGNORECASE,
)

_REPAIR_ACTION_RE = re.compile(r"\b(?:fix|repair|troubleshoot)\b", re.IGNORECASE)

_REPAIR_PROBLEM_RE = re.compile(
    r"\b(?:not working|won'?t|wont|can'?t|cannot|doesn'?t|does not|"
    r"isn'?t|is not|problem with|issues? with|wrong with|"
    r"keeps? (?:crashing|freezing|restarting|disconnecting)|stuck|"
    r"unresponsive|no (?:sound|audio|signal|display|power)|black screen|"
    r"slow|laggy|drain(?:s|ing)?|overheat(?:s|ing)?|dead|broken|"
    r"freez(?:e|es|ing)|crash(?:es|ing)?|error|fail(?:s|ing|ed)?|"
    r"flicker(?:s|ing)?)\b",
    re.IGNORECASE,
)

_GREETING_RE = re.compile(
    r"^\s*(?:hi|hello|hey|greetings|good (?:morning|afternoon|evening)|"
    r"thanks|thank you)\b",
    re.IGNORECASE,
)

_TECH_CONTEXT_RE = re.compile(
    r"\b(?:phones?|iphones?|androids?|laptops?|notebooks?|tablets?|ipads?|"
    r"tvs?|televisions?|monitors?|screens?|displays?|computers?|pcs?|"
    r"desktops?|macbooks?|imacs?|windows|chromeos|linux|cameras?|"
    r"printers?|routers?|modems?|networks?|wi-?fi|internets?|speakers?|"
    r"headphones?|headsets?|earbuds?|earphones?|watches?|smartwatches?|"
    r"consoles?|playstations?|xbox|nintendos?|projectors?|scanners?|"
    r"keyboards?|mice|mouse|controllers?|gamepads?|chargers?|charging|"
    r"ssds?|hdds?|drives?|storage|memory|ram|cpus?|gpus?|motherboards?|"
    r"usb|hdmi|cables?|adapters?|adaptors?|docks?|hubs?|devices?|"
    r"gadgets?|accessor(?:y|ies)|firmware|software|apps?|techfix|"
    r"bluetooth)\b",
    re.IGNORECASE,
)


def _normalize(text):
    return (text or '').lower().replace('\u2019', "'").replace('\u2018', "'")


def _stem(word):
    word = _TOKEN_ALIASES.get(word, word)
    if not any(char.isdigit() for char in word):
        word = word.replace('z', 's')
    if len(word) <= 3 or any(char.isdigit() for char in word):
        return word
    if word.endswith('ing') and len(word) >= 6:
        word = word[:-3]
        if len(word) >= 2 and word[-1] == word[-2]:
            word = word[:-1]
    elif word.endswith('ed') and len(word) >= 5:
        word = word[:-2]
        if len(word) >= 2 and word[-1] == word[-2]:
            word = word[:-1]
    elif word.endswith('ies') and len(word) >= 5:
        word = word[:-3] + 'y'
    elif word.endswith('es') and len(word) >= 5:
        word = word[:-2]
    elif word.endswith('s') and len(word) >= 4:
        word = word[:-1]
    if word.endswith('e') and len(word) >= 4:
        word = word[:-1]
    return word


def _tokens(text):
    text = re.sub(r"['`]", '', _normalize(text))
    tokens = set()
    for raw in TOKEN_RE.findall(text):
        raw = raw.replace('-', '')
        if len(raw) < 2 or raw in _STOPWORDS:
            continue
        token = _stem(raw)
        if len(token) < 2 or token in _STOPWORDS:
            continue
        tokens.add(token)
    return tokens


def _token_list(text):
    text = re.sub(r"['`]", '', _normalize(text))
    tokens = []
    for raw in TOKEN_RE.findall(text):
        raw = raw.replace('-', '')
        if len(raw) < 2 or raw in _STOPWORDS:
            continue
        token = _stem(raw)
        if len(token) < 2 or token in _STOPWORDS or token in tokens:
            continue
        tokens.append(token)
    return tokens


def _strict_tokens(text, drop_generic=True):
    """Raw identity tokens that keep model qualifiers such as Pro and Max."""
    text = re.sub(r"['`]", '', _normalize(text)).replace('+', ' plus ')
    tokens = set()
    for raw in TOKEN_RE.findall(text):
        raw = raw.replace('-', '')
        if len(raw) < 2:
            continue
        stem = _stem(raw)
        if raw in _STOPWORDS and raw not in _MODEL_WORDS:
            continue
        if stem in _STOPWORDS and raw not in _MODEL_WORDS:
            continue
        if drop_generic and (
            raw in _GENERIC_TOKENS
            or (stem in _GENERIC_TOKENS and raw not in _DISTINCTIVE_ALIASES)
        ):
            continue
        tokens.add(raw)
    return tokens


def _brand_words(products, accessories):
    words = set()
    for item in list(products) + list(accessories):
        if item.brand:
            words |= set(TOKEN_RE.findall(_normalize(item.brand)))
    return words


def _query_identity_tokens(query, brand_words, drop_generic=True):
    tokens = _strict_tokens(query, drop_generic=drop_generic) - brand_words
    return {
        token for token in tokens
        if token not in _ISSUE_SIGNAL_TOKENS
        and _stem(token) not in _ISSUE_SIGNAL_TOKENS
    }


def _item_identity_tokens(name, brand, brand_words, drop_generic=True):
    return _strict_tokens(name, drop_generic=drop_generic) - brand_words


def _product_identity_tokens(product, brand_words, drop_generic=True):
    if product is None:
        return set()
    return _item_identity_tokens(
        product.name, product.brand, brand_words, drop_generic=drop_generic
    )


def _accessory_identity_tokens(accessory, brand_words):
    if accessory is None:
        return set()
    tokens = _item_identity_tokens(
        accessory.name, accessory.brand, brand_words, drop_generic=False
    )
    if accessory.compatibility_notes:
        tokens |= _strict_tokens(
            accessory.compatibility_notes, drop_generic=False
        ) - brand_words
    return tokens


def _solution_identity_tokens(solution, brand_words):
    return _product_identity_tokens(solution.related_product, brand_words)


def _identity_match(item_tokens, identity_terms):
    return bool(identity_terms) and identity_terms <= item_tokens


def _accessory_type_tokens(query):
    tokens = set()
    for token in _strict_tokens(query, drop_generic=False):
        if token in _ACCESSORY_QUERY_WORDS or _stem(token) in _ACCESSORY_QUERY_WORDS:
            tokens.add(token)
            tokens.add(_stem(token))
    return tokens


def _item_has_type(item, type_tokens):
    if not type_tokens:
        return True
    item_tokens = _tokens(getattr(item, 'name', ''))
    item_tokens |= _tokens(getattr(item, 'kind', ''))
    return bool(item_tokens & type_tokens)


def _item_has_type_name(item, type_tokens):
    if not type_tokens:
        return True
    return bool(_tokens(getattr(item, 'name', '')) & type_tokens)


def _brand_matches(item, brand_hits):
    if not brand_hits:
        return True
    brand = (getattr(item, 'brand', '') or '').lower()
    return any(brand == hit.lower() for hit in brand_hits)


def _expansion_tokens(query):
    text = _normalize(query)
    extra = set()
    for pattern, words in _ISSUE_EXPANSIONS:
        if re.search(pattern, text):
            extra |= _tokens(words)
    return extra


def _query_tokens(query):
    return _tokens(query) | _expansion_tokens(query)


def search_terms(query):
    text = re.sub(r"['`]", '', _normalize(query))
    terms = []
    for raw in TOKEN_RE.findall(text):
        if len(raw) < 2 or raw in _STOPWORDS:
            continue
        if raw not in terms:
            terms.append(raw)
        stemmed = _stem(raw.replace('-', ''))
        if len(stemmed) > 1 and stemmed not in _STOPWORDS and stemmed not in terms:
            terms.append(stemmed)
    for token in _expansion_tokens(query):
        if token not in terms:
            terms.append(token)
    return terms[:12]


def _split_steps(raw):
    text = (raw or '').replace('\r', '').strip()
    if not text:
        return []
    matches = list(STEP_RE.finditer(text))
    if matches:
        steps = []
        for index, match in enumerate(matches):
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            step = re.sub(r'\s+', ' ', text[start:end]).strip(' .;')
            if step:
                steps.append(step)
        if steps:
            return steps
    parts = re.split(r'\n+|\s[-*\u2022]\s+|;\s+', text)
    steps = []
    for part in parts:
        part = re.sub(r'\s+', ' ', part).strip(' .;')
        if part:
            steps.append(part)
    return steps


def _score_fields(query_tokens, query_phrase, phrase_text, fields):
    score = 0
    matched = set()
    for token in query_tokens:
        for tokens, weight in fields:
            if token in tokens:
                score += weight
                matched.add(token)
    if query_phrase and len(query_phrase.split()) >= 2 and phrase_text:
        if ' %s ' % query_phrase in ' %s ' % phrase_text:
            score += 10
    return score, matched


def _score_solution(solution, query_tokens, query_phrase):
    product = solution.related_product
    title_tokens = _tokens(solution.title)
    product_tokens = _tokens(product.name) if product else set()
    product_category = (
        _tokens(product.category.name) if product and product.category else set()
    )
    fields = (
        (title_tokens, 5),
        (_tokens(solution.problem_description), 3),
        (product_tokens, 4),
        (_tokens(product.brand) if product else set(), 2),
        (_tokens(solution.category.name) if solution.category else set(), 2),
        (product_category, 2),
        (_tokens(solution.steps), 1),
    )
    score, matched = _score_fields(
        query_tokens, query_phrase, ' '.join(_token_list(solution.title)), fields
    )
    for token in matched:
        if any(char.isdigit() for char in token) and (
            token in title_tokens or token in product_tokens
        ):
            score += 4
            break
    return score, matched, solution


def _score_product(product, query_tokens, query_phrase):
    name_tokens = _tokens(product.name)
    fields = (
        (name_tokens, 6),
        (_tokens(product.brand), 3),
        (_tokens(product.category.name) if product.category else set(), 2),
        (_tokens(product.description), 1),
        (_tokens(product.specifications), 1),
    )
    score, matched = _score_fields(
        query_tokens, query_phrase, ' '.join(_token_list(product.name)), fields
    )
    if any(any(char.isdigit() for char in token) and token in name_tokens for token in matched):
        score += 5
    return score, matched, product


def _recommendation_score(product):
    specs = ' '.join(product.spec_list).lower()
    processor_rank = 0
    for pattern, rank in (
        (r'\bsnapdragon\s+8\s+elite\s+gen\s+5\b', 9),
        (r'\bdimensity\s+9500\b', 9),
        (r'\ba19\s+pro\b', 9),
        (r'\bsnapdragon\s+8\s+elite\b', 8),
        (r'\bdimensity\s+9400\b', 8),
        (r'\ba18\s+pro\b', 8),
        (r'\bsnapdragon\s+8\s+gen\s+3\b', 7),
        (r'\bdimensity\s+9300\b', 7),
    ):
        if re.search(pattern, specs):
            processor_rank = rank
            break
    memory_pair = re.search(
        r'\b(\d+)\s*gb\s*/\s*(\d+)\s*gb\b',
        specs,
    )
    ram_match = re.search(r'\b(\d+)\s*gb\s*(?:ram|memory)\b', specs)
    storage_match = re.search(
        r'\b(?:storage|rom)\s*[:=]?\s*(\d+)\s*gb\b',
        specs,
    )
    ram = int(ram_match.group(1)) if ram_match else 0
    storage = int(storage_match.group(1)) if storage_match else 0
    if memory_pair:
        ram = max(ram, int(memory_pair.group(1)))
        storage = max(storage, int(memory_pair.group(2)))
    return (
        processor_rank,
        ram,
        storage,
        bool(re.search(r'\b(?:amoled|oled|ltpo|\d+\s*hz)\b', specs)),
        bool(re.search(r'\b\d+\s*mp\b', specs)),
        bool(re.search(r'\b\d{3,5}\s*mah\b', specs)),
        len(product.spec_list),
    )


def _score_accessory(accessory, query_tokens, query_phrase):
    name_tokens = _tokens(accessory.name)
    fields = (
        (name_tokens, 6),
        (_tokens(accessory.brand), 3),
        (_tokens(accessory.category.name) if accessory.category else set(), 2),
        (_tokens(accessory.compatibility_notes), 2),
        (_tokens(accessory.description), 1),
    )
    score, matched = _score_fields(
        query_tokens, query_phrase, ' '.join(_token_list(accessory.name)), fields
    )
    if any(any(char.isdigit() for char in token) and token in name_tokens for token in matched):
        score += 5
    return score, matched, accessory


def _has_phrase(text, phrases):
    return any(
        re.search(r'(?<!\w)%s(?!\w)' % re.escape(word.strip()), text)
        for word in phrases
        if word.strip()
    )


def _detect_intent(query):
    text = _normalize(query)
    if _has_phrase(text, _PRODUCT_LOOKUP_WORDS + (
        'specs', 'specification', 'specifications', 'features',
        'prices', 'costs', 'reviews', 'buying',
    )):
        return 'lookup'
    if _has_phrase(text, _TROUBLE_WORDS):
        return 'troubleshoot'
    return 'general'


def _detect_topic(query):
    text = _normalize(query)
    for topic, patterns in _TOPIC_PATTERNS:
        if any(re.search(pattern, text) for pattern in patterns):
            return topic
    return 'default'


def _looks_like_repair_request(query):
    text = _normalize(query)
    if _REPAIR_ACTION_RE.search(text):
        return True
    tokens = _tokens(text)
    has_device = bool(tokens & _DEVICE_TOKENS)
    if re.search(r"\b(?:problem|issues?|wrong)\s+with\b", text):
        if re.search(r"\bmy\b", text) or has_device:
            return True
    if re.search(r"\bwhy\s+(?:is|are|does|do)\s+my\b", text):
        return True
    if _REPAIR_PROBLEM_RE.search(text):
        if re.search(r"\bmy\b", text) or has_device:
            return True
    return False


def _family_tokens(products, accessories, brand_tokens):
    family = set()
    brand_keys = set(brand_tokens)
    for item in list(products) + list(accessories):
        for token in _token_list(getattr(item, 'name', '')):
            if (
                len(token) >= 3
                and token.isalpha()
                and token not in _GENERIC_TOKENS
                and token not in _MODEL_WORDS
                and token not in _ISSUE_SIGNAL_TOKENS
                and token not in brand_keys
                and not _COMPONENT_MODEL_RE.search(token)
            ):
                family.add(token)
                break
    return family


def _looks_like_specific_model(
    query_tokens, query_identity, identity_tokens, brand_tokens, family_tokens
):
    if not query_identity:
        return False
    has_marker = bool(query_tokens & _MODEL_WORDS) or any(
        any(char.isdigit() for char in token) for token in query_tokens
    )
    if has_marker and (
        query_tokens & family_tokens or query_tokens & set(brand_tokens)
    ):
        return True
    for token in query_tokens:
        if (
            token not in _TECH_STANDARD_TOKENS
            and token in identity_tokens
            and any(char.isdigit() for char in token)
        ):
            return True
    return False


def _has_exact_catalog_identity(
    query_identity, products, accessories, brand_words
):
    if not query_identity:
        return False
    for item in products:
        if _product_identity_tokens(item, brand_words) == query_identity:
            return True
    for item in accessories:
        if _accessory_identity_tokens(item, brand_words) == query_identity:
            return True
    return False


def _is_general_tech_question(
    query, query_tokens, query_identity, identity_tokens, brand_tokens,
    family_tokens, products, accessories, brand_words,
):
    text = _normalize(query)
    if not text:
        return False
    if _GREETING_RE.search(text):
        return True
    if _CATALOG_QUERY_RE.search(text):
        return False
    if _looks_like_repair_request(text):
        return False
    if not _QUESTION_LIKE_RE.search(text):
        return False
    if _COMPARISON_RE.search(text):
        return True
    if _has_exact_catalog_identity(
        query_identity, products, accessories, brand_words
    ):
        return False
    if _COMPONENT_MODEL_RE.search(text) and not (
        query_tokens & family_tokens
    ):
        return True
    if _looks_like_specific_model(
        query_tokens, query_identity, identity_tokens, brand_tokens,
        family_tokens,
    ):
        return False
    return True


def _has_tech_context(query, query_tokens, brand_tokens):
    if _TECH_CONTEXT_RE.search(_normalize(query)):
        return True
    return bool(query_tokens & set(brand_tokens))


def _general_tech_answer():
    return {
        'kind': 'answer',
        'badge': 'Technology help',
        'title': '',
        'summary': (
            'I can answer that using general technology knowledge, but the AI '
            'knowledge service is unavailable right now. Please try again, or '
            'ask me about TechFix catalog products, prices, stock, or repair '
            'guides.'
        ),
        'first_step': '',
        'steps': [],
        'steps_title': '',
        'difficulty': '',
        'category': '',
        'product': None,
        'accessory': None,
        'video_url': '',
        'safety': '',
        'suggestions': [],
        'ai': False,
        'strict': False,
        'matches': {'products': [], 'accessories': [], 'solutions': []},
        'sources': [],
    }


def _is_price_query(query):
    text = _normalize(query)
    return any(word in text for word in ('price', 'cost', 'how much'))


def _plural(count, singular, plural=None):
    if count == 1:
        return '1 %s' % singular
    return '%s %s' % (count, plural or singular + 's')


def _clean_title(title):
    return re.sub(r'^Fix\s+', '', title or '', flags=re.IGNORECASE).strip()


def _device_match(item, device_tokens):
    if not device_tokens or item is None:
        return True
    return bool(_tokens(getattr(item, 'kind', '')) & device_tokens)


def _suggestions(solution_ranked, brand=None, device_tokens=None,
                 identity_terms=None, brand_words=None):
    if not identity_terms and not brand and not device_tokens:
        return []
    suggestions = []
    for _, _, solution in solution_ranked:
        product = solution.related_product
        if brand and (not product or (product.brand or '').lower() != brand.lower()):
            continue
        if device_tokens and not _device_match(product, device_tokens):
            continue
        if identity_terms and not _identity_match(
            _product_identity_tokens(product, brand_words or set()), identity_terms
        ):
            continue
        text = _clean_title(solution.title)
        if text and text not in suggestions:
            suggestions.append(text)
        if len(suggestions) == 3:
            break
    return suggestions[:3]


_VIDEO_ID_RE = re.compile(
    r'(?:v=|youtu\.be/|/embed/|/shorts/|/live/)([0-9A-Za-z_-]{6,20})'
)
_VIDEO_TITLE_TIMEOUT = 3

_VIDEO_TITLE_ISSUES = {
    'charging': frozenset({
        'charg', 'charger', 'battery', 'batteri', 'drain', 'connector',
        'port', 'plug', 'spark', 'loos', 'di',
    }),
    'audio': frozenset({
        'sound', 'audio', 'volume', 'volum', 'distort', 'distortion',
        'static', 'silent', 'ear', 'mute', 'mut', 'noise',
    }),
    'pairing': frozenset({
        'pair', 'bluetooth', 'sync', 'connect', 'connection',
    }),
    'display': frozenset({
        'screen', 'display', 'flicker', 'black', 'pictur', 'touchscreen',
        'touch', 'unresponsiv',
    }),
    'keyboard': frozenset({
        'keyboard', 'key', 'button', 'trackpad', 'touchpad', 'click',
        'unresponsiv',
    }),
    'network': frozenset({
        'wifi', 'network', 'internet', 'signal', 'ping', 'offlin', 'drop',
        'disconnect',
    }),
    'overheat': frozenset({
        'overheat', 'heat', 'hot', 'warm', 'temperatur', 'fan',
    }),
    'performance': frozenset({
        'slow', 'slowli', 'lag', 'freez', 'crash', 'hang', 'stutter',
    }),
    'boot': frozenset({
        'boot', 'restart', 'logo', 'turn', 'stuck',
    }),
    'storage': frozenset({
        'storage', 'memory', 'disk', 'spac', 'card', 'sd',
    }),
    'camera': frozenset({
        'camera', 'lens', 'blur', 'blurry', 'focu',
    }),
    'printer': frozenset({
        'printer', 'print', 'offlin', 'paper', 'jam', 'ink', 'toner',
    }),
    'fingerprint': frozenset({
        'fingerprint', 'face', 'unlock',
    }),
}

_SOLUTION_ISSUES = {
    'charging': frozenset({
        'charg', 'charger', 'battery', 'batteri', 'drain', 'di', 'power',
        'led', 'port', 'connector', 'plug', 'spark', 'loos',
    }),
    'audio': frozenset({
        'sound', 'audio', 'volume', 'volum', 'distort', 'distortion',
        'static', 'silent', 'ear', 'mute', 'mut', 'noise',
    }),
    'pairing': frozenset({
        'pair', 'bluetooth', 'sync', 'connect', 'connection',
    }),
    'display': frozenset({
        'screen', 'display', 'flicker', 'black', 'blank', 'pictur',
        'touchscreen', 'touch', 'tap', 'dead', 'respond', 'unresponsiv',
    }),
    'keyboard': frozenset({
        'keyboard', 'key', 'button', 'trackpad', 'touchpad', 'click',
        'mous', 'respond', 'unresponsiv',
    }),
    'network': frozenset({
        'wifi', 'network', 'internet', 'signal', 'ping', 'offlin', 'slow',
        'slowli', 'disconnect',
    }),
    'overheat': frozenset({
        'overheat', 'heat', 'hot', 'warm', 'temperatur', 'fan',
    }),
    'performance': frozenset({
        'slow', 'slowli', 'lag', 'freez', 'crash', 'hang', 'stutter',
    }),
    'boot': frozenset({
        'boot', 'restart', 'logo', 'turn', 'stuck', 'dead', 'power',
    }),
    'storage': frozenset({
        'storage', 'memory', 'disk', 'spac', 'card', 'sd', 'full',
        'recognis', 'recogniz',
    }),
    'camera': frozenset({
        'camera', 'lens', 'blur', 'blurry', 'focu',
    }),
    'printer': frozenset({
        'printer', 'print', 'offlin', 'paper', 'jam', 'ink', 'toner',
    }),
    'fingerprint': frozenset({
        'fingerprint', 'face', 'unlock',
    }),
}

_QUERY_ISSUES = {
    'charging': frozenset({
        'charg', 'charger', 'battery', 'batteri', 'drain', 'di', 'port',
        'connector', 'plug', 'spark', 'loos',
    }),
    'audio': frozenset({
        'sound', 'audio', 'volume', 'volum', 'distort', 'distortion',
        'static', 'silent', 'ear', 'mute', 'mut', 'noise',
    }),
    'pairing': frozenset({
        'pair', 'bluetooth', 'sync', 'connect', 'connection',
    }),
    'display': frozenset({
        'screen', 'display', 'flicker', 'black', 'blank', 'pictur',
        'touchscreen', 'touch', 'tap', 'unresponsiv',
    }),
    'keyboard': frozenset({
        'keyboard', 'key', 'button', 'trackpad', 'touchpad', 'click',
        'mous', 'respond', 'unresponsiv',
    }),
    'network': frozenset({
        'wifi', 'network', 'internet', 'signal', 'ping', 'offlin', 'drop',
        'disconnect',
    }),
    'overheat': frozenset({
        'overheat', 'heat', 'hot', 'warm', 'temperatur', 'fan',
    }),
    'performance': frozenset({
        'slow', 'slowli', 'lag', 'freez', 'crash', 'hang', 'stutter',
    }),
    'boot': frozenset({
        'boot', 'restart', 'logo', 'turn', 'stuck', 'power',
    }),
    'storage': frozenset({
        'storage', 'memory', 'disk', 'spac', 'card', 'sd', 'full',
        'recognis', 'recogniz',
    }),
    'camera': frozenset({
        'camera', 'lens', 'blur', 'blurry', 'focu',
    }),
    'printer': frozenset({
        'printer', 'print', 'offlin', 'paper', 'jam', 'ink', 'toner',
    }),
    'fingerprint': frozenset({
        'fingerprint', 'face', 'unlock',
    }),
}

_VIDEO_ACTION_RE = re.compile(
    r"\b(?:fix\w*|repair\w*|solv\w*|solution\w*|troubleshoot\w*|"
    r"problem\w*|issue\w*|error\w*|fail\w*|drain\w*|stuck|loose|"
    r"overheat\w*|blur\w*|offline|spark\w*|drop\w*|distort\w*|"
    r"reset\w*|restor\w*|replac\w*|clean\w*|unlock\w*|slow\w*|lag\w*|"
    r"flicker\w*|black|blank|improv\w*|extend\w*|won't|wont|cannot|"
    r"can't|stopped|disconnect\w*|not\s+(?:charging|charge|holding|"
    r"powering|turning|booting|pairing|connecting|working|responding)|"
    r"will\s+not|no\s+(?:sound|picture|internet|signal)|high\s+ping|"
    r"double\s+click|weak\s+signal)\b",
    re.IGNORECASE,
)

_VIDEO_PAIRING_ACTION_RE = re.compile(
    r"\bpair\w*|\b(?:can't|cannot|won't|wont|not|fail\w*|problem\w*|"
    r"issue\w*|error\w*|troubleshoot\w*)\b[^.?!]{0,40}\bconnect\w*",
    re.IGNORECASE,
)

_VIDEO_REQUEST_RE = re.compile(
    r"\btutorials?\b|"
    r"\bvideos?\s+(?:tutorials?|guides?|walkthroughs?|instructions?|steps?)\b|"
    r"\bvideos?\s+(?:for|on|about|of|showing|that\s+shows?)\b|"
    r"\b(?:show|give|send|find|get|need|want|watch|see)\s+"
    r"(?:me\s+|us\s+)?(?:a\s+|an\s+|the\s+)?(?:youtube\s+)?videos?\b|"
    r"\byoutube\s+(?:link|guide)\b|"
    r"\blink\s+(?:to|for)\s+(?:a\s+)?youtube\b|"
    r"\b(?:show|give|send|find|get)\s+(?:me\s+)?(?:a\s+)?youtube\b",
    re.IGNORECASE,
)

_VIDEO_QUERY_FILLERS_RE = re.compile(
    r"\b(?:can|could|would|will|please|give|show|send|find|get|me|my|a|an|"
    r"the|for|about|on|of|to|i|need|want|see|watch|any|do|you|have|is|are|"
    r"there|link)\b",
    re.IGNORECASE,
)


def _is_video_request(query):
    return bool(_VIDEO_REQUEST_RE.search(_normalize(query)))


def _video_search_url(query):
    text = _VIDEO_REQUEST_RE.sub(' ', _normalize(query))
    text = re.sub(
        r'\b(?:videos?|youtube)\b', ' ', text, flags=re.IGNORECASE
    )
    text = _VIDEO_QUERY_FILLERS_RE.sub(' ', text)
    text = re.sub(r'\s+', ' ', text).strip(' .?!,;:-')
    if not text:
        return ''
    if not re.search(r'\b(?:fix|repair|solution|tutorial)\b', text):
        text += ' fix tutorial'
    return 'https://www.youtube.com/results?search_query=%s' % (
        urllib.parse.quote_plus(text)
    )


@lru_cache(maxsize=512)
def _video_title(url):
    match = _VIDEO_ID_RE.search(str(url or ''))
    if not match:
        return ''
    watch_url = 'https://www.youtube.com/watch?v=%s' % match.group(1)
    endpoint = 'https://www.youtube.com/oembed?format=json&url=%s' % (
        urllib.parse.quote(watch_url, safe='')
    )
    request = urllib.request.Request(
        endpoint, headers={'User-Agent': 'Mozilla/5.0'}
    )
    try:
        with urllib.request.urlopen(
            request, timeout=_VIDEO_TITLE_TIMEOUT
        ) as response:
            payload = json.loads(response.read().decode('utf-8'))
    except Exception:
        return ''
    return str(payload.get('title') or '').strip()


def _video_issue_categories(text, table):
    tokens = _tokens(text)
    return {name for name, words in table.items() if tokens & words}


def _solution_issue_text(solution):
    title = solution.title or ''
    if title.lower().startswith('fix ') and ': ' in title:
        title = title.split(': ', 1)[1]
    return '%s %s' % (title, solution.problem_description or '')


def _video_matches_question(video_url, query, solution=None):
    title = _video_title(video_url)
    if not title:
        return False
    title_issues = _video_issue_categories(title, _VIDEO_TITLE_ISSUES)
    if not title_issues:
        return False
    query_issues = _video_issue_categories(query or '', _QUERY_ISSUES)
    if query_issues:
        required = query_issues
    elif solution is not None:
        required = _video_issue_categories(
            _solution_issue_text(solution), _SOLUTION_ISSUES
        )
    else:
        required = set()
    shared = required & title_issues
    if not shared:
        return False
    action_ok = bool(_VIDEO_ACTION_RE.search(title))
    if not action_ok and 'pairing' in shared:
        action_ok = bool(_VIDEO_PAIRING_ACTION_RE.search(title))
    if not action_ok:
        return False
    if solution is not None:
        product = solution.related_product
        if product is not None:
            identity = _tokens('%s %s' % (
                product.brand or '', product.name or ''
            ))
            if identity and not (identity & _tokens(title)):
                return False
    return True


def _tutorial_video(solution_ranked, brand_hits=(), device_tokens=(),
                    identity_terms=None, brand_words=None, issue_terms=None,
                    query='', min_score=3):
    """Return the video of the best matching repair guide, if it has one."""
    brand_names = {
        brand.casefold() for brand in (brand_hits or ()) if brand
    }
    issue_terms = issue_terms or set()
    best_video = ''
    best_solution = None
    best_overlap = -1
    for score, matched, solution in solution_ranked:
        if score < min_score or not solution.video_url:
            continue
        product = solution.related_product
        if brand_names and (
            not product or (product.brand or '').casefold() not in brand_names
        ):
            continue
        if device_tokens and not _device_match(product, device_tokens):
            continue
        if identity_terms and not _identity_match(
            _solution_identity_tokens(solution, brand_words or set()),
            identity_terms,
        ):
            continue
        overlap = len(matched & issue_terms)
        if issue_terms and not overlap:
            continue
        if overlap > best_overlap:
            best_video = solution.video_url
            best_solution = solution
            best_overlap = overlap
            if not issue_terms:
                break
    if best_video and not _video_matches_question(
        best_video, query, best_solution
    ):
        return ''
    return best_video


def _video_identity_match(item_tokens, identity_terms):
    if not identity_terms:
        return False
    item_stems = {_stem(token) for token in item_tokens}
    return {_stem(token) for token in identity_terms} <= item_stems


def _best_video_solution(solution_ranked, brand_hits=(), device_tokens=(),
                         identity_terms=None, brand_words=None,
                         issue_terms=None, min_score=5,
                         require_identity=True, family_terms=None):
    """Return the best ranked guide with a video for an explicit video request."""
    brand_names = {
        brand.casefold() for brand in (brand_hits or ()) if brand
    }
    issue_terms = issue_terms or set()
    family_terms = family_terms or set()
    for score, matched, solution in solution_ranked:
        if score < min_score or not solution.video_url:
            continue
        product = solution.related_product
        if brand_names and (
            not product or (product.brand or '').casefold() not in brand_names
        ):
            continue
        if device_tokens and not _device_match(product, device_tokens):
            continue
        solution_identity = _solution_identity_tokens(
            solution, brand_words or set()
        )
        if require_identity and identity_terms and not _video_identity_match(
            solution_identity, identity_terms,
        ):
            continue
        if not require_identity and family_terms and not (
            {_stem(token) for token in solution_identity}
            & {_stem(token) for token in family_terms}
        ):
            continue
        if issue_terms:
            solution_issues = (
                _tokens(solution.title) | _tokens(solution.problem_description)
            )
            if not (matched & issue_terms and issue_terms & solution_issues):
                continue
        return score, matched, solution
    return None


def _solution_answer(solution, query='', include_video=True):
    steps = _split_steps(solution.steps)
    desc = (solution.problem_description or '').strip()
    if desc:
        summary = 'Issue: %s\n\nFollow the step-by-step repair guide below to resolve this problem.' % desc
    else:
        summary = 'Follow the step-by-step repair guide below to resolve this problem.'
    return {
        'kind': 'solution',
        'badge': 'Repair guide',
        'title': solution.title,
        'summary': summary,
        'first_step': steps[0] if steps else '',
        'steps': steps,
        'steps_title': 'Step-by-step repair process' if steps else '',
        'difficulty': solution.difficulty_level,
        'category': solution.category.name if solution.category else '',
        'product': solution.related_product,
        'accessory': None,
        'video_url': (
            solution.video_url
            if include_video and _video_matches_question(
                solution.video_url, query, solution
            )
            else ''
        ),
        'safety': '',
        'suggestions': [],
        'ai': False,
    }


def _product_answer(product, query, intent, topic):
    summary_parts = []
    if product.description:
        summary_parts.append(product.description.strip())
    if product.price:
        summary_parts.append('Price: ₱%s.' % product.price)
    elif _is_price_query(query):
        summary_parts.append('No price is listed in the TechFix catalog.')
    if product.stock_quantity is not None:
        stock_text = '%s units available' % product.stock_quantity if product.stock_quantity > 0 else 'Currently out of stock'
        summary_parts.append('Stock: %s.' % stock_text)
    summary = ' '.join(summary_parts) if summary_parts else '%s is listed in the TechFix catalog.' % product.name
    steps = []
    steps_title = ''
    if intent == 'troubleshoot':
        label = _TOPIC_LABELS.get(topic, _TOPIC_LABELS['default'])
        summary = (
            'Troubleshooting guide for %s: %s' % (product.name, summary)
        )
        steps = list(_TOPIC_STEPS.get(topic, _TOPIC_STEPS['default']))
        steps_title = '%s Troubleshooting Steps' % label.title()
    return {
        'kind': 'product',
        'badge': 'Product details',
        'title': product.name,
        'summary': summary,
        'first_step': '',
        'steps': steps,
        'steps_title': steps_title,
        'difficulty': '',
        'category': product.category.name if product.category else '',
        'product': product,
        'accessory': None,
        'video_url': '',
        'safety': '',
        'suggestions': [],
        'ai': False,
        'price_query': _is_price_query(query),
    }


def _accessory_answer(accessory, query, intent, topic):
    summary_parts = []
    if accessory.description:
        summary_parts.append(accessory.description.strip())
    if accessory.compatibility_notes:
        summary_parts.append('Compatibility: %s.' % accessory.compatibility_notes.strip())
    if accessory.price:
        summary_parts.append('Price: ₱%s.' % accessory.price)
    elif _is_price_query(query):
        summary_parts.append('No price is listed in the TechFix catalog.')
    if accessory.stock_quantity is not None:
        stock_text = '%s units available' % accessory.stock_quantity if accessory.stock_quantity > 0 else 'Currently out of stock'
        summary_parts.append('Stock: %s.' % stock_text)
    summary = ' '.join(summary_parts) if summary_parts else '%s is listed in the TechFix catalog.' % accessory.name
    steps = []
    steps_title = ''
    if intent == 'troubleshoot':
        label = _TOPIC_LABELS.get(topic, _TOPIC_LABELS['default'])
        summary = (
            'Troubleshooting guide for %s: %s' % (accessory.name, summary)
        )
        steps = list(_TOPIC_STEPS.get(topic, _TOPIC_STEPS['default']))
        steps_title = '%s Troubleshooting Steps' % label.title()
    return {
        'kind': 'accessory',
        'badge': 'Accessory details',
        'title': accessory.name,
        'summary': summary,
        'first_step': '',
        'steps': steps,
        'steps_title': steps_title,
        'difficulty': '',
        'category': accessory.category.name if accessory.category else '',
        'product': None,
        'accessory': accessory,
        'video_url': '',
        'safety': '',
        'suggestions': [],
        'ai': False,
        'price_query': _is_price_query(query),
    }


def _results_answer(title, summary, products=(), accessories=(), solutions=()):
    products = list(products)
    accessories = list(accessories)
    solutions = list(solutions)
    return {
        'kind': 'results',
        'badge': 'Catalog results',
        'title': title,
        'summary': summary,
        'first_step': '',
        'steps': [],
        'steps_title': '',
        'difficulty': '',
        'category': '',
        'product': None,
        'accessory': None,
        'video_url': '',
        'safety': '',
        'suggestions': [],
        'ai': False,
        'strict': True,
        'matches': {
            'products': products[:60],
            'accessories': accessories[:30],
            'solutions': solutions[:30],
        },
    }


def _catalog_results_answer(query, matched_products, matched_accessories):
    matched_products = list(matched_products)
    matched_accessories = list(matched_accessories)
    if not matched_products and not matched_accessories:
        return None
    counts = []
    if matched_products:
        counts.append(_plural(len(matched_products), 'product'))
    if matched_accessories:
        counts.append(
            _plural(len(matched_accessories), 'accessory', 'accessories')
        )
    summary = 'I found %s matching "%s" in the TechFix catalog.' % (
        ' and '.join(counts), query,
    )
    answer = _results_answer(
        query,
        summary,
        products=matched_products,
        accessories=matched_accessories,
    )
    answer['sources'] = []
    return answer


def _no_match_answer(query):
    return {
        'kind': 'fallback',
        'badge': 'No exact match',
        'title': '',
        'summary': (
            'I could not find an exact TechFix catalog match for "%s". '
            'Try the full brand and model name, for example "iPhone 17 Pro Max".'
        ) % query,
        'first_step': '',
        'steps': [],
        'steps_title': '',
        'difficulty': '',
        'category': '',
        'product': None,
        'accessory': None,
        'video_url': '',
        'safety': '',
        'suggestions': [],
        'ai': False,
        'strict': True,
        'matches': {'products': [], 'accessories': [], 'solutions': []},
    }


def _brand_answer(
    brand, products, accessories, query_tokens=None, device_tokens=None,
    accessory_type_tokens=None,
):
    query_tokens = query_tokens or set()
    device_tokens = device_tokens or set()
    accessory_type_tokens = accessory_type_tokens or set()
    brand_products = [
        item for item in products
        if (item.brand or '').lower() == brand.lower()
    ]
    brand_accessories = [
        item for item in accessories
        if (item.brand or '').lower() == brand.lower()
    ]
    wants_accessories = bool(
        query_tokens & _ACCESSORY_LIST_TOKENS or accessory_type_tokens
    )
    wants_products = bool(
        query_tokens & _PRODUCT_LIST_TOKENS
        or (device_tokens and not wants_accessories)
    )

    if not wants_products and not wants_accessories:
        return {
            'kind': 'answer',
            'badge': 'Brand overview',
            'title': brand,
            'summary': (
                '%s is available in the TechFix catalog. Tell me which %s '
                'product or accessory you need help with, or ask a question '
                'about the brand.' % (brand, brand)
            ),
            'first_step': '',
            'steps': [],
            'steps_title': '',
            'difficulty': '',
            'category': '',
            'product': None,
            'accessory': None,
            'video_url': '',
            'safety': '',
            'suggestions': [],
            'ai': False,
            'strict': False,
            'brand_overview': True,
            'matches': {'products': [], 'accessories': [], 'solutions': []},
            'sources': [],
        }

    matched_products = brand_products if wants_products else []
    matched_accessories = brand_accessories if wants_accessories else []
    if not matched_products and not matched_accessories:
        return {
            'kind': 'answer',
            'badge': 'No exact match',
            'title': brand,
            'summary': (
                'No %s items are listed in the TechFix catalog yet. Ask me '
                'about a specific model, or tell me what you need help with.'
            ) % brand,
            'first_step': '',
            'steps': [],
            'steps_title': '',
            'difficulty': '',
            'category': '',
            'product': None,
            'accessory': None,
            'video_url': '',
            'safety': '',
            'suggestions': [],
            'ai': False,
            'strict': False,
            'matches': {'products': [], 'accessories': [], 'solutions': []},
            'sources': [],
        }

    counts = []
    if matched_products:
        counts.append(_plural(len(matched_products), 'product'))
    if matched_accessories:
        counts.append(_plural(len(matched_accessories), 'accessory', 'accessories'))
    summary = 'I found %s for %s.' % (' and '.join(counts), brand)
    return _results_answer(
        brand, summary,
        products=matched_products,
        accessories=matched_accessories,
    )


def _fallback_answer(query, topic, solution_ranked, brand_hits, device_tokens,
                     identity_terms=None, brand_words=None):
    label = _TOPIC_LABELS.get(topic, _TOPIC_LABELS['default'])
    brand = brand_hits[0] if brand_hits else None
    steps = list(_TOPIC_STEPS.get(topic, _TOPIC_STEPS['default']))
    summary = (
        'Here are recommended troubleshooting instructions to resolve your %s issue. '
        'Follow these steps in order to diagnose and fix the problem:'
    ) % label
    return {
        'kind': 'fallback',
        'badge': 'Troubleshooting guide',
        'title': '%s Troubleshooting Guide' % label.title(),
        'summary': summary,
        'first_step': steps[0] if steps else '',
        'steps': steps,
        'steps_title': '%s Resolution Steps' % label.title(),
        'difficulty': '',
        'category': '',
        'product': None,
        'accessory': None,
        'video_url': '',
        'safety': '',
        'suggestions': _suggestions(
            solution_ranked, brand=brand, device_tokens=device_tokens,
            identity_terms=identity_terms, brand_words=brand_words,
        ),
        'ai': False,
    }


def _clarify_answer(solution_ranked, device_tokens, identity_terms=None,
                    brand_words=None):
    steps = list(_TOPIC_STEPS['default'])
    return {
        'kind': 'clarify',
        'badge': 'Support guide',
        'title': 'Device Troubleshooting',
        'summary': (
            'Here are standard troubleshooting steps to diagnose and resolve your device issue. '
            'For exact disassembly or part replacement, please specify your device brand and model:'
        ),
        'first_step': steps[0] if steps else '',
        'steps': steps,
        'steps_title': 'Standard Troubleshooting Steps',
        'difficulty': '',
        'category': '',
        'product': None,
        'accessory': None,
        'video_url': '',
        'safety': '',
        'suggestions': _suggestions(
            solution_ranked, device_tokens=device_tokens,
            identity_terms=identity_terms, brand_words=brand_words,
        ),
        'ai': False,
    }


def _video_help_answer():
    return {
        'kind': 'clarify',
        'badge': 'Video tutorial',
        'title': 'Find a repair video',
        'summary': (
            'Tell me the device and the problem you want to fix, and I will '
            'find a video tutorial for it. For example: "video tutorial for '
            'iPhone 12 screen flickering" or "video for laptop overheating".'
        ),
        'first_step': '',
        'steps': [],
        'steps_title': '',
        'difficulty': '',
        'category': '',
        'product': None,
        'accessory': None,
        'video_url': '',
        'safety': '',
        'suggestions': [],
        'ai': False,
    }


def _video_search_answer(query, solution_ranked, brand_hits, device_tokens,
                         identity_terms=None, brand_words=None):
    brand = brand_hits[0] if brand_hits else None
    return {
        'kind': 'fallback',
        'badge': 'Video tutorial',
        'title': 'Video tutorial for your problem',
        'summary': (
            'I do not have a saved repair-guide video for that exact problem '
            'yet. Open the link below to see YouTube video tutorials for "%s".'
        ) % query,
        'first_step': '',
        'steps': [],
        'steps_title': '',
        'difficulty': '',
        'category': '',
        'product': None,
        'accessory': None,
        'video_url': _video_search_url(query),
        'safety': '',
        'suggestions': _suggestions(
            solution_ranked, brand=brand, device_tokens=device_tokens,
            identity_terms=identity_terms, brand_words=brand_words,
        ),
        'ai': False,
    }


def _sources(solution_ranked, product_ranked, accessory_ranked, limit=5,
             identity_terms=None, brand_words=None, exact_identity=False):
    def identity_ok(tokens):
        if not identity_terms:
            return True
        if exact_identity:
            return tokens == identity_terms
        return _identity_match(tokens, identity_terms)

    sources = []
    for score, _, solution in solution_ranked:
        if score < 3 or len(sources) >= limit:
            continue
        if not identity_ok(
            _solution_identity_tokens(solution, brand_words or set())
        ):
            continue
        product = solution.related_product
        sources.append({
            'type': 'repair guide',
            'title': solution.title,
            'problem': re.sub(r'\s+', ' ', solution.problem_description or '').strip()[:600],
            'steps': re.sub(r'\s+', ' ', solution.steps or '').strip()[:1400],
            'difficulty': solution.difficulty_level,
            'device': product.name if product else '',
            'brand': product.brand if product else '',
        })
    for score, _, product in product_ranked:
        if score < 5 or len(sources) >= limit:
            continue
        if not identity_ok(
            _product_identity_tokens(product, brand_words or set())
        ):
            continue
        sources.append({
            'type': 'product',
            'name': product.name,
            'brand': product.brand,
            'category': product.category.name if product.category else '',
            'description': re.sub(r'\s+', ' ', product.description or '').strip()[:600],
            'specifications': re.sub(r'\s+', ' ', product.specifications or '').strip()[:300],
            'price': str(product.price) if product.price is not None else '',
            'source_url': product.source_url,
            'stock': product.stock_quantity,
        })
    for score, _, accessory in accessory_ranked:
        if score < 5 or len(sources) >= limit:
            continue
        if not identity_ok(
            _accessory_identity_tokens(accessory, brand_words or set())
        ):
            continue
        sources.append({
            'type': 'accessory',
            'name': accessory.name,
            'brand': accessory.brand,
            'category': accessory.category.name if accessory.category else '',
            'description': re.sub(r'\s+', ' ', accessory.description or '').strip()[:500],
            'compatibility': re.sub(
                r'\s+', ' ', accessory.compatibility_notes or ''
            ).strip()[:300],
            'price': str(accessory.price) if accessory.price is not None else '',
            'source_url': accessory.source_url,
            'stock': accessory.stock_quantity,
        })
    return sources


def build_answer(query):
    from .models import Accessory, Product, Solution

    query = (query or '').strip()
    if not query:
        return None

    solutions = list(
        Solution.objects.select_related(
            'category', 'related_product', 'related_product__category'
        )
    )
    products = list(Product.objects.select_related('category'))
    accessories = list(Accessory.objects.select_related('category'))

    brand_tokens = {}
    for item in products:
        if item.brand:
            for token in _tokens(item.brand):
                brand_tokens.setdefault(token, item.brand)
    for item in accessories:
        if item.brand:
            for token in _tokens(item.brand):
                brand_tokens.setdefault(token, item.brand)

    brand_words = _brand_words(products, accessories)
    query_identity = _query_identity_tokens(query, brand_words)
    accessory_identity = _query_identity_tokens(
        query, brand_words, drop_generic=False
    )

    identity_tokens = set()
    for item in products:
        identity_tokens |= _tokens(item.name)
    identity_tokens -= set(brand_tokens)
    identity_tokens -= _GENERIC_TOKENS
    identity_tokens -= _ISSUE_SIGNAL_TOKENS

    query_tokens = _query_tokens(query)
    query_phrase = ' '.join(_token_list(query))
    intent = _detect_intent(query)
    topic = _detect_topic(query)
    issue_signal = intent == 'troubleshoot' or bool(query_tokens & _ISSUE_SIGNAL_TOKENS)
    device_tokens = query_tokens & _DEVICE_TOKENS
    has_identity = bool(
        (query_tokens & set(brand_tokens))
        or (query_tokens & identity_tokens)
        or any(any(char.isdigit() for char in token) for token in query_tokens)
    )
    brand_hits = []
    for token in query_tokens:
        if token in brand_tokens and brand_tokens[token] not in brand_hits:
            brand_hits.append(brand_tokens[token])

    video_request = _is_video_request(query)
    problem_asked = bool(
        issue_signal
        or _looks_like_repair_request(query)
        or _VIDEO_ACTION_RE.search(_normalize(query))
    )

    family_tokens = _family_tokens(products, accessories, brand_tokens)
    if _is_general_tech_question(
        query, query_tokens, query_identity, identity_tokens, brand_tokens,
        family_tokens, products, accessories, brand_words,
    ) and not (video_request and problem_asked):
        return _general_tech_answer()

    if (
        issue_signal
        and not _has_tech_context(query, query_tokens, brand_tokens)
        and not (video_request and problem_asked)
    ):
        return _general_tech_answer()

    identity_terms = query_tokens & identity_tokens
    identity_mode = 'all'
    if not identity_terms:
        identity_terms = query_tokens & set(brand_tokens)
        identity_mode = 'any'
    if not identity_terms:
        identity_terms = {
            token for token in query_tokens if any(char.isdigit() for char in token)
        }
        identity_mode = 'any'

    solution_ranked = sorted(
        (_score_solution(item, query_tokens, query_phrase) for item in solutions),
        key=lambda item: item[0],
        reverse=True,
    )
    product_ranked = sorted(
        (_score_product(item, query_tokens, query_phrase) for item in products),
        key=lambda item: item[0],
        reverse=True,
    )
    accessory_ranked = sorted(
        (_score_accessory(item, query_tokens, query_phrase) for item in accessories),
        key=lambda item: item[0],
        reverse=True,
    )

    strict_product_ranked = [
        item for item in product_ranked
        if _identity_match(
            _product_identity_tokens(item[2], brand_words), query_identity
        )
    ]
    strict_accessory_ranked = [
        item for item in accessory_ranked
        if _identity_match(
            _accessory_identity_tokens(item[2], brand_words), accessory_identity
        )
    ]
    strict_solution_ranked = [
        item for item in solution_ranked
        if _identity_match(
            _solution_identity_tokens(item[2], brand_words), query_identity
        )
    ]

    if video_request:
        video_identity = {
            token for token in query_tokens
            if token in identity_tokens
            or any(char.isdigit() for char in token)
        }

        def has_problem_match(solution, matched):
            extra = matched - _solution_identity_tokens(solution, brand_words)
            extra -= set(brand_tokens)
            extra -= _GENERIC_TOKENS
            identity_stems = {_stem(token) for token in video_identity}
            extra = {
                token for token in extra if _stem(token) not in identity_stems
            }
            return bool(problem_asked or extra)

        issue_terms = query_tokens & _ISSUE_SIGNAL_TOKENS
        best_video = _best_video_solution(
            solution_ranked,
            brand_hits=brand_hits,
            device_tokens=device_tokens,
            identity_terms=video_identity,
            brand_words=brand_words,
            issue_terms=issue_terms,
        )
        if best_video and has_problem_match(best_video[2], best_video[1]):
            answer = _solution_answer(
                best_video[2], query, include_video=False
            )
            answer['video_url'] = best_video[2].video_url
            answer['badge'] = 'Video tutorial'
            return answer

        relaxed_video = _best_video_solution(
            solution_ranked,
            brand_hits=brand_hits,
            device_tokens=device_tokens,
            identity_terms=video_identity,
            brand_words=brand_words,
            issue_terms=issue_terms,
            require_identity=False,
            family_terms=video_identity,
        )
        if relaxed_video and has_problem_match(
            relaxed_video[2], relaxed_video[1]
        ):
            answer = _solution_answer(
                relaxed_video[2], query, include_video=False
            )
            answer['video_url'] = relaxed_video[2].video_url
            answer['badge'] = 'Video tutorial'
            if video_identity and has_identity and not _video_identity_match(
                _solution_identity_tokens(relaxed_video[2], brand_words),
                video_identity,
            ):
                answer['summary'] = (
                    'I do not have a guide for that exact model, but this '
                    'closely related tutorial covers the same problem.\n\n%s'
                ) % answer['summary']
            return answer

        if not problem_asked:
            return _video_help_answer()

        if (
            _has_tech_context(query, query_tokens, brand_tokens)
            or brand_hits
            or device_tokens
            or query_identity
        ):
            return _video_search_answer(
                query,
                solution_ranked,
                brand_hits,
                device_tokens,
                identity_terms=query_identity,
                brand_words=brand_words,
            )
        return _general_tech_answer()

    accessory_type_tokens = _accessory_type_tokens(query)

    if (
        not issue_signal
        and not query_identity
        and device_tokens
        and _RECOMMENDATION_RE.search(query)
    ):
        candidates = [
            item for item in products
            if _brand_matches(item, brand_hits)
            and _device_match(item, device_tokens)
            and item.spec_list
        ]
        if candidates:
            selected = max(
                candidates,
                key=lambda item: (
                    _recommendation_score(item),
                    item.name.casefold(),
                ),
            )
            answer = _product_answer(selected, query, intent, topic)
            device_label = (
                'phone' if 'phon' in device_tokens else 'product'
            )
            answer['badge'] = 'Recommended %s' % device_label
            answer['title'] = 'My recommendation: %s' % selected.name
            answer['summary'] = (
                'For a %s with strong listed specifications, I recommend %s: '
                '%s. %s %s'
            ) % (
                device_label,
                selected.name,
                '; '.join(selected.spec_list[:5]),
                (
                    'Listed price: ₱%s.' % selected.price
                    if selected.price is not None
                    else 'No price is listed in the catalog.'
                ),
                (
                    'It is gaming-focused, so it is best suited to users who '
                    'prioritize gaming performance.'
                    if 'redmagic' in selected.name.casefold()
                    else ''
                ),
            )
            answer['strict'] = True
            answer['sources'] = []
            return answer

    if not issue_signal and query_identity:
        strict_products = [
            item for item in strict_product_ranked
            if _brand_matches(item[2], brand_hits)
        ]
        strict_accessories = [
            item for item in strict_accessory_ranked
            if _brand_matches(item[2], brand_hits)
            and _item_has_type(item[2], accessory_type_tokens)
        ]
        products_have_type = any(
            _item_has_type(item[2], accessory_type_tokens)
            for item in strict_products
        )

        if accessory_type_tokens and not products_have_type:
            if strict_accessories:
                found = [item for _, _, item in strict_accessories]
                answer = _catalog_results_answer(query, (), found)
            else:
                relaxed_identity = {
                    token for token in query_identity
                    if not any(char.isdigit() for char in token)
                    and token not in _MODEL_WORDS
                }
                fallback_accessories = []
                for _, _, item in accessory_ranked:
                    if not _brand_matches(item, brand_hits):
                        continue
                    if not _item_has_type(item, accessory_type_tokens):
                        continue
                    item_identity = _accessory_identity_tokens(
                        item, brand_words
                    )
                    if relaxed_identity and _identity_match(
                        item_identity, relaxed_identity
                    ):
                        fallback_accessories.append(item)
                    elif not relaxed_identity and brand_hits:
                        fallback_accessories.append(item)
                if fallback_accessories:
                    answer = _catalog_results_answer(
                        query, (), fallback_accessories
                    )
                else:
                    answer = _no_match_answer(query)
            answer['sources'] = _sources(
                solution_ranked, product_ranked, accessory_ranked,
                identity_terms=accessory_identity, brand_words=brand_words,
            )
            return answer

        if strict_products:
            found = [item for _, _, item in strict_products]
            exact = [
                item for item in found
                if _product_identity_tokens(item, brand_words) == query_identity
            ]
            if len(exact) == 1 or len(found) == 1:
                selected = exact[0] if len(exact) == 1 else found[0]
                answer = _product_answer(selected, query, intent, topic)
                answer['strict'] = True
                answer['sources'] = _sources(
                    solution_ranked, product_ranked, accessory_ranked,
                    identity_terms=_product_identity_tokens(
                        selected, brand_words
                    ),
                    brand_words=brand_words,
                    exact_identity=True,
                )
            else:
                answer = _catalog_results_answer(query, found, ())
                answer['sources'] = _sources(
                    solution_ranked, product_ranked, accessory_ranked,
                    identity_terms=query_identity, brand_words=brand_words,
                )
            return answer

        if strict_accessories:
            found = [item for _, _, item in strict_accessories]
            answer = _catalog_results_answer(query, (), found)
            answer['sources'] = _sources(
                solution_ranked, product_ranked, accessory_ranked,
                identity_terms=accessory_identity, brand_words=brand_words,
            )
            return answer

        answer = _no_match_answer(query)
        answer['sources'] = []
        return answer

    if not issue_signal and not query_identity:
        if accessory_type_tokens:
            matched_products = [
                item for item in products
                if _brand_matches(item, brand_hits)
                and _item_has_type(item, accessory_type_tokens)
            ]
            matched_accessories = [
                item for item in accessories
                if _brand_matches(item, brand_hits)
                and _item_has_type(item, accessory_type_tokens)
            ]
            named_products = [
                item for item in matched_products
                if _item_has_type_name(item, accessory_type_tokens)
            ]
            named_accessories = [
                item for item in matched_accessories
                if _item_has_type_name(item, accessory_type_tokens)
            ]
            if named_products or named_accessories:
                matched_products = named_products
                matched_accessories = named_accessories
            answer = _catalog_results_answer(
                query, matched_products, matched_accessories
            )
            if answer is not None:
                return answer

        if device_tokens:
            matched_products = [
                item for item in products
                if _brand_matches(item, brand_hits)
                and _device_match(item, device_tokens)
            ]
            matched_accessories = []
            if query_tokens & _ACCESSORY_LIST_TOKENS:
                matched_accessories = [
                    item for item in accessories
                    if _brand_matches(item, brand_hits)
                    and _device_match(item, device_tokens)
                ]
                matched_products = []
            answer = _catalog_results_answer(
                query, matched_products, matched_accessories
            )
            if answer is not None:
                return answer

    solution_pool = strict_solution_ranked if query_identity else solution_ranked
    product_pool = strict_product_ranked if query_identity else product_ranked
    accessory_pool = (
        strict_accessory_ranked if query_identity else accessory_ranked
    )

    best_solution = solution_pool[0] if solution_pool else None
    issue_terms = query_tokens & _ISSUE_SIGNAL_TOKENS
    if issue_terms:
        best_solution = next(
            (item for item in solution_pool if item[1] & issue_terms),
            None,
        )
    best_product = product_pool[0] if product_pool else None
    best_accessory = accessory_pool[0] if accessory_pool else None

    solution_ready = bool(
        best_solution
        and has_identity
        and issue_signal
        and best_solution[0] >= 7
        and _is_specific(best_solution[1], brand_tokens)
    )
    product_ready = bool(
        best_product
        and has_identity
        and best_product[0] >= 7
        and _is_specific(best_product[1], brand_tokens)
    )
    accessory_ready = bool(
        best_accessory
        and has_identity
        and best_accessory[0] >= 7
        and _is_specific(best_accessory[1], brand_tokens)
    )

    answer_intent = (
        'troubleshoot' if issue_signal and intent != 'lookup' else intent
    )

    if intent == 'lookup' and product_ready:
        answer = _product_answer(best_product[2], query, answer_intent, topic)
    elif solution_ready and (intent == 'troubleshoot' or issue_signal):
        answer = _solution_answer(best_solution[2], query)
    elif product_ready:
        answer = _product_answer(best_product[2], query, answer_intent, topic)
    elif accessory_ready:
        answer = _accessory_answer(
            best_accessory[2], query, answer_intent, topic
        )
    elif brand_hits and not issue_signal:
        answer = _brand_answer(
            brand_hits[0], products, accessories,
            query_tokens=query_tokens,
            device_tokens=device_tokens,
            accessory_type_tokens=accessory_type_tokens,
        )
        if answer.get('kind') != 'results':
            return answer
    elif issue_signal:
        answer = _fallback_answer(
            query, topic, solution_ranked, brand_hits, device_tokens,
            identity_terms=query_identity, brand_words=brand_words,
        )
    else:
        answer = _clarify_answer(
            solution_ranked, device_tokens,
            identity_terms=query_identity, brand_words=brand_words,
        )

    if answer.get('steps') and not answer.get('video_url'):
        answer['video_url'] = _tutorial_video(
            solution_ranked,
            brand_hits=brand_hits,
            device_tokens=device_tokens,
            identity_terms=query_identity if has_identity else None,
            brand_words=brand_words,
            issue_terms=query_tokens & _ISSUE_SIGNAL_TOKENS,
            query=query,
        )

    if answer.get('kind') != 'results':
        answer['matches'] = {
            'products': [
                item for score, matched, item in product_pool
                if score >= 6
                and _is_specific(matched, brand_tokens)
                and _identity_ok(matched, identity_terms, identity_mode)
                and _device_match(item, device_tokens)
            ][:60],
            'accessories': [
                item for score, matched, item in accessory_pool
                if score >= 6
                and _is_specific(matched, brand_tokens)
                and _identity_ok(matched, identity_terms, identity_mode)
                and _device_match(item, device_tokens)
            ][:60],
            'solutions': [
                item for score, matched, item in solution_pool
                if score >= 5
                and _is_specific(matched, brand_tokens)
                and _identity_ok(matched, identity_terms, identity_mode)
                and _device_match(item.related_product, device_tokens)
            ][:60],
        }

    answer['sources'] = _sources(
        solution_pool, product_pool, accessory_pool,
        identity_terms=query_identity, brand_words=brand_words,
    )
    return answer


def _is_specific(matched, brand_tokens):
    return any(
        token not in _GENERIC_TOKENS and token not in brand_tokens
        for token in matched
    )


def _identity_ok(matched, identity_terms, identity_mode):
    if not identity_terms:
        return True
    if identity_mode == 'all':
        return identity_terms <= matched
    return bool(identity_terms & matched)
