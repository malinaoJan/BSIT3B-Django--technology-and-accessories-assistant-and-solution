"""Question answering for the TechFix assistant.

The engine matches a free-text question against repair guides, products and
accessories, then returns a specific answer with numbered steps. Gemini can
enrich the result through ``apps.core.gemini``; the local answer remains the
fallback when the API is unavailable.
"""

import re

TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9\-]*")
STEP_RE = re.compile(r"(?:^|[\s\n])(?:step\s*)?(\d{1,2})[.)]\s+", re.IGNORECASE)

_STOPWORDS = frozenset("""
a an the and or but if then than so because as of to in on at by for with from
into over under about after before during while when where who whom which what
why how is are was were be been being am do does did doing done have has had
having can could should would will shall may might must i me my mine we us our
you your he him his she her it its they them their this that these those there
here not no yes nor too very really just only also even still again ever never
always sometimes now once please help someone tell know want need like get got
gets make makes made use using used try trying tried fix fixes fixed repair
repairs solution solutions troubleshoot troubleshooting problem problems issue
issues keeps keep kept starts started start stops stopped stop working works
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
        if drop_generic and (raw in _GENERIC_TOKENS or stem in _GENERIC_TOKENS):
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


def _has_accessory_intent(query):
    for token in _strict_tokens(query, drop_generic=False):
        if token in _ACCESSORY_QUERY_WORDS or _stem(token) in _ACCESSORY_QUERY_WORDS:
            return True
    return False


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


def _detect_intent(query):
    text = _normalize(query)
    if any(word in text for word in _PRODUCT_LOOKUP_WORDS):
        return 'lookup'
    if any(word in text for word in _TROUBLE_WORDS):
        return 'troubleshoot'
    return 'general'


def _detect_topic(query):
    text = _normalize(query)
    for topic, patterns in _TOPIC_PATTERNS:
        if any(re.search(pattern, text) for pattern in patterns):
            return topic
    return 'default'


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


def _solution_answer(solution):
    steps = _split_steps(solution.steps)
    return {
        'kind': 'solution',
        'badge': 'Repair guide',
        'title': solution.title,
        'summary': (solution.problem_description or '').strip(),
        'first_step': steps[0] if steps else '',
        'steps': steps,
        'steps_title': 'Step-by-step process' if steps else '',
        'difficulty': solution.difficulty_level,
        'category': solution.category.name if solution.category else '',
        'product': solution.related_product,
        'accessory': None,
        'video_url': solution.video_url,
        'safety': '',
        'suggestions': [],
        'ai': False,
    }


def _product_answer(product, query, intent, topic):
    summary = (product.description or '').strip()
    if not summary:
        summary = '%s is listed in the TechFix catalog.' % product.name
    steps = []
    steps_title = ''
    if intent == 'troubleshoot':
        label = _TOPIC_LABELS.get(topic, _TOPIC_LABELS['default'])
        summary = (
            'I could not find an exact repair guide for this issue, but here is the '
            '%s. %s' % (product.name, summary)
        )
        steps = list(_TOPIC_STEPS.get(topic, _TOPIC_STEPS['default']))
        steps_title = 'General %s steps' % label
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
    summary = (accessory.description or '').strip()
    if accessory.compatibility_notes:
        summary = (summary + ' ' + accessory.compatibility_notes).strip()
    if not summary:
        summary = '%s is listed in the TechFix catalog.' % accessory.name
    steps = []
    steps_title = ''
    if intent == 'troubleshoot':
        label = _TOPIC_LABELS.get(topic, _TOPIC_LABELS['default'])
        summary = (
            'I could not find an exact repair guide for this accessory issue, but here is '
            'the %s. %s' % (accessory.name, summary)
        )
        steps = list(_TOPIC_STEPS.get(topic, _TOPIC_STEPS['default']))
        steps_title = 'General %s steps' % label
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


def _brand_answer(brand, products, accessories):
    brand_products = [
        item for item in products
        if (item.brand or '').lower() == brand.lower()
    ]
    brand_accessories = [
        item for item in accessories
        if (item.brand or '').lower() == brand.lower()
    ]
    summary = 'I found %s and %s for %s.' % (
        _plural(len(brand_products), 'product'),
        _plural(len(brand_accessories), 'accessory', 'accessories'),
        brand,
    )
    return _results_answer(
        brand, summary,
        products=brand_products,
        accessories=brand_accessories,
    )


def _fallback_answer(query, topic, solution_ranked, brand_hits, device_tokens,
                     identity_terms=None, brand_words=None):
    label = _TOPIC_LABELS.get(topic, _TOPIC_LABELS['default'])
    brand = brand_hits[0] if brand_hits else None
    steps = list(_TOPIC_STEPS.get(topic, _TOPIC_STEPS['default']))
    summary = (
        'I could not find an exact repair guide for "%s" in the TechFix catalog. '
        'Here are general %s steps you can try. For a device-specific fix, include '
        'the brand and model in your question.'
    ) % (query, label)
    return {
        'kind': 'fallback',
        'badge': 'General guidance',
        'title': '',
        'summary': summary,
        'first_step': '',
        'steps': steps,
        'steps_title': 'General %s steps' % label,
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
    return {
        'kind': 'clarify',
        'badge': 'Tell me more',
        'title': '',
        'summary': (
            'Tell me the device brand and model plus what is happening, for example '
            '"Sony Xperia L will not charge". Then I can give you the exact answer and '
            'step-by-step fix.'
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
        'suggestions': _suggestions(
            solution_ranked, device_tokens=device_tokens,
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
            'price': str(product.price),
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
            'price': str(accessory.price),
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

    if not issue_signal and query_identity:
        if _has_accessory_intent(query):
            if strict_accessory_ranked:
                found = [item for _, _, item in strict_accessory_ranked]
                answer = _results_answer(
                    query,
                    'I found %s matching "%s" in the TechFix catalog.' % (
                        _plural(len(found), 'accessory', 'accessories'), query,
                    ),
                    accessories=found,
                )
            else:
                answer = _no_match_answer(query)
            answer['sources'] = _sources(
                solution_ranked, product_ranked, accessory_ranked,
                identity_terms=accessory_identity, brand_words=brand_words,
            )
            return answer

        if strict_product_ranked:
            found = [item for _, _, item in strict_product_ranked]
            exact = [
                item for item in found
                if _product_identity_tokens(item, brand_words) == query_identity
            ]
            if len(exact) == 1 or len(found) == 1:
                selected = exact[0] if len(exact) == 1 else found[0]
                answer = _product_answer(selected, query, intent, topic)
                answer['sources'] = _sources(
                    solution_ranked, product_ranked, accessory_ranked,
                    identity_terms=_product_identity_tokens(
                        selected, brand_words
                    ),
                    brand_words=brand_words,
                    exact_identity=True,
                )
            else:
                answer = _results_answer(
                    query,
                    'I found %s matching "%s" in the TechFix catalog.' % (
                        _plural(len(found), 'product'), query,
                    ),
                    products=found,
                )
                answer['sources'] = _sources(
                    solution_ranked, product_ranked, accessory_ranked,
                    identity_terms=query_identity, brand_words=brand_words,
                )
            return answer

        if strict_accessory_ranked:
            found = [item for _, _, item in strict_accessory_ranked]
            answer = _results_answer(
                query,
                'I found %s matching "%s" in the TechFix catalog.' % (
                    _plural(len(found), 'accessory', 'accessories'), query,
                ),
                accessories=found,
            )
            answer['sources'] = _sources(
                solution_ranked, product_ranked, accessory_ranked,
                identity_terms=accessory_identity, brand_words=brand_words,
            )
            return answer

        answer = _no_match_answer(query)
        answer['sources'] = []
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
        answer = _solution_answer(best_solution[2])
    elif product_ready:
        answer = _product_answer(best_product[2], query, answer_intent, topic)
    elif accessory_ready:
        answer = _accessory_answer(
            best_accessory[2], query, answer_intent, topic
        )
    elif brand_hits:
        answer = _brand_answer(brand_hits[0], products, accessories)
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
