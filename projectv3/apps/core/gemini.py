"""Gemini-powered answers for the TechFix chat box."""

import json
import logging
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.conf import settings

logger = logging.getLogger(__name__)

_API_ROOT = 'https://generativelanguage.googleapis.com/v1beta/models'

_SYSTEM_PROMPT = (
    'You are TechFix Assistant, the intelligent technical support assistant for TechFix. '
    'Your mission is to provide users with specific, accurate, and direct answers to any question '
    'they ask in the chatbox.\n\n'
    'You specialize in and should answer:\n'
    '1. Device Troubleshooting & Repairs: For hardware and software issues with smartphones, '
    'laptops, desktop PCs, tablets, TVs/monitors, printers, routers, audio devices, gaming consoles, '
    'and accessories, explain the likely cause and provide concrete, actionable, numbered steps.\n'
    '2. TechFix Catalog, Products & Pricing: When TechFix catalog data is provided, use it as the source '
    'of truth for products, accessories, specs, stock, and prices. Quote exact prices and stock when asked.\n'
    '3. TechFix Platform & Navigation: Explain TechFix features, such as browsing products, checking '
    'accessory compatibility, viewing repair guides, and diagnosing tech problems.\n'
    '4. General Technology Knowledge: Clearly explain tech concepts (e.g., SSD vs HDD, RAM, Wi-Fi 6, '
    'OLED vs LCD, OS updates, maintenance, and cleaning).\n'
    '5. Greetings & Support: Greet users warmly and explain how you can help them.\n\n'
    'Guidelines for Answers:\n'
    '- Always be direct, specific, and helpful. Address the user\'s question immediately.\n'
    '- Never use generic disclaimer boilerplate like "Since I do not have specific information about '
    'your device model, please note that this advice is general". Instead, give specific instructions and '
    'mention model differences directly if relevant.\n'
    '- For repair or troubleshooting questions, provide a clear explanation in summary, followed by '
    '3-6 concrete numbered steps in the steps array.\n'
    '- For informational, conceptual, price, or product questions where troubleshooting steps are not '
    'needed, provide the complete specific answer in summary and leave steps empty ([]).\n'
    '- Set is_tech to true for all technology, hardware, software, gadgets, repair, and TechFix questions. '
    'Only set is_tech to false if the question is completely unrelated to technology or the TechFix system '
    '(e.g., cooking recipes, creative writing, sports). For non-tech questions, politely explain that you '
    'are dedicated to technology and device repair assistance.\n'
    '- Always return valid JSON matching the schema.'
)

_RESPONSE_SCHEMA = {
    'type': 'OBJECT',
    'properties': {
        'is_tech': {'type': 'BOOLEAN'},
        'title': {'type': 'STRING'},
        'summary': {'type': 'STRING'},
        'steps': {'type': 'ARRAY', 'items': {'type': 'STRING'}},
        'difficulty': {'type': 'STRING'},
        'safety': {'type': 'STRING'},
    },
    'required': ['is_tech', 'title', 'summary', 'steps'],
}


def _source_block(source, index):
    kind = source.get('type', 'item')
    if kind == 'repair guide':
        return (
            '[%s] Repair guide: %s\n'
            'Problem: %s\n'
            'Difficulty: %s\n'
            'Device: %s\n'
            'Brand: %s\n'
            'Steps: %s'
        ) % (
            index,
            source.get('title', ''),
            source.get('problem', ''),
            source.get('difficulty', ''),
            source.get('device', ''),
            source.get('brand', ''),
            source.get('steps', ''),
        )
    if kind == 'product':
        return (
            '[%s] Product: %s\n'
            'Brand: %s | Category: %s | Price: %s | Stock: %s\n'
            'Description: %s\n'
            'Specifications: %s'
        ) % (
            index,
            source.get('name', ''),
            source.get('brand', ''),
            source.get('category', ''),
            source.get('price', ''),
            source.get('stock', ''),
            source.get('description', ''),
            source.get('specifications', ''),
        )
    return (
        '[%s] Accessory: %s\n'
        'Brand: %s | Category: %s | Price: %s | Stock: %s\n'
        'Description: %s\n'
        'Compatibility: %s'
    ) % (
        index,
        source.get('name', ''),
        source.get('brand', ''),
        source.get('category', ''),
        source.get('price', ''),
        source.get('stock', ''),
        source.get('description', ''),
        source.get('compatibility', ''),
    )


