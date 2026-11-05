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
    'You are TechFix Assistant, a precise, knowledgeable technical assistant for TechFix. '
    'Answer any technology-related question accurately and directly, with a focus on '
    'technology, gadgets, and consumer electronics.\n\n'
    'You must handle:\n'
    '1. Devices and gadgets: smartphones, tablets, laptops, desktop PCs, TVs, monitors, '
    'printers, routers and networking, audio devices, wearables, cameras, gaming consoles, '
    'smart-home devices, storage, components, accessories, and other consumer electronics.\n'
    '2. Buying advice and comparisons: recommend specific models or categories by budget and '
    'use case. For comparisons, give a clear verdict, the key differences, and honest trade-offs.\n'
    '3. General technology knowledge: explain concepts such as SSD vs HDD, RAM, CPU/GPU, Wi-Fi, '
    '5G, OLED vs LCD, operating systems, cybersecurity, AI, maintenance, and cleaning.\n'
    '4. Troubleshooting and repair: identify the likely cause and give concrete numbered steps '
    'for hardware and software problems.\n'
    '5. TechFix catalog, products, pricing, stock, compatibility, and platform navigation: when '
    'TechFix catalog data is provided, it is the source of truth. Quote exact prices and stock; '
    'never invent or guess a TechFix price, stock value, or product specification.\n\n'
    'Guidelines for answers:\n'
    '- Be direct, specific, and technically accurate. Address the question immediately.\n'
    '- Use exact model names, standards, and measurable details where they matter. If a fact is '
    'unknown or varies by model or region, say so briefly rather than inventing it.\n'
    '- For repair or troubleshooting questions, explain the likely cause in summary and provide '
    '3-6 concrete numbered steps. Include a practical safety warning for batteries, electricity, '
    'or opened hardware.\n'
    '- For concepts, comparisons, recommendations, and price or product questions where steps are '
    'not needed, put the complete answer in summary and leave steps empty ([]).\n'
    '- For buying advice, give practical selection criteria and at least one or two specific '
    'examples when possible; state the trade-offs honestly.\n'
    '- Do not use generic disclaimer boilerplate like "this advice is general". Give specific '
    'instructions and mention model differences directly when relevant.\n'
    '- Do not answer non-technology requests. Set is_tech true for every technology, gadget, '
    'software, repair, buying, or TechFix question. Set is_tech false only when the request is '
    'unrelated to technology (for example recipes, sports, politics, or creative writing). For '
    'those, politely explain that you focus on technology and invite a tech question; do not '
    'provide the requested non-tech answer.\n'
    '- For a related follow-up, use the conversation history only to understand its context. '
    'Answer the newest question directly and do not repeat or summarize the previous answer '
    'unless the user asks you to.\n'
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
            'Specifications: %s\n'
            'Official product page: %s'
        ) % (
            index,
            source.get('name', ''),
            source.get('brand', ''),
            source.get('category', ''),
            source.get('price') or 'not listed',
            source.get('stock') if source.get('stock') is not None else 'not listed',
            source.get('description', ''),
            source.get('specifications', ''),
            source.get('source_url', ''),
        )
    return (
        '[%s] Accessory: %s\n'
        'Brand: %s | Category: %s | Price: %s | Stock: %s\n'
        'Description: %s\n'
        'Compatibility: %s\n'
        'Official product page: %s'
    ) % (
        index,
        source.get('name', ''),
        source.get('brand', ''),
        source.get('category', ''),
        source.get('price') or 'not listed',
        source.get('stock') if source.get('stock') is not None else 'not listed',
        source.get('description', ''),
        source.get('compatibility', ''),
        source.get('source_url', ''),
    )


def _build_prompt(question, sources, history_included=False):
    lines = ['User question: %s' % question, '']
    if history_included:
        lines.append(
            'The earlier conversation is context only. Answer only the user\'s latest question. '
            'Use prior messages to understand what they mean, but do not repeat or summarize '
            'earlier answers unless the user asks.'
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
