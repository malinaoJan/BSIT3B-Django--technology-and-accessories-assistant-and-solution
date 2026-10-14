from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import SupportTicketForm
from .models import (
    Category,
    Compatibility,
    Device,
    Product,
    SupportTicket,
    TroubleshootingGuide,
)


def _base_context(**extra):
    context = {
        "nav_categories": Category.objects.annotate(
            product_count=Count("products", filter=Q(products__is_active=True))
        ).order_by("name"),
    }
    context.update(extra)
    return context


def home(request):
    featured = (
        Product.objects.filter(is_active=True)
        .select_related("category")
        .order_by("-created_at")[:8]
    )
    categories = Category.objects.annotate(
        product_count=Count("products", filter=Q(products__is_active=True))
    ).order_by("name")
    guides = TroubleshootingGuide.objects.filter(is_published=True).order_by("-created_at")[:3]

    stats = {
        "products": Product.objects.filter(is_active=True).count(),
        "categories": Category.objects.count(),
        "guides": TroubleshootingGuide.objects.filter(is_published=True).count(),
        "devices": Device.objects.count(),
    }
    return render(
        request,
        "catalog/home.html",
        _base_context(
            featured=featured,
            categories=categories,
            guides=guides,
            stats=stats,
            active="home",
        ),
    )


def product_list(request):
    query = request.GET.get("q", "").strip()
    category_id = request.GET.get("category", "").strip()
    sort = request.GET.get("sort", "newest")

    products = Product.objects.filter(is_active=True).select_related("category")

    if query:
        products = products.filter(
            Q(name__icontains=query)
            | Q(brand__icontains=query)
            | Q(description__icontains=query)
        )
    if category_id:
        products = products.filter(category_id=category_id)

    sort_map = {
        "newest": "-created_at",
        "price_asc": "price",
        "price_desc": "-price",
        "name": "name",
    }
    products = products.order_by(sort_map.get(sort, "-created_at"))

    context = _base_context(
        products=products,
        query=query,
        selected_category=category_id,
        sort=sort,
        active="products",
    )
    return render(request, "catalog/product_list.html", context)


def product_detail(request, pk):
    product = get_object_or_404(
        Product.objects.select_related("category"), pk=pk, is_active=True
    )
    compatibilities = (
        Compatibility.objects.filter(product=product)
        .select_related("device")
        .order_by("device__brand", "device__model_name")
    )
    related = (
        Product.objects.filter(category=product.category, is_active=True)
        .exclude(pk=product.pk)
        .select_related("category")[:4]
    )
    return render(
        request,
        "catalog/product_detail.html",
        _base_context(
            product=product,
            compatibilities=compatibilities,
            related=related,
            active="products",
        ),
    )


def guide_list(request):
    query = request.GET.get("q", "").strip()
    guides = TroubleshootingGuide.objects.filter(is_published=True)
    if query:
        guides = guides.filter(
            Q(title__icontains=query) | Q(issue__icontains=query) | Q(symptoms__icontains=query)
        )
    guides = guides.order_by("-created_at")
    return render(
        request,
        "catalog/guide_list.html",
        _base_context(guides=guides, query=query, active="guides"),
    )


def guide_detail(request, pk):
    guide = get_object_or_404(TroubleshootingGuide, pk=pk, is_published=True)
    steps = [s.strip() for s in guide.steps.splitlines() if s.strip()]
    return render(
        request,
        "catalog/guide_detail.html",
        _base_context(guide=guide, steps=steps, active="guides"),
    )


def support(request):
    if request.method == "POST":
        form = SupportTicketForm(request.POST)
        if form.is_valid():
            ticket = form.save(commit=False)
            if request.user.is_authenticated:
                ticket.user = request.user
            ticket.save()
            messages.success(
                request,
                "Thanks! Your support ticket has been submitted. Our team will get back to you soon.",
            )
            return redirect("catalog:support")
    else:
        form = SupportTicketForm()

    return render(
        request,
        "catalog/support.html",
        _base_context(form=form, active="support"),
    )