def _build_prompt(question, sources, history_included=False):
    lines = ['User question: %s' % question, '']
    if history_included:
        lines.append(
            'The earlier conversation is above. Use it to resolve follow-up '
            'questions. Do not repeat earlier answers unless the user asks you to.'
        )
        lines.append('')
    if sources:
        lines.append('Relevant TechFix catalog data:')
        for index, source in enumerate(sources[:5], 1):
            lines.append(_source_block(source, index))
            lines.append('')
        lines.append(
            'When the question asks about products, pricing, stock, compatibility, or repair guides, '
            'quote the relevant confirmed TechFix data accurately in your answer.'
        )
    else:
        lines.append(
            'Answer using your technical knowledge. Give a direct, specific, and actionable answer '
            'to the user\'s question.'
        )
    lines.append('')
    lines.append(
        'Format your response in JSON according to the schema:\n'
        '- title: A concise, descriptive title for the answer.\n'
        '- summary: The specific, direct answer to the user\'s question (1-3 clear paragraphs as needed).\n'
        '- steps: If the question asks for a repair, fix, troubleshooting, or procedure, provide 3 to 6 '
        'concrete, actionable numbered steps. If it is an informational, conceptual, or price question, '
        'leave steps as an empty array [].\n'
        '- difficulty: Easy, Medium, or Hard if steps are provided; otherwise omit or leave blank.\n'
        '- safety: A short practical safety caution if handling electricity, batteries, or opened hardware; '
        'otherwise leave blank.\n'
        '- is_tech: true for all tech, electronics, repair, and TechFix platform questions; false only for '
        'completely non-tech topics.'
    )
    return '\n'.join(lines)


def _history_contents(history):
    contents = []
    for item in (history or [])[-8:]:
        if not isinstance(item, dict):
            continue
        role = item.get('role')
        if role == 'user':
            text = str(item.get('text') or '').strip()
            if text:
                contents.append({
                    'role': 'user',
                    'parts': [{'text': text[:3000]}],
                })
        elif role == 'assistant':
            answer = item.get('answer')
            if not isinstance(answer, dict):
                continue
            text = str(answer.get('summary') or '').strip()
            steps = answer.get('steps') or []
            if steps:
                text = '%s\nSteps: %s' % (
                    text, '; '.join(str(step) for step in steps[:6])
                )
            if text:
                contents.append({
                    'role': 'model',
                    'parts': [{'text': text[:3000]}],
                })
    return contents


def _extract_text(data):
    candidates = data.get('candidates') or []
    if not candidates:
        return ''
    parts = (candidates[0].get('content') or {}).get('parts') or []
    text = ''.join(
        part.get('text', '')
        for part in parts
        if not part.get('thought')
    ).strip()
    if text.startswith('```'):
        lines = text.splitlines()
        if lines and lines[0].startswith('```'):
            lines = lines[1:]
        if lines and lines[-1].strip() == '```':
            lines = lines[:-1]
        text = '\n'.join(lines).strip()
    return text


def _model_candidates():
    configured = str(
        getattr(settings, 'GEMINI_MODEL', 'gemini-3.1-flash-lite') or ''
    ).strip()
    candidates = [configured] if configured else []
    fallbacks = getattr(settings, 'GEMINI_FALLBACK_MODELS', ())
    if isinstance(fallbacks, str):
        fallbacks = fallbacks.split(',')
    for model in fallbacks or ():
        model = str(model or '').strip()
        if model and model not in candidates:
            candidates.append(model)
    return candidates


def _request_gemini(model, key, payload):
    request = urllib.request.Request(
        '%s/%s:generateContent' % (_API_ROOT, model),
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json', 'x-goog-api-key': key},
        method='POST',
    )
    with urllib.request.urlopen(request, timeout=25) as response:
        return json.load(response)


