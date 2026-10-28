"""Gemini-powered answers for the TechFix chat box."""

import json
import logging
import urllib.error
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)

_API_ROOT = 'https://generativelanguage.googleapis.com/v1beta/models'

_SYSTEM_PROMPT = (
    'You are TechFix Assistant, a practical technology repair and accessories '
    'expert. Answer the user question directly and specifically. When catalog '
    'sources are provided, base the answer on the best matching repair guide and '
    'keep its concrete details. When no relevant source is provided, give safe '
    'general troubleshooting advice and say it is general. Never invent prices, '
    'part numbers or model-specific facts. Do not claim to be ChatGPT or Gemini. '
    'Return valid JSON only.'
)

_RESPONSE_SCHEMA = {
    'type': 'OBJECT',
    'properties': {
        'title': {'type': 'STRING'},
        'summary': {'type': 'STRING'},
        'steps': {'type': 'ARRAY', 'items': {'type': 'STRING'}},
        'difficulty': {'type': 'STRING'},
        'safety': {'type': 'STRING'},
    },
    'required': ['title', 'summary', 'steps'],
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


def _build_prompt(question, sources):
    lines = ['User question: %s' % question, '']
    if sources:
        lines.append('Relevant TechFix catalog data:')
        for index, source in enumerate(sources[:5], 1):
            lines.append(_source_block(source, index))
            lines.append('')
        lines.append(
            'Use the best matching catalog entry as the primary source. If the '
            'question is about a different device, adapt the steps carefully and '
            'do not copy unrelated model details.'
        )
    else:
        lines.append(
            'No matching catalog entry was found. Give safe, general '
            'troubleshooting steps and state that the advice is general.'
        )
    lines.append('')
    lines.append(
        'Return a short title, a 1-3 sentence specific answer in summary, 3-6 '
        'concrete ordered steps, a difficulty of Easy, Medium or Hard, and a short '
        'safety note when needed. If the question only asks for a price, specs, '
        'stock or availability, put the details in summary and return an empty '
        'steps array instead of repair steps.'
    )
    return '\n'.join(lines)


def _extract_text(data):
    candidates = data.get('candidates') or []
    if not candidates:
        return ''
    parts = (candidates[0].get('content') or {}).get('parts') or []
    return ''.join(part.get('text', '') for part in parts).strip()


def ask_gemini(question, sources):
    key = getattr(settings, 'GEMINI_API_KEY', '')
    if not key:
        return None
    model = getattr(settings, 'GEMINI_MODEL', 'gemini-3.1-flash-lite')
    payload = {
        'systemInstruction': {'parts': [{'text': _SYSTEM_PROMPT}]},
        'contents': [{'role': 'user', 'parts': [{'text': _build_prompt(question, sources)}]}],
        'generationConfig': {
            'temperature': 0.25,
            'maxOutputTokens': 900,
            'responseMimeType': 'application/json',
            'responseSchema': _RESPONSE_SCHEMA,
        },
    }
    request = urllib.request.Request(
        '%s/%s:generateContent' % (_API_ROOT, model),
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json', 'x-goog-api-key': key},
        method='POST',
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.load(response)
        text = _extract_text(data)
        if not text:
            return None
        parsed = json.loads(text)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError, KeyError) as exc:
        logger.warning('Gemini request failed: %s', exc)
        return None
    except Exception as exc:
        logger.warning('Gemini request failed: %s', exc)
        return None

    summary = str(parsed.get('summary') or '').strip()
    if not summary:
        return None
    steps = parsed.get('steps') or []
    if not isinstance(steps, list):
        steps = []
    steps = [str(step).strip() for step in steps if str(step).strip()][:8]
    return {
        'title': str(parsed.get('title') or '').strip(),
        'summary': summary,
        'steps': steps,
        'difficulty': str(parsed.get('difficulty') or '').strip(),
        'safety': str(parsed.get('safety') or '').strip(),
    }


def enhance_answer(question, answer):
    if not answer or answer.get('kind') == 'clarify':
        return answer
    data = ask_gemini(question, answer.get('sources', []))
    if not data:
        return answer
    merged = dict(answer)
    merged['summary'] = data['summary']
    if data.get('steps'):
        merged['steps'] = data['steps']
    merged['steps_title'] = 'Step-by-step process' if merged.get('steps') else ''
    merged['first_step'] = ''
    merged['safety'] = data.get('safety', '')
    if data.get('difficulty'):
        merged['difficulty'] = data['difficulty']
    if data.get('title') and not merged.get('title'):
        merged['title'] = data['title']
    merged['ai'] = True
    merged['badge'] = (
        'AI repair answer' if merged.get('kind') == 'solution' else 'AI answer'
    )
    return merged
