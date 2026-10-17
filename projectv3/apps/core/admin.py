from django.contrib import admin

from .models import Accessory, Category, Product, Solution


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