def _parse_gemini_data(data, model):
    text = _extract_text(data)
    if not text:
        logger.warning('Gemini returned no text for %s', model)
        return None
    try:
        parsed = json.loads(text)
    except ValueError as exc:
        logger.warning('Gemini returned invalid JSON for %s: %s', model, exc)
        return None
    if not isinstance(parsed, dict):
        logger.warning('Gemini returned an unexpected payload for %s', model)
        return None

    summary = str(parsed.get('summary') or '').strip()
    if not summary:
        logger.warning('Gemini returned no summary for %s', model)
        return None
    steps = parsed.get('steps') or []
    if not isinstance(steps, list):
        steps = []
    steps = [str(step).strip() for step in steps if str(step).strip()][:8]
    is_tech = parsed.get('is_tech', True)
    if not isinstance(is_tech, bool):
        is_tech = str(is_tech).strip().lower() not in ('false', '0', 'no')
    difficulty = str(parsed.get('difficulty') or '').strip()
    difficulty = difficulty.title() if difficulty.lower() in ('easy', 'medium', 'hard') else ''
    return {
        'is_tech': is_tech,
        'title': str(parsed.get('title') or '').strip(),
        'summary': summary,
        'steps': steps,
        'difficulty': difficulty,
        'safety': str(parsed.get('safety') or '').strip(),
    }


def _ask_model(model, key, payload):
    try:
        data = _request_gemini(model, key, payload)
    except urllib.error.HTTPError as exc:
        logger.warning('Gemini request failed for %s: HTTP %s', model, exc.code)
        return None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        logger.warning('Gemini request failed for %s: %s', model, exc)
        return None
    except Exception as exc:
        logger.warning('Gemini request failed for %s: %s', model, exc)
        return None
    return _parse_gemini_data(data, model)


def ask_gemini(question, sources, history=None):
    key = getattr(settings, 'GEMINI_API_KEY', '')
    if not key:
        return None
    contents = _history_contents(history)
    contents.append({
        'role': 'user',
        'parts': [{
            'text': _build_prompt(question, sources, history_included=bool(contents))
        }],
    })
    payload = {
        'systemInstruction': {'parts': [{'text': _SYSTEM_PROMPT}]},
        'contents': contents,
        'generationConfig': {
            'temperature': 0.25,
            'maxOutputTokens': 1500,
            'responseMimeType': 'application/json',
            'responseSchema': _RESPONSE_SCHEMA,
        },
    }

    models = _model_candidates()
    for model in models:
        result = _ask_model(model, key, payload)
        if result:
            return result
    return None


def _empty_answer():
    return {
        'kind': 'fallback',
        'badge': 'AI answer',
        'title': '',
        'summary': '',
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
        'ai': True,
        'matches': {'products': [], 'accessories': [], 'solutions': []},
        'sources': [],
        'notice': '',
    }


def _off_topic_answer(data):
    result = _empty_answer()
    result['badge'] = 'TechFix only'
    result['summary'] = data.get('summary') or (
        'I can only help with technology, gadgets, accessories and technical '
        'solutions. Ask me about a device or a tech problem and I will help.'
    )
    result['steps'] = []
    result['title'] = ''
    return result


def _merge_ai_answer(answer, data):
    merged = dict(answer) if answer else _empty_answer()
    merged['summary'] = data.get('summary') or merged.get('summary', '')
    steps = data.get('steps') or []
    merged['steps'] = steps
    merged['steps_title'] = 'Step-by-step process' if steps else ''
    merged['first_step'] = ''
    merged['safety'] = data.get('safety') or merged.get('safety', '')
    if data.get('difficulty'):
        merged['difficulty'] = data['difficulty']
    if data.get('title'):
        merged['title'] = data['title']
    elif not merged.get('title'):
        merged['title'] = 'TechFix Support'

    if merged.get('kind') in ('clarify', 'fallback'):
        merged['kind'] = 'solution' if steps else 'answer'

    merged['ai'] = True
    merged['badge'] = (
        'AI repair answer'
        if merged.get('kind') == 'solution' and steps
        else 'AI answer'
    )
    merged['notice'] = ''
    return merged


def enhance_answer(question, answer, history=None):
    """Answer with Gemini, falling back to the local catalog answer if needed."""
    answer = answer or {}
    data = ask_gemini(
        question, answer.get('sources', []), history=history
    )
    if not data:
        if not answer:
            return None
        fallback = dict(answer)
        fallback['notice'] = (
            'AI is temporarily unavailable, so this answer uses TechFix built-in '
            'guidance.'
        )
        return fallback
    if not data.get('is_tech', True):
        return _off_topic_answer(data)
    return _merge_ai_answer(answer, data)
