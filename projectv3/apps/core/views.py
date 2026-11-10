import io
import json
import logging
import mimetypes
import os
import re
import uuid
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import SuspiciousFileOperation, ValidationError
from django.core.files.storage import default_storage
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme, urlencode
from django.utils.text import get_valid_filename
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST

from .assistant import build_answer, search_terms, _tokens
from .gemini import enhance_answer
from .recent_activity import get_recent_activities, record_recent_activity

logger = logging.getLogger(__name__)

User = get_user_model()

MAX_FAILED_ATTEMPTS = 5
LOCK_DURATION = timedelta(minutes=1)
INVALID_LOGIN_MESSAGE = 'Invalid username or password.'
LOCKED_MESSAGE = 'Too many failed attempts. Locked for 1 minute.'


def _reset_lock_state(request):
    request.session['failed_attempts'] = 0
    request.session['lock_time'] = None


def _get_lock_state(request):
    failed_attempts = request.session.get('failed_attempts', 0)
    lock_time = request.session.get('lock_time')

    if not lock_time:
        return failed_attempts, None

    try:
        unlock_time = datetime.fromisoformat(lock_time)
        # Session stores ISO string; make aware if naive to compare with timezone.now().
        if timezone.is_naive(unlock_time):
            unlock_time = timezone.make_aware(unlock_time)
    except (TypeError, ValueError):
        _reset_lock_state(request)
        return 0, None

    try:
        if timezone.now() < unlock_time:
            remaining = int((unlock_time - timezone.now()).total_seconds())
            return failed_attempts, remaining
    except TypeError:
        _reset_lock_state(request)
        return 0, None

    _reset_lock_state(request)
    return 0, None


def _set_lock_state(request):
    lock_until = timezone.now() + LOCK_DURATION
    request.session['failed_attempts'] = MAX_FAILED_ATTEMPTS
    request.session['lock_time'] = lock_until.isoformat()
    return int(LOCK_DURATION.total_seconds())


def _validate_registration_data(data):
    errors = {}

    username = data.get('username', '').strip()
    first_name = data.get('first_name', '').strip()
    last_name = data.get('last_name', '').strip()
    email = data.get('email', '').strip()
    phone_number = data.get('phone_number', '').strip()
    password = data.get('password', '')
    confirm_password = data.get('confirm_password', '')

    if not username:
        errors['username'] = 'Username is required.'
    elif User.objects.filter(username=username).exists():
        errors['username'] = 'Username already taken.'

    if not first_name:
        errors['first_name'] = 'First name is required.'

    if not last_name:
        errors['last_name'] = 'Last name is required.'

    if not email:
        errors['email'] = 'Email is required.'
    else:
        try:
            validate_email(email)
        except ValidationError:
            errors['email'] = 'Enter a valid email address.'
        else:
            if User.objects.filter(email=email).exists():
                errors['email'] = 'Email already registered.'

    if phone_number:
        from apps.users.models import PhoneProfile

        phone_number = re.sub(r'[\s().-]', '', phone_number)
        if not re.fullmatch(r'\+[1-9]\d{7,14}', phone_number):
            errors['phone_number'] = 'Enter a valid phone number in international format, such as +639171234567.'
        elif PhoneProfile.objects.filter(phone_number=phone_number).exists():
            errors['phone_number'] = 'Phone number already registered.'

    if not password:
        errors['password'] = 'Password is required.'
    elif len(password) < 8:
        errors['password'] = 'Password must be at least 8 characters.'
    else:
        try:
            validate_password(password)
        except ValidationError as exc:
            errors['password'] = ' '.join(exc.messages)

    if password != confirm_password:
        errors['confirm_password'] = 'Passwords do not match.'

    return errors


@require_http_methods(['GET', 'POST'])
def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    failed_attempts, remaining = _get_lock_state(request)
    if remaining is not None:
        messages.error(request, f'Too many failed attempts. Try again in {remaining} seconds.')
        return render(request, 'auth/login.html', {
            'locked': True,
            'remaining': remaining,
            'google_login_enabled': settings.GOOGLE_OAUTH_ENABLED,
        })

    if request.method == 'GET':
        return render(request, 'auth/login.html', {
            'google_login_enabled': settings.GOOGLE_OAUTH_ENABLED,
        })

    identifier = request.POST.get('identifier', request.POST.get('username', '')).strip()
    password = request.POST.get('password', '')
    from apps.users.models import PhoneProfile

    normalized_phone = re.sub(r'[\s().-]', '', identifier)
    identity_filter = Q(username__iexact=identifier) | Q(email__iexact=identifier)
    if re.fullmatch(r'\+[1-9]\d{7,14}', normalized_phone):
        identity_filter |= Q(phone_profile__phone_number=normalized_phone)
    matching_users = list(
        User.objects.filter(identity_filter).distinct().order_by('pk')[:2]
    )
    candidate = matching_users[0] if len(matching_users) == 1 else None
    user = authenticate(
        request,
        username=candidate.get_username() if candidate else identifier,
        password=password,
    )

    if user is not None:
        _reset_lock_state(request)
        login(request, user)
        next_url = request.POST.get('next') or request.GET.get('next')
        if next_url and url_has_allowed_host_and_scheme(
            next_url, allowed_hosts={request.get_host()}
        ):
            return redirect(next_url)
        return redirect('dashboard')

    failed_attempts += 1
    request.session['failed_attempts'] = failed_attempts
    if failed_attempts >= MAX_FAILED_ATTEMPTS:
        remaining = _set_lock_state(request)
        messages.error(request, LOCKED_MESSAGE)
        return render(request, 'auth/login.html', {
            'locked': True,
            'remaining': remaining,
            'identifier': identifier,
            'google_login_enabled': settings.GOOGLE_OAUTH_ENABLED,
        })

    remaining_attempts = MAX_FAILED_ATTEMPTS - failed_attempts
    messages.error(request, f'{INVALID_LOGIN_MESSAGE} {remaining_attempts} attempts remaining.')
    return render(request, 'auth/login.html', {
        'identifier': identifier,
        'google_login_enabled': settings.GOOGLE_OAUTH_ENABLED,
    })


