
from django.contrib import admin
from .models import (
    Category,
    Product,
    Device,
    Compatibility,
    UserProfile,
    RecommendationRequest,
    Recommendation,
    TroubleshootingGuide,
    SupportTicket,
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "brand",
        "category",
        "price",
        "stock_quantity",
        "is_active",
    )
    list_filter = ("category", "brand", "is_active")
    search_fields = ("name", "brand")


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "brand",
        "model_name",
        "device_type",
        "connector_type",
    )
    search_fields = ("brand", "model_name")


@admin.register(Compatibility)
class CompatibilityAdmin(admin.ModelAdmin):
    list_display = ("product", "device", "verified")
    list_filter = ("verified",)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "phone", "preferred_budget")


@admin.register(RecommendationRequest)
class RecommendationRequestAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "intended_use",
        "budget_min",
        "budget_max",
        "created_at",
    )


@admin.register(Recommendation)
class RecommendationAdmin(admin.ModelAdmin):
    list_display = ("request", "product", "rank")


@admin.register(TroubleshootingGuide)
class TroubleshootingGuideAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "issue",
        "is_published",
    )
    list_filter = ("is_published",)
    search_fields = ("title", "issue")


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "subject",
        "status",
        "priority",
        "created_at",
    )
    list_filter = ("status", "priority")
    search_fields = ("name", "email", "subject")
