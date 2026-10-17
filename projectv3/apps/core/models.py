from django.db import models


class Category(models.Model):
    """Grouping for products, accessories and solutions (ex. Laptops, Audio, Chargers)."""

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'techfix_category'
        verbose_name_plural = 'categories'
        ordering = ['name']

    def __str__(self):
        return self.name


class Product(models.Model):
    """Main technology devices (laptop, phone, printer, router)."""

    name = models.CharField(max_length=255)
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='products'
    )
    brand = models.CharField(max_length=100, blank=True)
    description = models.TextField()
    specifications = models.TextField(blank=True, help_text='RAM, CPU, Storage, etc.')
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    stock_quantity = models.PositiveIntegerField(default=0)
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'techfix_product'
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class Accessory(models.Model):
    """Add-ons: cases, chargers, keyboards, earbuds, cables."""

    name = models.CharField(max_length=255)
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='accessories'
    )
    brand = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    compatibility_notes = models.TextField(
        blank=True, help_text='Ex. Compatible with USB-C laptops'
    )
    stock_quantity = models.PositiveIntegerField(default=0)
    image = models.ImageField(upload_to='accessories/', blank=True, null=True)
    compatible_products = models.ManyToManyField(
        Product, blank=True, related_name='compatible_accessories'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'techfix_accessory'
        verbose_name_plural = 'accessories'
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class Solution(models.Model):
    """Step-by-step fix for a common technology problem."""

    DIFFICULTY_CHOICES = [
        ('Easy', 'Easy'),
        ('Medium', 'Medium'),
        ('Hard', 'Hard'),
    ]

    title = models.CharField(max_length=255)
    problem_description = models.TextField(help_text='Symptoms / common issue')
    steps = models.TextField(help_text='Step 1, Step 2, ...')
    difficulty_level = models.CharField(
        max_length=10, choices=DIFFICULTY_CHOICES, default='Easy'
    )
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='solutions'
    )
    related_product = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True, blank=True, related_name='solutions'
    )
    video_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'techfix_solution'
        ordering = ['-created_at']

    def __str__(self):
        return self.title