@require_POST
def logout_view(request):
    logout(request)
    return redirect('dashboard')


def _search_filter(query, fields):
    terms = search_terms(query)
    if not terms:
        return Q(pk__in=[])
    condition = Q()
    for term in terms:
        for field in fields:
            condition |= Q(**{field + '__icontains': term})
    return condition


def _product_search(qs, query):
    """Full-field product search across every meaningful query term."""
    return qs.filter(
        _search_filter(query, [
            'name', 'brand', 'description', 'specifications', 'category__name',
        ])
    ).distinct()


def _accessory_search(qs, query):
    """Full-field accessory search across every meaningful query term."""
    return qs.filter(
        _search_filter(query, [
            'name', 'brand', 'description', 'compatibility_notes', 'category__name',
        ])
    ).distinct()


def _solution_search(qs, query):
    """Full-field repair guide search across every meaningful query term."""
    return qs.filter(
        _search_filter(query, [
            'title', 'problem_description', 'steps', 'difficulty_level',
            'category__name', 'related_product__name', 'related_product__brand',
        ])
    ).distinct()


def _specific_search(qs, query, fields):
    """Require every query term to match at least one field."""
    tokens = list(_tokens(query))
    if not tokens:
        return qs.none()
    for token in tokens:
        condition = Q()
        for field in fields:
            condition |= Q(**{field + '__icontains': token})
        qs = qs.filter(condition)
    return qs.distinct()


def _load_legacy_names(path, key):
    import os as _os
    _p = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))), path)
    _ns = {}
    with open(_p, encoding='utf-8') as _fh:
        exec(_fh.read(), _ns)
    return {item[1] for items in _ns[key].values() for item in items}


_LEGACY_PRODUCTS = None
_LEGACY_ACCESSORIES = None


def _legacy_product_names():
    global _LEGACY_PRODUCTS
    if _LEGACY_PRODUCTS is None:
        _LEGACY_PRODUCTS = _load_legacy_names('old_products_data.py', 'OLD_PRODUCTS')
    return _LEGACY_PRODUCTS


def _legacy_accessory_names():
    global _LEGACY_ACCESSORIES
    if _LEGACY_ACCESSORIES is None:
        _LEGACY_ACCESSORIES = _load_legacy_names('old_accessories_data.py', 'OLD_ACCESSORIES')
    return _LEGACY_ACCESSORIES


