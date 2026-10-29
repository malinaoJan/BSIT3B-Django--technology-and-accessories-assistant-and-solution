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
    'You are TechFix Assistant, the technology support assistant for TechFix. '
    'Help only with technology topics: computers, phones, tablets, TVs, cameras, '
    'printers, routers, audio gear, gaming devices, accessories, repairs, '
    'troubleshooting, setup, compatibility and tech buying advice. If the request '
    'is unrelated to technology, set is_tech to false and politely say you only '
    'help with technology. Use the conversation history to understand follow-up '
    'questions such as "it", "that device" or "what about the battery". When '
    'TechFix catalog data is provided, treat it as the only source of product '
    'specifications, compatibility and prices. Never invent or guess '
    'specifications, model-specific compatibility, part numbers, stock or prices. '
    'If the catalog does not contain a detail, say you do not have confirmed '
    'information and give safe general guidance instead. Answer only about the '
    'exact device, model or item named in the user question. Do not list or '
    'discuss other devices or models unless the user explicitly asks for '
    'alternatives. Do not claim to be ChatGPT or Gemini. Return valid JSON only.'
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
            'Use the best matching catalog entry as the primary source. Answer '
            'only about the exact device, model or item named in the user '
            'question. Do not list, compare or mention other devices or models '
            'unless the user explicitly asks for alternatives. Do not copy '
            'unrelated model details.'
        )
    else:
        lines.append(
            'No matching catalog entry was found. Give safe, general '
            'troubleshooting steps and state that the advice is general. Do not '
            'guess TechFix product specs, compatibility, stock or prices.'
        )
    lines.append('')
    lines.append(
        'Return is_tech true only when the request is about technology, gadgets, '
        'accessories or technical solutions. Otherwise set is_tech false, give a '
        'short polite refusal in summary, and return an empty steps array. For '
        'technology questions return a short title, a 1-3 sentence specific answer '
        'in summary, 3-6 concrete ordered steps, a difficulty of Easy, Medium or '
        'Hard, and a short safety note when needed. If the question only asks for '
        'a price, specs, stock or availability, put the details in summary and '
        'return an empty steps array instead of repair steps.'
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
            'maxOutputTokens': 900,
            'responseMimeType': 'application/json',
            'responseSchema': _RESPONSE_SCHEMA,
        },
    }

    models = _model_candidates()
    if not models:
        return None
    if len(models) == 1:
        return _ask_model(models[0], key, payload)

    executor = ThreadPoolExecutor(max_workers=len(models))
    futures = [
        executor.submit(_ask_model, model, key, payload)
        for model in models
    ]
    try:
        for future in as_completed(futures, timeout=30):
            try:
                result = future.result()
            except Exception as exc:
                logger.warning('Gemini worker failed: %s', exc)
                continue
            if result:
                return result
    except TimeoutError:
        logger.warning('Gemini requests timed out')
    finally:
        executor.shutdown(wait=False, cancel_futures=True)
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
    if data.get('title') and not merged.get('title'):
        merged['title'] = data['title']
    if merged.get('kind') == 'clarify':
        merged['kind'] = 'fallback'
        if data.get('title'):
            merged['title'] = data['title']
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
