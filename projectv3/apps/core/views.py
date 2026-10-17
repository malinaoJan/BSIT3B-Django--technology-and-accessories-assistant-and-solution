from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db.models import Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods, require_POST

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
    return redirect('login')


def _product_search(qs, query):
    """Full-field product search: name, brand, description, specs, category."""
    return qs.filter(
        Q(name__icontains=query) | Q(brand__icontains=query)
        | Q(description__icontains=query) | Q(specifications__icontains=query)
        | Q(category__name__icontains=query)
    )


def _accessory_search(qs, query):
    """Full-field accessory search: name, brand, description, compatibility, category."""
    return qs.filter(
        Q(name__icontains=query) | Q(brand__icontains=query)
        | Q(description__icontains=query) | Q(compatibility_notes__icontains=query)
        | Q(category__name__icontains=query)
    )


def _solution_search(qs, query):
    """Full-field solution search: title, problem, steps, difficulty, category, linked product."""
    return qs.filter(
        Q(title__icontains=query)
        | Q(problem_description__icontains=query)
        | Q(steps__icontains=query)
        | Q(difficulty_level__icontains=query)
        | Q(category__name__icontains=query)
        | Q(related_product__name__icontains=query)
        | Q(related_product__brand__icontains=query)
    )


@login_required(login_url='login')
def home(request):
    from apps.info.models import Info

    from .models import Accessory, Product, Solution

    if request.user.is_superuser:
        infos_qs = Info.objects.all()
        total_users = User.objects.count()
    else:
        infos_qs = Info.objects.filter(user=request.user)
        total_users = None

    total_infos = infos_qs.count()
    recent_infos = infos_qs.order_by('-created_at')[:5]

    # Technology and Accessories Assistant and Solution data
    search_query = request.GET.get('q', '').strip()
    product_result_count = accessory_result_count = solution_result_count = 0
    if search_query:
        product_matches = _product_search(
            Product.objects.select_related('category'), search_query
        )
        accessory_matches = _accessory_search(
            Accessory.objects.select_related('category'), search_query
        )
        solution_matches = _solution_search(
            Solution.objects.select_related('category', 'related_product'), search_query
        )
        product_result_count = product_matches.count()
        accessory_result_count = accessory_matches.count()
        solution_result_count = solution_matches.count()
        products = product_matches[:6]
        accessories = accessory_matches[:6]
        solutions = solution_matches[:6]
    else:
        products = Product.objects.select_related('category').all()[:6]
        accessories = Accessory.objects.select_related('category').all()[:6]
        solutions = Solution.objects.select_related('category', 'related_product').all()[:6]

    return render(request, 'home.html', {
        'total_users': total_users,
        'total_infos': total_infos,
        'recent_infos': recent_infos,
        'products': products,
        'accessories': accessories,
        'solutions': solutions,
        'total_products': Product.objects.count(),
        'total_accessories': Accessory.objects.count(),
        'total_solutions': Solution.objects.count(),
        'search_query': search_query,
        'product_result_count': product_result_count,
        'accessory_result_count': accessory_result_count,
        'solution_result_count': solution_result_count,
        'brands': _get_brand_folders(),
        'brands_preview': sorted(
            _get_brand_folders(),
            key=lambda f: f['product_count'] + f['accessory_count'] + f['solution_count'],
            reverse=True,
        )[:6],
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


def _canonical_brand(brand):
    """Return the stored casing of a brand (case-insensitive match), or None."""
    for name in _get_all_brands():
        if name.lower() == (brand or '').lower():
            return name
    return None


@login_required(login_url='login')
def brand_list(request):
    query = request.GET.get('q', '').strip()
    folders = _get_brand_folders()
    if query:
        folders = [f for f in folders if query.lower() in f['name'].lower()]
    return render(request, 'catalog/brands.html', {
        'brands': folders, 'query': query, 'total': len(folders),
    })


@login_required(login_url='login')
def brand_detail(request, brand):
    from django.http import Http404

    from .models import Accessory, Product, Solution

    canonical = _canonical_brand(brand)
    if canonical is None:
        raise Http404('Brand not found.')
    query = request.GET.get('q', '').strip()

    products = Product.objects.filter(brand__iexact=canonical).select_related('category')
    accessories = Accessory.objects.filter(brand__iexact=canonical).select_related('category')
    solutions = Solution.objects.filter(
        Q(related_product__brand__iexact=canonical)
        | (Q(related_product__isnull=True) & Q(title__icontains=canonical))
    ).select_related('category', 'related_product')
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


@login_required(login_url='login')
def product_list(request):
    from .models import Product

    query = request.GET.get('q', '').strip()
    active_brand = request.GET.get('brand', '').strip()
    qs = Product.objects.select_related('category').all()
    if active_brand:
        qs = qs.filter(brand__iexact=active_brand)
    if query:
        qs = _product_search(qs, query)
    return render(request, 'catalog/products.html', {
        'products': qs, 'query': query, 'total': qs.count(),
        'brands': _get_brand_folders(), 'active_brand': active_brand,
    })


@login_required(login_url='login')
def accessory_list(request):
    from .models import Accessory

    query = request.GET.get('q', '').strip()
    active_brand = request.GET.get('brand', '').strip()
    qs = Accessory.objects.select_related('category').all()
    if active_brand:
        qs = qs.filter(brand__iexact=active_brand)
    if query:
        qs = _accessory_search(qs, query)
    return render(request, 'catalog/accessories.html', {
        'accessories': qs, 'query': query, 'total': qs.count(),
        'brands': _get_brand_folders(), 'active_brand': active_brand,
    })


@login_required(login_url='login')
def product_detail(request, pk):
    from django.http import Http404

    from .models import Accessory, Product, Solution

    try:
        product = Product.objects.select_related('category').get(pk=pk)
    except Product.DoesNotExist:
        raise Http404('Product not found.')

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


@login_required(login_url='login')
def accessory_detail(request, pk):
    from django.http import Http404

    from .models import Accessory

    try:
        item = Accessory.objects.select_related('category').get(pk=pk)
    except Accessory.DoesNotExist:
        raise Http404('Accessory not found.')

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


@login_required(login_url='login')
def solution_list(request):
    from .models import Solution

    query = request.GET.get('q', '').strip()
    active_brand = request.GET.get('brand', '').strip()
    qs = Solution.objects.select_related('category', 'related_product').all()
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