def _new_first(qs, legacy_names):
    """Order a Product/Accessory queryset so current (non-legacy) items come first,
    then legacy items — each group newest-first by created_at."""
    from django.db.models import Avg, Case, Count, When, Value, IntegerField
    return qs.annotate(
        _review_count=Count('reviews', distinct=True),
        _review_avg=Avg('reviews__rating'),
        _legacy=Case(
            When(name__in=legacy_names, then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        )
    ).order_by('_legacy', '-created_at')


CHAT_SESSION_KEY = 'techfix_chat_messages'
MAX_CHAT_MESSAGES = 20
MAX_CHAT_QUESTION_LENGTH = 1000
MAX_CHAT_ATTACHMENTS = 5
MAX_CHAT_ATTACHMENT_BYTES = 10 * 1024 * 1024
MAX_CHAT_ATTACHMENT_TOTAL_BYTES = 25 * 1024 * 1024
CHAT_ATTACHMENT_EXTENSIONS = frozenset({
    '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp',
    '.pdf', '.txt', '.md', '.csv',
    '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.zip',
})
CHAT_IMAGE_EXTENSIONS = frozenset({
    '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp',
})
MAX_AI_ATTACHMENT_BYTES = 12 * 1024 * 1024
MAX_AI_ATTACHMENT_TEXT_CHARS = 20000
DEFAULT_ATTACHMENT_QUESTION = (
    'Analyze the attached file or photo. Identify the device, object, error '
    'message, or problem shown, read any visible text, and explain what it '
    'means and what I should do next.'
)
GEMINI_IMAGE_MIME_TYPES = frozenset({
    'image/png', 'image/jpeg', 'image/webp', 'image/heic', 'image/heif',
})
_IMAGE_MIME_BY_EXTENSION = {
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.png': 'image/png',
    '.webp': 'image/webp',
    '.heic': 'image/heic',
    '.heif': 'image/heif',
}
_FOLLOW_UP_PRONOUNS = frozenset({
    'it', 'its', 'this', 'that', 'these', 'those', 'they', 'them', 'their',
    'same', 'also', 'still', 'again', 'another', 'both',
})
_FOLLOW_UP_STARTS = (
    'and ', 'also ', 'what about', 'how about', 'what if', 'then ',
    'can you', 'could you', 'would it', 'does it', 'is it',
    'how much', 'how many',
)


def _serialize_product(product):
    if product is None:
        return None
    return {
        'id': product.pk,
        'name': product.name,
        'brand': product.brand,
        'category': product.category.name if product.category else '',
        'description': product.description,
        'price': str(product.price) if product.price is not None else '',
        'source_url': product.source_url,
        'stock': product.stock_quantity,
        'specs': product.spec_list,
        'image_url': product.image.url if product.has_real_photo else '',
        'icon': product.display_icon,
        'tint': product.display_tint,
    }


def _serialize_accessory(accessory):
    if accessory is None:
        return None
    return {
        'id': accessory.pk,
        'name': accessory.name,
        'brand': accessory.brand,
        'category': accessory.category.name if accessory.category else '',
        'description': accessory.description,
        'price': str(accessory.price) if accessory.price is not None else '',
        'source_url': accessory.source_url,
        'stock': accessory.stock_quantity,
        'compatibility': accessory.compatibility_notes,
        'image_url': accessory.image.url if accessory.has_real_photo else '',
        'icon': accessory.display_icon,
        'tint': accessory.display_tint,
    }


def _serialize_solution_match(solution):
    return {
        'id': solution.pk,
        'title': solution.title,
        'category': solution.category.name if solution.category else '',
        'difficulty': solution.difficulty_level,
    }


def _serialize_matches(matches):
    matches = matches if isinstance(matches, dict) else {}
    return {
        'products': [
            _serialize_product(item)
            for item in (matches.get('products') or [])[:60]
            if item is not None
        ],
        'accessories': [
            _serialize_accessory(item)
            for item in (matches.get('accessories') or [])[:30]
            if item is not None
        ],
        'solutions': [
            _serialize_solution_match(item)
            for item in (matches.get('solutions') or [])[:30]
            if item is not None
        ],
    }


def _products_mentioned_in_message(message):
    """Return catalog products whose full name the user explicitly mentioned."""
    from .models import Product

    text = (message or '').strip()
    if not text:
        return []

    catalog_names = list(
        Product.objects.order_by('pk').values_list('pk', 'name')
    )
    names_by_text = {}
    for product_id, name in catalog_names:
        normalized_name = (name or '').strip()
        if normalized_name:
            names_by_text.setdefault(normalized_name.casefold(), product_id)
    if not names_by_text:
        return []

    alternatives = sorted(
        (re.escape(name) for name in names_by_text),
        key=len,
        reverse=True,
    )
    product_pattern = re.compile(
        r'(?<!\w)(' + '|'.join(alternatives) + r')(?!\w)',
        re.IGNORECASE,
    )
    mentioned_ids = list(dict.fromkeys(
        names_by_text[match.group(1).casefold()]
        for match in product_pattern.finditer(text)
    ))
    if not mentioned_ids:
        return []
    products = Product.objects.select_related('category').in_bulk(mentioned_ids)
    return [
        products[product_id]
        for product_id in mentioned_ids
        if product_id in products
    ]


def _serialize_mentioned_products(answer):
    selected_product = answer.get('product')
    products = [
        selected_product,
        *(answer.get('mentioned_products') or []),
    ]
    seen_ids = set()
    serialized = []
    for product in products:
        product_id = getattr(product, 'pk', None)
        if product_id is None or product_id in seen_ids:
            continue
        seen_ids.add(product_id)
        serialized.append(_serialize_product(product))
    return serialized


def _serialize_answer(answer):
    serialized = {
        'kind': str(answer.get('kind') or ''),
        'badge': str(answer.get('badge') or 'Answer'),
        'title': str(answer.get('title') or ''),
        'summary': str(answer.get('summary') or ''),
        'first_step': str(answer.get('first_step') or ''),
        'steps': [str(step) for step in (answer.get('steps') or [])],
        'steps_title': str(answer.get('steps_title') or ''),
        'difficulty': str(answer.get('difficulty') or ''),
        'category': str(answer.get('category') or ''),
        'product': _serialize_product(answer.get('product')),
        'accessory': _serialize_accessory(answer.get('accessory')),
        'video_url': str(answer.get('video_url') or ''),
        'safety': str(answer.get('safety') or ''),
        'suggestions': [
            str(suggestion) for suggestion in (answer.get('suggestions') or [])
        ],
        'ai': bool(answer.get('ai')),
        'notice': str(answer.get('notice') or ''),
        'mentioned_products': (
            []
            if (
                answer.get('brand_overview')
                or answer.get('kind') == 'results'
                or answer.get('badge') == 'No exact match'
            )
            else _serialize_mentioned_products(answer)
        ),
    }
    if serialized['kind'] == 'results':
        serialized['matches'] = _serialize_matches(answer.get('matches'))
    return serialized


def _chat_upload_name(upload):
    raw_name = os.path.basename(str(upload.name or '')).strip()
    try:
        return get_valid_filename(raw_name)
    except SuspiciousFileOperation:
        return ''


def _save_chat_attachments(uploads):
    if not uploads:
        return [], ''
    if len(uploads) > MAX_CHAT_ATTACHMENTS:
        return [], 'You can attach up to %d files at a time.' % MAX_CHAT_ATTACHMENTS

    validated = []
    total_size = 0
    for upload in uploads:
        name = _chat_upload_name(upload)
        extension = os.path.splitext(name)[1].lower()
        if not name or extension not in CHAT_ATTACHMENT_EXTENSIONS:
            return [], '"%s" is not a supported file type.' % (name or 'That file')
        if not upload.size:
            return [], '"%s" is empty.' % name
        if upload.size > MAX_CHAT_ATTACHMENT_BYTES:
            return [], '"%s" is larger than 10 MB.' % name
        total_size += upload.size
        validated.append((upload, name, extension))
    if total_size > MAX_CHAT_ATTACHMENT_TOTAL_BYTES:
        return [], 'Attachments must be 25 MB or smaller in total.'

    attachments = []
    for upload, name, extension in validated:
        stored_name = 'chat_uploads/%s/%s%s' % (
            timezone.now().strftime('%Y%m'), uuid.uuid4().hex, extension
        )
        saved_path = default_storage.save(stored_name, upload)
        attachments.append({
            'name': name[:120],
            'url': default_storage.url(saved_path),
            'size': upload.size,
            'is_image': extension in CHAT_IMAGE_EXTENSIONS,
        })
    return attachments, ''


def _convert_image_for_ai(upload):
    try:
        from PIL import Image
    except Exception:
        logger.exception('Image support is unavailable')
        return '', b''
    try:
        upload.seek(0)
        with Image.open(upload) as image:
            if getattr(image, 'is_animated', False):
                image.seek(0)
            converted = image.convert('RGB')
            buffer = io.BytesIO()
            converted.save(buffer, format='JPEG', quality=88)
            return 'image/jpeg', buffer.getvalue()
    except Exception:
        logger.warning('Could not read an attached image for AI analysis')
        return '', b''


def _ai_chat_attachments(uploads):
    """Build Gemini-ready attachment parts for the current message."""
    attachments = []
    total_size = 0
    for upload in uploads:
        name = _chat_upload_name(upload) or 'attachment'
        extension = os.path.splitext(name)[1].lower()
        mime_type = str(getattr(upload, 'content_type', '') or '').lower()
        if not mime_type:
            mime_type = mimetypes.guess_type(name)[0] or 'application/octet-stream'
        try:
            upload.seek(0)
        except (AttributeError, OSError):
            pass

        if extension in CHAT_IMAGE_EXTENSIONS:
            if extension in ('.gif', '.bmp'):
                mime_type, data = _convert_image_for_ai(upload)
            else:
                if mime_type not in GEMINI_IMAGE_MIME_TYPES:
                    mime_type = _IMAGE_MIME_BY_EXTENSION.get(
                        extension, 'image/jpeg'
                    )
                try:
                    data = upload.read()
                except (AttributeError, OSError):
                    data = b''
            if not data:
                attachments.append({
                    'type': 'note',
                    'text': (
                        'The user attached an image named "%s" but it could not '
                        'be read. Ask them to attach a JPEG or PNG photo.'
                    ) % name,
                })
                continue
            if total_size + len(data) > MAX_AI_ATTACHMENT_BYTES:
                attachments.append({
                    'type': 'note',
                    'text': (
                        'The user attached an image named "%s" that is too large '
                        'to inspect. Ask them to send a smaller JPEG or PNG.'
                    ) % name,
                })
                continue
            total_size += len(data)
            attachments.append({
                'type': 'image',
                'name': name,
                'mime_type': mime_type,
                'data': data,
            })
        elif extension == '.pdf':
            try:
                data = upload.read()
            except (AttributeError, OSError):
                data = b''
            if data and total_size + len(data) <= MAX_AI_ATTACHMENT_BYTES:
                total_size += len(data)
                attachments.append({
                    'type': 'document',
                    'name': name,
                    'mime_type': 'application/pdf',
                    'data': data,
                })
            else:
                attachments.append({
                    'type': 'note',
                    'text': (
                        'The user attached a PDF named "%s" but it could not be '
                        'inspected. Ask them to send a smaller PDF or a photo '
                        'of the relevant page.'
                    ) % name,
                })
        elif extension in {'.txt', '.md', '.csv'}:
            try:
                raw = upload.read(MAX_AI_ATTACHMENT_TEXT_CHARS + 1)
            except (AttributeError, OSError):
                raw = b''
            text = raw.decode('utf-8', errors='replace')[
                :MAX_AI_ATTACHMENT_TEXT_CHARS
            ]
            attachments.append({
                'type': 'text',
                'text': 'Contents of attached file "%s":\n%s' % (name, text),
            })
        else:
            attachments.append({
                'type': 'note',
                'text': (
                    'The user attached a file named "%s" (%s). This file type '
                    'cannot be read directly. Ask them to describe the content '
                    'or attach a photo or PDF if they need help with it.'
                ) % (name, mime_type),
            })
    return attachments


def _normalize_chat_attachments(raw):
    if not isinstance(raw, list):
        return []
    media_prefix = settings.MEDIA_URL or '/media/'
    attachments = []
    for item in raw[:MAX_CHAT_ATTACHMENTS]:
        if not isinstance(item, dict):
            continue
        name = item.get('name')
        url = item.get('url')
        size = item.get('size')
        if not isinstance(name, str) or not name.strip():
            continue
        if not isinstance(url, str) or not url.startswith(media_prefix):
            continue
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            size = 0
        attachments.append({
            'name': name.strip()[:120],
            'url': url,
            'size': size,
            'is_image': bool(item.get('is_image')),
        })
    return attachments


def _attachment_only_answer(attachments):
    count = len(attachments)
    names = ', '.join(item['name'] for item in attachments)
    return {
        'kind': 'answer',
        'badge': 'Files received',
        'title': 'Attachment received' if count == 1 else 'Attachments received',
        'summary': (
            'I received %d %s: %s. Tell me what you need help with and '
            'include any details from the attached file.'
            % (count, 'file' if count == 1 else 'files', names)
        ),
        'suggestions': [
            'Help me troubleshoot a device problem.',
            'Find accessories that are compatible with my device.',
        ],
    }


def _attachment_notice(attachments):
    count = len(attachments)
    names = ', '.join(item['name'] for item in attachments)
    label = 'file' if count == 1 else '%d files' % count
    return 'Attached %s: %s.' % (label, names)


def _normalize_chat_history(raw):
    if not isinstance(raw, list):
        return []
    history = []
    for item in raw[-MAX_CHAT_MESSAGES:]:
        if not isinstance(item, dict):
            continue
        role = item.get('role')
        if role == 'user':
            text = item.get('text')
            if not isinstance(text, str):
                text = ''
            text = text.strip()[:MAX_CHAT_QUESTION_LENGTH]
            attachments = _normalize_chat_attachments(item.get('attachments'))
            if not text and not attachments:
                continue
            entry = {'role': 'user', 'text': text}
            if attachments:
                entry['attachments'] = attachments
            history.append(entry)
        elif role == 'assistant':
            answer = item.get('answer')
            if isinstance(answer, dict):
                history.append({'role': 'assistant', 'answer': answer})
    return history


def _get_chat_history(request):
    return _normalize_chat_history(request.session.get(CHAT_SESSION_KEY))


def _latest_chat_turn(history):
    last_user = None
    for index in range(len(history) - 1, -1, -1):
        if history[index].get('role') == 'user':
            last_user = index
            break
    if last_user is None:
        return []
    turn = [history[last_user]]
    for entry in history[last_user + 1:]:
        if entry.get('role') == 'assistant':
            turn.append(entry)
            break
    return turn


def _save_chat_history(request, history):
    request.session[CHAT_SESSION_KEY] = history[-MAX_CHAT_MESSAGES:]


def _append_chat_turn(request, message, answer, attachments=None):
    history = _get_chat_history(request)
    entry = {'role': 'user', 'text': message}
    if attachments:
        entry['attachments'] = attachments
    history.append(entry)
    history.append({'role': 'assistant', 'answer': answer})
    _save_chat_history(request, history)
    if message:
        activity_title = message
    else:
        count = len(attachments or [])
        activity_title = 'Shared %d %s' % (
            count, 'file' if count == 1 else 'files'
        )
    try:
        record_recent_activity(
            request,
            'assistant',
            activity_title,
            reverse('dashboard') + '#techfix',
            chat_history=history,
        )
    except Exception:
        logger.exception('Recording recent activity failed')


def _context_query(message, history):
    prior = [
        item.get('text') for item in history
        if item.get('role') == 'user' and item.get('text')
    ]
    if not prior:
        return message
    text = message.lower()
    words = set(re.findall(r'[a-z0-9]+', text))
    if words & _FOLLOW_UP_PRONOUNS or text.startswith(_FOLLOW_UP_STARTS):
        return '%s %s' % (prior[-1], message)
    return message


def _is_chat_question(message):
    text = (message or '').strip().lower()
    if '?' in text:
        return True
    first_word = text.split()[0] if text.split() else ''
    question_starters = {
        'how', 'what', 'why', 'where', 'when', 'who', 'which',
        'can', 'could', 'should', 'would', 'is', 'are', 'do', 'does', 'did',
        'will', 'tell', 'explain', 'help',
    }
    if first_word in question_starters:
        return True
    trouble_words = (
        'fix', 'repair', 'broken', 'issue', 'problem', 'stuck', 'error',
        'slow', 'lag', 'freeze', 'crash', 'drain', 'overheat', 'fail',
        'dead', 'not working', "won't", 'wont', 'cant', 'cannot',
    )
    return any(w in text for w in trouble_words)


def _create_chat_answer(message, history, attachments=None):
    context_query = _context_query(message, history)
    try:
        local_answer = build_answer(context_query)
    except Exception:
        logger.exception('Local assistant answer failed')
        local_answer = None

    answer = enhance_answer(
        message,
        local_answer,
        history=history,
        attachments=attachments,
    )
    if answer:
        if local_answer and local_answer.get('matches') and not answer.get('matches'):
            answer['matches'] = local_answer['matches']
        if local_answer and local_answer.get('product') and not answer.get('product'):
            answer['product'] = local_answer['product']
        if local_answer and local_answer.get('accessory') and not answer.get('accessory'):
            answer['accessory'] = local_answer['accessory']
        if local_answer and local_answer.get('strict'):
            local_kind = local_answer.get('kind')
            if local_kind in ('product', 'results'):
                answer['kind'] = local_kind
            if not attachments:
                answer['kind'] = local_kind or answer.get('kind')
                if local_answer.get('badge'):
                    answer['badge'] = local_answer['badge']
                if local_answer.get('suggestions') and not answer.get('suggestions'):
                    answer['suggestions'] = local_answer['suggestions']
    else:
        answer = local_answer

    if answer:
        answer['mentioned_products'] = _products_mentioned_in_message(
            context_query
        )
    return answer


@never_cache
def home(request):
    if request.GET.get('new'):
        request.session.pop(CHAT_SESSION_KEY, None)
        return redirect('dashboard')

    legacy_query = (request.GET.get('q') or '').strip()
    if legacy_query:
        if len(legacy_query) <= MAX_CHAT_QUESTION_LENGTH:
            history = _get_chat_history(request)
            try:
                answer = _create_chat_answer(legacy_query, history)
            except Exception:
                logger.exception('Legacy assistant chat failed')
                answer = None
            if answer:
                _append_chat_turn(
                    request, legacy_query, _serialize_answer(answer)
                )
        return redirect(reverse('dashboard') + '#techfix')

    return render(request, 'home.html', {
        'chat_messages': _get_chat_history(request),
    })


@never_cache
@login_required(login_url='login')
def scheduled_assistant(request):
    if request.GET.get('new'):
        request.session.pop(CHAT_SESSION_KEY, None)
        return redirect('scheduled_assistant')
    return render(request, 'scheduled.html', {
        'chat_messages': _get_chat_history(request),
    })


@login_required(login_url='login')
def recent_activity_detail(request, pk):
    from django.http import Http404

    from .models import RecentActivity

    activity = RecentActivity.objects.filter(
        user=request.user, pk=pk
    ).first()
    if activity is None:
        raise Http404('Recent activity not found.')

    RecentActivity.objects.filter(pk=activity.pk).update(
        created_at=timezone.now()
    )

    if activity.kind != 'assistant':
        return redirect(activity.url)

    turn = _latest_chat_turn(
        _normalize_chat_history(activity.chat_history)
    )
    if not turn:
        try:
            answer = _create_chat_answer(activity.title, [])
        except Exception:
            logger.exception('Rebuilding recent activity failed')
            answer = None
        if answer:
            turn = [
                {'role': 'user', 'text': activity.title},
                {'role': 'assistant', 'answer': _serialize_answer(answer)},
            ]
            RecentActivity.objects.filter(pk=activity.pk).update(
                chat_history=turn
            )
        else:
            request.session.pop(CHAT_SESSION_KEY, None)
            return redirect(reverse('dashboard') + '?new=1')

    _save_chat_history(request, turn)
    return redirect(reverse('dashboard') + '#techfix')


@require_POST
@never_cache
def assistant_chat(request):
    is_multipart = (
        str(request.content_type or '').startswith('multipart/form-data')
    )
    if is_multipart:
        message = request.POST.get('message', '')
        if not isinstance(message, str):
            return JsonResponse({'error': 'Invalid chat request.'}, status=400)
    else:
        try:
            payload = json.loads(request.body or b'{}')
        except (TypeError, ValueError):
            return JsonResponse({'error': 'Invalid chat request.'}, status=400)
        if not isinstance(payload, dict):
            return JsonResponse({'error': 'Invalid chat request.'}, status=400)
        message = payload.get('message')
        if not isinstance(message, str):
            return JsonResponse({'error': 'Please type a message.'}, status=400)

    message = message.strip()
    if len(message) > MAX_CHAT_QUESTION_LENGTH:
        return JsonResponse(
            {'error': 'Please keep your question under 1,000 characters.'},
            status=400,
        )

    attachments = []
    ai_attachments = []
    if is_multipart:
        uploads = request.FILES.getlist('attachments')
        if not uploads:
            uploads = request.FILES.getlist('files')
        attachments, attachment_error = _save_chat_attachments(uploads)
        if attachment_error:
            return JsonResponse({'error': attachment_error}, status=400)
        if uploads:
            ai_attachments = _ai_chat_attachments(uploads)

    if not message and not attachments:
        return JsonResponse({'error': 'Please type a message.'}, status=400)

    history = _get_chat_history(request)
    try:
        answer = _create_chat_answer(
            message or DEFAULT_ATTACHMENT_QUESTION,
            history,
            attachments=ai_attachments or None,
        )
    except Exception:
        logger.exception('Assistant chat failed')
        return JsonResponse(
            {'error': 'TechFix could not answer that question right now. '
                      'Please try again.'},
            status=500,
        )
    if not message and not (answer and answer.get('ai')):
        answer = _attachment_only_answer(attachments)
    if not answer:
        return JsonResponse(
            {'error': 'TechFix could not answer that question right now. '
                      'Please try again.'},
            status=502,
        )

    try:
        serialized = _serialize_answer(answer)
        if attachments:
            notice = _attachment_notice(attachments)
            serialized['notice'] = (
                '%s %s' % (notice, serialized['notice'])
                if serialized.get('notice') else notice
            )
        html = render_to_string(
            'catalog/_chat_message.html',
            {'message': {'role': 'assistant', 'answer': serialized}},
            request=request,
        )
        _append_chat_turn(request, message, serialized, attachments)
    except Exception:
        logger.exception('Assistant reply failed')
        return JsonResponse(
            {'error': 'TechFix could not display that answer. Please try again.'},
            status=500,
        )

    try:
        recent_activities = get_recent_activities(request)
    except Exception:
        logger.exception('Loading recent activities failed')
        recent_activities = []
    return JsonResponse({
        'html': html,
        'recent_activities': recent_activities,
    })


def _get_all_brands():
    """Distinct non-empty brands across products and accessories, sorted A-Z."""
    from .models import Accessory, Product

    product_brands = list(
        Product.objects.exclude(brand='').values_list('brand', flat=True).distinct()
    )
    accessory_brands = list(
        Accessory.objects.exclude(brand='').values_list('brand', flat=True).distinct()
    )
    return sorted(set(product_brands + accessory_brands), key=str.lower)


def _brand_accent(brand):
    """Deterministic accent class (bf-a..bf-e) so each brand folder has its own tint."""
    return 'bf-' + 'abcde'[sum(ord(ch) for ch in (brand or '').lower()) % 5]


def _get_brand_folders():
    """Brand folders with per-brand counts of products, accessories and solutions."""
    from .models import Accessory, Product, Solution

    folders = []
    for brand in _get_all_brands():
        solutions_qs = Solution.objects.filter(
            Q(related_product__brand__iexact=brand)
            | (Q(related_product__isnull=True) & Q(title__icontains=brand))
        )
        folders.append({
            'name': brand,
            'accent': _brand_accent(brand),
            'product_count': Product.objects.filter(brand__iexact=brand).count(),
            'accessory_count': Accessory.objects.filter(brand__iexact=brand).count(),
            'solution_count': solutions_qs.count(),
        })
    return folders


def _library_image_search(qs, query):
    """Specific name, brand and category search for Library photos."""
    tokens = list(_tokens(query))
    if not tokens:
        return qs.none()
    for token in tokens:
        condition = Q()
        for field in ('name', 'brand', 'category__name'):
            condition |= Q(**{field + '__icontains': token})
        qs = qs.filter(condition)
    return qs.distinct()


_LIBRARY_FEATURED_PRODUCTS = (
    ('samsung', 'galaxy s26'),
    ('samsung', 'galaxy s26+'),
    ('apple', 'iphone 18 pro'),
    ('apple', 'iphone 17e'),
)


def _get_library_images(query=''):
    """Return every matching catalog item for the Library images view."""
    from .models import Accessory, Product

    featured_order = {
        product: index
        for index, product in enumerate(_LIBRARY_FEATURED_PRODUCTS)
    }
    products = Product.objects.select_related('category')
    accessories = Accessory.objects.select_related('category')
    if query:
        products = _library_image_search(products, query)
        accessories = _library_image_search(accessories, query)

    items = []
    for product in products.order_by('-created_at', '-pk').iterator():
        key = (product.brand.casefold(), product.name.casefold())
        items.append({
            'name': product.name,
            'brand': product.brand,
            'kind': 'Product',
            'image_url': product.image.url if product.has_real_photo else '',
            'icon': product.display_icon,
            'tint': product.display_tint,
            'url': reverse('product_detail', args=[product.pk]),
            '_featured_order': (
                featured_order.get(key) if product.has_real_photo else None
            ),
            '_original_order': len(items),
        })
    for accessory in accessories.order_by('-created_at', '-pk').iterator():
        items.append({
            'name': accessory.name,
            'brand': accessory.brand,
            'kind': 'Accessory',
            'image_url': accessory.image.url if accessory.has_real_photo else '',
            'icon': accessory.display_icon,
            'tint': accessory.display_tint,
            'url': reverse('accessory_detail', args=[accessory.pk]),
            '_featured_order': None,
            '_original_order': len(items),
        })
    def sort_key(item):
        if item['_featured_order'] is not None:
            return (0, item['_featured_order'], item['_original_order'])
        return (1, 0 if item['image_url'] else 1, item['_original_order'])

    items.sort(key=sort_key)
    for item in items:
        item.pop('_featured_order')
        item.pop('_original_order')
    return items


def _get_library_solutions(query=''):
    """Return repair guides for the Library solutions view."""
    from .models import Solution

    qs = Solution.objects.select_related(
        'category', 'related_product'
    ).order_by('-created_at', '-pk')
    if query:
        qs = _solution_search(qs, query)

    difficulty_classes = {
        'Easy': 'techfix-badge-easy',
        'Medium': 'techfix-badge-medium',
    }
    items = []
    for index, solution in enumerate(qs):
        product = solution.related_product
        items.append({
            'name': solution.title,
            'brand': product.brand if product else '',
            'category': solution.category.name if solution.category else '',
            'difficulty': solution.difficulty_level,
            'difficulty_class': difficulty_classes.get(
                solution.difficulty_level, 'techfix-badge-hard'
            ),
            'video_url': solution.video_url,
            'video_thumb': solution.video_thumb,
            'icon': 'fa-solid fa-screwdriver-wrench',
            'tint': 'pt-' + str(index % 8),
            'url': (
                reverse('product_detail', args=[product.pk])
                if product
                else reverse('solution_list') + '?' + urlencode({'q': solution.title})
            ),
        })
    return items


def _canonical_brand(brand):
    """Return the stored casing of a brand (case-insensitive match), or None."""
    for name in _get_all_brands():
        if name.lower() == (brand or '').lower():
            return name
    return None


def brand_list(request):
    query = request.GET.get('q', '').strip()
    record_recent_activity(
        request,
        'library',
        'Brand library' + (': ' + query if query else ''),
        request.get_full_path(),
    )
    folders = _get_brand_folders()
    if query:
        folders = [f for f in folders if query.lower() in f['name'].lower()]
    image_items = _get_library_images(query)
    solution_items = _get_library_solutions(query)
    active_tab = 'suggested'
    if query and not folders:
        if image_items:
            active_tab = 'images'
        elif solution_items:
            active_tab = 'solutions'
    return render(request, 'catalog/brands.html', {
        'brands': folders,
        'query': query,
        'total': len(folders),
        'image_items': image_items,
        'solution_items': solution_items,
        'active_tab': active_tab,
    })


def brand_detail(request, brand):
    from django.http import Http404

    from .models import Accessory, Product, Solution

    canonical = _canonical_brand(brand)
    if canonical is None:
        raise Http404('Brand not found.')
    query = request.GET.get('q', '').strip()
    record_recent_activity(
        request, 'brand', 'Brand: ' + canonical, request.get_full_path()
    )

    products = _new_first(
        Product.objects.filter(brand__iexact=canonical).select_related('category'),
        _legacy_product_names(),
    )
    accessories = _new_first(
        Accessory.objects.filter(brand__iexact=canonical).select_related('category'),
        _legacy_accessory_names(),
    )
    solutions = Solution.objects.filter(
        Q(related_product__brand__iexact=canonical)
        | (Q(related_product__isnull=True) & Q(title__icontains=canonical))
    ).select_related('category', 'related_product').order_by('-created_at')
    if query:
        products = _specific_search(products, query, [
            'name', 'brand', 'description', 'specifications', 'category__name',
        ])
        accessories = _specific_search(accessories, query, [
            'name', 'brand', 'description', 'compatibility_notes', 'category__name',
        ])
        solutions = _specific_search(solutions, query, [
            'title', 'problem_description', 'steps', 'difficulty_level',
            'category__name', 'related_product__name', 'related_product__brand',
        ])
    return render(request, 'catalog/brand_detail.html', {
        'brand': canonical,
        'accent': _brand_accent(canonical),
        'brands': _get_brand_folders(),
        'products': products, 'product_count': products.count(),
        'accessories': accessories, 'accessory_count': accessories.count(),
        'solutions': solutions, 'solution_count': solutions.count(),
        'query': query,
    })


def product_list(request):
    from .models import Product

    query = request.GET.get('q', '').strip()
    active_brand = request.GET.get('brand', '').strip()
    record_recent_activity(
        request,
        'products',
        'Products' + (': ' + query if query else ''),
        request.get_full_path(),
    )
    qs = _new_first(Product.objects.select_related('category').all(), _legacy_product_names())
    if active_brand:
        qs = qs.filter(brand__iexact=active_brand)
    if query:
        qs = _product_search(qs, query)
    return render(request, 'catalog/products.html', {
        'products': qs, 'query': query, 'total': qs.count(),
        'brands': _get_brand_folders(), 'active_brand': active_brand,
    })


def accessory_list(request):
    from .models import Accessory

    query = request.GET.get('q', '').strip()
    active_brand = request.GET.get('brand', '').strip()
    record_recent_activity(
        request,
        'accessories',
        'Accessories' + (': ' + query if query else ''),
        request.get_full_path(),
    )
    qs = _new_first(Accessory.objects.select_related('category').all(), _legacy_accessory_names())
    if active_brand:
        qs = qs.filter(brand__iexact=active_brand)
    if query:
        qs = _accessory_search(qs, query)
    return render(request, 'catalog/accessories.html', {
        'accessories': qs, 'query': query, 'total': qs.count(),
        'brands': _get_brand_folders(), 'active_brand': active_brand,
    })


def _review_context(request, item):
    reviews = item.reviews.select_related('user').order_by('-created_at', '-pk')
    user_review = None
    if request.user.is_authenticated:
        user_review = reviews.filter(user=request.user).first()
    return {
        'reviews': reviews,
        'user_review': user_review,
        'has_sample_reviews': reviews.filter(is_sample=True).exists(),
    }


def _handle_review_submission(request, *, product=None, accessory=None):
    from .models import Review

    if not request.user.is_authenticated:
        messages.error(request, 'Please sign in to share your review.')
        return redirect(f"{reverse('login')}?next={request.path}")
    comment = request.POST.get('comment', '').strip()
    title = request.POST.get('title', '').strip()[:120]
    try:
        rating = int(request.POST.get('rating', ''))
    except (TypeError, ValueError):
        rating = 0
    if rating not in range(1, 6):
        messages.error(request, 'Please choose a rating from 1 to 5 stars.')
    elif not comment:
        messages.error(request, 'Please write a short review before submitting.')
    else:
        review, created = Review.objects.update_or_create(
            user=request.user,
            product=product,
            accessory=accessory,
            defaults={'rating': rating, 'title': title, 'comment': comment},
        )
        messages.success(
            request,
            'Thanks! Your review has been saved.'
            if created
            else 'Your review has been updated.',
        )
    return redirect(f'{request.path}#reviews')


def product_detail(request, pk):
    from django.http import Http404

    from .models import Accessory, Product, Solution

    try:
        product = Product.objects.select_related('category').get(pk=pk)
    except Product.DoesNotExist:
        raise Http404('Product not found.')
    if request.method == 'POST':
        return _handle_review_submission(request, product=product)
    record_recent_activity(
        request, 'product', 'Product: ' + product.name, request.get_full_path()
    )

    related_accessories = Accessory.objects.filter(
        compatible_products=product
    ).select_related('category').order_by('name')

    if product.brand:
        same_brand = Product.objects.filter(brand__iexact=product.brand).exclude(
            pk=product.pk
        ).select_related('category').order_by('name')[:6]
        accessories_brand = Accessory.objects.filter(
            brand__iexact=product.brand
        ).exclude(compatible_products=product).select_related('category').order_by('name')[:6]
    else:
        same_brand = Product.objects.none()
        accessories_brand = Accessory.objects.none()

    solutions = Solution.objects.filter(related_product=product).select_related('category')

    return render(request, 'catalog/product_detail.html', {
        'product': product,
        'related_accessories': related_accessories,
        'brand_accessories': accessories_brand,
        'same_brand': same_brand,
        'solutions': solutions,
        'brands': _get_brand_folders(),
        **_review_context(request, product),
    })


def accessory_detail(request, pk):
    from django.http import Http404

    from .models import Accessory

    try:
        item = Accessory.objects.select_related('category').get(pk=pk)
    except Accessory.DoesNotExist:
        raise Http404('Accessory not found.')
    if request.method == 'POST':
        return _handle_review_submission(request, accessory=item)
    record_recent_activity(
        request, 'accessory', 'Accessory: ' + item.name, request.get_full_path()
    )

    compatible_products = item.compatible_products.select_related('category').order_by('name')
    if item.brand:
        other_items = Accessory.objects.filter(
            brand__iexact=item.brand
        ).exclude(pk=item.pk).select_related('category').order_by('name')[:6]
    else:
        other_items = Accessory.objects.none()

    return render(request, 'catalog/accessory_detail.html', {
        'item': item,
        'compatible_products': compatible_products,
        'other_items': other_items,
        'brands': _get_brand_folders(),
        **_review_context(request, item),
    })


def solution_list(request):
    from .models import Solution

    query = request.GET.get('q', '').strip()
    active_brand = request.GET.get('brand', '').strip()
    record_recent_activity(
        request,
        'repair_guides',
        'Repair guides' + (': ' + query if query else ''),
        request.get_full_path(),
    )
    qs = Solution.objects.select_related('category', 'related_product').all().order_by('-created_at')
    if active_brand:
        qs = qs.filter(
            Q(related_product__brand__iexact=active_brand)
            | (Q(related_product__isnull=True) & Q(title__icontains=active_brand))
        )
    if query:
        qs = _solution_search(qs, query)
    return render(request, 'catalog/solutions.html', {
        'solutions': qs, 'query': query, 'total': qs.count(),
        'brands': _get_brand_folders(), 'active_brand': active_brand,
    })


@require_http_methods(['GET', 'POST'])
def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'GET':
        return render(request, 'auth/register.html')

    form_data = {
        'username': request.POST.get('username', ''),
        'first_name': request.POST.get('first_name', ''),
        'last_name': request.POST.get('last_name', ''),
        'email': request.POST.get('email', ''),
        'phone_number': request.POST.get('phone_number', ''),
        'password': request.POST.get('password', ''),
        'confirm_password': request.POST.get('confirm_password', ''),
    }

    errors = _validate_registration_data(form_data)
    if errors:
        return render(request, 'auth/register.html', {'errors': errors, 'form_data': form_data})

    from apps.users.models import PhoneProfile

    phone_number = re.sub(r'[\s().-]', '', form_data['phone_number'].strip())
    try:
        with transaction.atomic():
            user = User.objects.create_user(
                username=form_data['username'].strip(),
                first_name=form_data['first_name'].strip(),
                last_name=form_data['last_name'].strip(),
                email=form_data['email'].strip(),
                password=form_data['password'],
            )
            if phone_number:
                PhoneProfile.objects.create(user=user, phone_number=phone_number)
    except IntegrityError:
        return render(request, 'auth/register.html', {
            'errors': {'form': 'An account already uses one of those details.'},
            'form_data': form_data,
        })
    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    return redirect('dashboard')
