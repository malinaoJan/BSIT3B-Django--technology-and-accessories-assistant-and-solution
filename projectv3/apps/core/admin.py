from django.contrib import admin

from .models import Accessory, Category, Product, Review, Solution


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    search_fields = ('name',)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'brand', 'category', 'price', 'stock_quantity', 'created_at')
    list_filter = ('category',)
    search_fields = ('name', 'brand', 'description')


@admin.register(Accessory)
class AccessoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'brand', 'category', 'price', 'stock_quantity')
    list_filter = ('category',)
    search_fields = ('name', 'brand')
    filter_horizontal = ('compatible_products',)


@admin.register(Solution)
class SolutionAdmin(admin.ModelAdmin):
    list_display = ('title', 'difficulty_level', 'category', 'related_product', 'created_at')
    list_filter = ('difficulty_level', 'category')
    search_fields = ('title', 'problem_description')


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('user', 'item', 'rating', 'title', 'is_sample', 'created_at')
    list_filter = ('is_sample', 'rating', 'created_at')
    search_fields = (
        'user__username',
        'user__first_name',
        'user__last_name',
        'title',
        'comment',
        'product__name',
        'accessory__name',
    )
    autocomplete_fields = ('user', 'product', 'accessory')
    list_select_related = ('user', 'product', 'accessory')
    readonly_fields = ('created_at', 'updated_at')

    @admin.display(description='Item')
    def item(self, obj):
        return obj.product or obj.accessory
