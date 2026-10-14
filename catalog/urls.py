from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    path("", views.home, name="home"),
    path("products/", views.product_list, name="product_list"),
    path("products/<int:pk>/", views.product_detail, name="product_detail"),
    path("guides/", views.guide_list, name="guide_list"),
    path("guides/<int:pk>/", views.guide_detail, name="guide_detail"),
    path("support/", views.support, name="support"),
]
