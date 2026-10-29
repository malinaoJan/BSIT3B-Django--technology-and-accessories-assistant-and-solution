import json
import logging
import re
from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST

from .assistant import build_answer, search_terms
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
        return render(request, 'auth/login.html', {'locked': True, 'remaining': remaining})

    if request.method == 'GET':
        return render(request, 'auth/login.html')

    username = request.POST.get('username', '').strip()
    password = request.POST.get('password', '')
    user = authenticate(request, username=username, password=password)

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
        return render(request, 'auth/login.html', {'locked': True, 'remaining': remaining})

    remaining_attempts = MAX_FAILED_ATTEMPTS - failed_attempts
    messages.error(request, f'{INVALID_LOGIN_MESSAGE} {remaining_attempts} attempts remaining.')
    return render(request, 'auth/login.html', {'username': username})


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
    from django.db.models import Case, When, Value, IntegerField
    return qs.annotate(
        _legacy=Case(
            When(name__in=legacy_names, then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        )
    ).order_by('_legacy', '-created_at')


CHAT_SESSION_KEY = 'techfix_chat_messages'
MAX_CHAT_MESSAGES = 20
MAX_CHAT_QUESTION_LENGTH = 1000
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
        'price': str(product.price),
        'stock': product.stock_quantity,
        'specs': product.spec_list,
    }


def _serialize_accessory(accessory):
    if accessory is None:
        return None
    return {
        'id': accessory.pk,
        'name': accessory.name,
        'brand': accessory.brand,
        'category': accessory.category.name if accessory.category else '',
        'price': str(accessory.price),
        'stock': accessory.stock_quantity,
        'compatibility': accessory.compatibility_notes,
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
    }
    if serialized['kind'] == 'results':
        serialized['matches'] = _serialize_matches(answer.get('matches'))
    return serialized


def _get_chat_history(request):
    raw = request.session.get(CHAT_SESSION_KEY)
    if not isinstance(raw, list):
        return []
    history = []
    for item in raw[-MAX_CHAT_MESSAGES:]:
        if not isinstance(item, dict):
            continue
        role = item.get('role')
        if role == 'user':
            text = item.get('text')
            if isinstance(text, str) and text.strip():
                history.append({
                    'role': 'user',
                    'text': text.strip()[:MAX_CHAT_QUESTION_LENGTH],
                })
        elif role == 'assistant':
            answer = item.get('answer')
            if isinstance(answer, dict):
                history.append({'role': 'assistant', 'answer': answer})
    return history


def _save_chat_history(request, history):
    request.session[CHAT_SESSION_KEY] = history[-MAX_CHAT_MESSAGES:]


def _append_chat_turn(request, message, answer):
    history = _get_chat_history(request)
    history.append({'role': 'user', 'text': message})
    history.append({'role': 'assistant', 'answer': answer})
    _save_chat_history(request, history)
    record_recent_activity(
        request, 'assistant', message, reverse('dashboard') + '#techfix'
    )


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


def _create_chat_answer(message, history):
    try:
        local_answer = build_answer(_context_query(message, history))
    except Exception:
        logger.exception('Local assistant answer failed')
        local_answer = None

    if local_answer and local_answer.get('strict') and not _is_chat_question(message):
        if local_answer.get('badge') != 'No exact match':
            return local_answer

    answer = enhance_answer(message, local_answer, history=history)
    if answer:
        if local_answer and local_answer.get('matches') and not answer.get('matches'):
            answer['matches'] = local_answer['matches']
        if local_answer and local_answer.get('product') and not answer.get('product'):
            answer['product'] = local_answer['product']
        if local_answer and local_answer.get('accessory') and not answer.get('accessory'):
            answer['accessory'] = local_answer['accessory']
        return answer

    return local_answer


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


@require_POST
@never_cache
def assistant_chat(request):
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
    if not message:
        return JsonResponse({'error': 'Please type a message.'}, status=400)
    if len(message) > MAX_CHAT_QUESTION_LENGTH:
        return JsonResponse(
            {'error': 'Please keep your question under 1,000 characters.'},
            status=400,
        )

    history = _get_chat_history(request)
    try:
        answer = _create_chat_answer(message, history)
    except Exception:
        logger.exception('Assistant chat failed')
        return JsonResponse(
            {'error': 'TechFix could not answer that question right now. '
                      'Please try again.'},
            status=500,
        )
    if not answer:
        return JsonResponse(
            {'error': 'TechFix could not answer that question right now. '
                      'Please try again.'},
            status=502,
        )

    serialized = _serialize_answer(answer)
    _append_chat_turn(request, message, serialized)
    try:
        html = render_to_string(
            'catalog/_chat_message.html',
            {'message': {'role': 'assistant', 'answer': serialized}},
            request=request,
        )
    except Exception:
        logger.exception('Assistant reply rendering failed')
        return JsonResponse(
            {'error': 'TechFix could not display that answer. Please try again.'},
            status=500,
        )
    return JsonResponse({
        'html': html,
        'recent_activities': get_recent_activities(request),
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
    """Name, brand and category search for Library photos."""
    return qs.filter(
        _search_filter(query, ['name', 'brand', 'category__name'])
    ).distinct()


def _is_bag_image(item):
    return item.kind == 'bag' or re.search(
        r'\b(?:bags?|backpacks?|briefcases?|sleeves?|pouches?|totes?|duffel\s+bags?)\b',
        item.name,
        re.IGNORECASE,
    ) is not None


def _get_library_images(query=''):
    """Recent product and accessory photos for the Library images view."""
    from .models import Accessory, Product

    products = Product.objects.exclude(name__in=_legacy_product_names()).exclude(
        image=''
    ).exclude(
        image__isnull=True
    ).select_related('category')
    accessories = Accessory.objects.exclude(
        name__in=_legacy_accessory_names()
    ).exclude(image='').exclude(
        image__isnull=True
    ).select_related('category')
    if query:
        products = _library_image_search(products, query)
        accessories = _library_image_search(accessories, query)

    items = []
    product_count = 0
    for product in products.order_by('-created_at').iterator():
        if _is_bag_image(product):
            continue
        items.append({
            'name': product.name,
            'brand': product.brand,
            'kind': 'Product',
            'image_url': product.image.url,
            'url': reverse('product_detail', args=[product.pk]),
        })
        product_count += 1
        if product_count == 12:
            break
    accessory_count = 0
    for accessory in accessories.order_by('-created_at').iterator():
        if _is_bag_image(accessory):
            continue
        items.append({
            'name': accessory.name,
            'brand': accessory.brand,
            'kind': 'Accessory',
            'image_url': accessory.image.url,
            'url': reverse('accessory_detail', args=[accessory.pk]),
        })
        accessory_count += 1
        if accessory_count == 12:
            break
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
    return render(request, 'catalog/brands.html', {
        'brands': folders,
        'query': query,
        'total': len(folders),
        'image_items': image_items,
        'active_tab': 'all' if query else 'suggested',
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
        products = _product_search(products, query)
        accessories = _accessory_search(accessories, query)
        solutions = _solution_search(solutions, query)
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


def product_detail(request, pk):
    from django.http import Http404

    from .models import Accessory, Product, Solution

    try:
        product = Product.objects.select_related('category').get(pk=pk)
    except Product.DoesNotExist:
        raise Http404('Product not found.')
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
    })


def accessory_detail(request, pk):
    from django.http import Http404

    from .models import Accessory

    try:
        item = Accessory.objects.select_related('category').get(pk=pk)
    except Accessory.DoesNotExist:
        raise Http404('Accessory not found.')
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
        'password': request.POST.get('password', ''),
        'confirm_password': request.POST.get('confirm_password', ''),
    }

    errors = _validate_registration_data(form_data)
    if errors:
        return render(request, 'auth/register.html', {'errors': errors, 'form_data': form_data})

    user = User.objects.create_user(
        username=form_data['username'].strip(),
        first_name=form_data['first_name'].strip(),
        last_name=form_data['last_name'].strip(),
        email=form_data['email'].strip(),
        password=form_data['password'],
    )
    login(request, user)
    return redirect('dashboard')
